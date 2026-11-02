
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from models import ScheduleEventDB
from modification_preview import (
    ModificationAction,
    ModificationRequest,
)
from modification_service import ModificationService


TEST_DATE = date(2026, 10, 27)


@pytest.fixture
def service_and_engine(migrated_database):
    engine = create_engine(migrated_database)

    with Session(engine) as session:
        session.add_all([
            ScheduleEventDB(
                title="Belajar Python",
                event_date=TEST_DATE,
                start_time="09:00",
                end_time="10:00",
                category="fixed",
            ),
            ScheduleEventDB(
                title="Belajar Python",
                event_date=TEST_DATE,
                start_time="15:00",
                end_time="16:00",
                category="fixed",
            ),
            ScheduleEventDB(
                title="Meeting Proyek",
                event_date=TEST_DATE,
                start_time="13:00",
                end_time="14:00",
                category="fixed",
            ),
        ])
        session.commit()

    yield ModificationService(engine), engine

    engine.dispose()


def test_reschedule_preview(service_and_engine):
    service, _ = service_and_engine

    result = service.preview(
        ModificationRequest(
            action=ModificationAction.RESCHEDULE,
            target_title="Belajar Python",
            target_date=TEST_DATE,
            target_period="afternoon",
            new_start_time="16:00",
        )
    )

    assert result.status == "preview_ready"
    assert result.before["start_time"] == "15:00"
    assert result.after["start_time"] == "16:00"
    assert result.after["end_time"] == "17:00"


def test_update_title_preview(service_and_engine):
    service, _ = service_and_engine

    result = service.preview(
        ModificationRequest(
            action=ModificationAction.UPDATE,
            target_title="Meeting Proyek",
            target_date=TEST_DATE,
            new_title="Meeting Sprint",
        )
    )

    assert result.status == "preview_ready"
    assert result.before["title"] == "Meeting Proyek"
    assert result.after["title"] == "Meeting Sprint"


def test_delete_preview(service_and_engine):
    service, _ = service_and_engine

    result = service.preview(
        ModificationRequest(
            action=ModificationAction.DELETE,
            target_title="Meeting Proyek",
            target_date=TEST_DATE,
        )
    )

    assert result.status == "preview_ready"
    assert result.after is None


def test_ambiguous_target(service_and_engine):
    service, _ = service_and_engine

    result = service.preview(
        ModificationRequest(
            action=ModificationAction.DELETE,
            target_title="Belajar Python",
            target_date=TEST_DATE,
        )
    )

    assert result.status == "ambiguous"
    assert len(result.candidates) == 2


def test_missing_target(service_and_engine):
    service, _ = service_and_engine

    result = service.preview(
        ModificationRequest(
            action=ModificationAction.DELETE,
            target_title="Belajar Java",
            target_date=TEST_DATE,
        )
    )

    assert result.status == "not_found"


def test_preview_does_not_modify_database(service_and_engine):
    service, engine = service_and_engine

    service.preview(
        ModificationRequest(
            action=ModificationAction.DELETE,
            target_title="Meeting Proyek",
            target_date=TEST_DATE,
        )
    )

    with Session(engine) as session:
        rows = session.scalars(
            select(ScheduleEventDB)
        ).all()

        assert len(rows) == 3
        assert any(
            row.title == "Meeting Proyek"
            for row in rows
        )


def test_update_requires_new_title(service_and_engine):
    service, _ = service_and_engine

    result = service.preview(
        ModificationRequest(
            action=ModificationAction.UPDATE,
            target_title="Meeting Proyek",
            target_date=TEST_DATE,
        )
    )

    assert result.status == "invalid_request"


def test_reschedule_requires_new_target_time_or_date(
    service_and_engine,
):
    service, _ = service_and_engine

    result = service.preview(
        ModificationRequest(
            action=ModificationAction.RESCHEDULE,
            target_title="Meeting Proyek",
            target_date=TEST_DATE,
        )
    )

    assert result.status == "invalid_request"
