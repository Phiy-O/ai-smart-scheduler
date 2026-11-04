
from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database import Base
from models import ScheduleEventDB
from modification_preview import (
    ModificationPreview,
)
from modification_approval_service import (
    ModificationApprovalService,
)


def setup_case(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'delete_test.db'}"
    )

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        event = ScheduleEventDB(
            title="Belajar Python",
            event_date=date(2026, 11, 4),
            start_time="09:00",
            end_time="10:30",
            category="focus",
        )
        session.add(event)
        session.commit()
        event_id = event.id

    with Session(engine) as session:
        event = session.get(ScheduleEventDB, event_id)
        snapshot = {
            "id": event.id,
            "title": event.title,
            "event_date": event.event_date.isoformat(),
            "start_time": event.start_time,
            "end_time": event.end_time,
            "category": event.category,
        }

    preview = ModificationPreview(
        status="preview_ready",
        action="delete",
        target_id=event_id,
        before=snapshot,
        after=None,
    )

    return engine, event_id, preview


def event_exists(engine, event_id):
    with Session(engine) as session:
        return session.get(ScheduleEventDB, event_id) is not None


def test_delete_only_after_approval(tmp_path):
    engine, event_id, preview = setup_case(tmp_path)
    service = ModificationApprovalService(engine)

    proposal = service.create_delete_proposal(preview)

    assert proposal["status"] == "pending_approval"
    assert event_exists(engine, event_id)

    result = service.approve(proposal["proposal_id"])

    assert result["status"] == "approved"
    assert not event_exists(engine, event_id)


def test_reject_preserves_event(tmp_path):
    engine, event_id, preview = setup_case(tmp_path)
    service = ModificationApprovalService(engine)

    proposal = service.create_delete_proposal(preview)
    result = service.reject(proposal["proposal_id"])

    assert result["status"] == "rejected"
    assert event_exists(engine, event_id)


def test_duplicate_approval_is_rejected(tmp_path):
    engine, event_id, preview = setup_case(tmp_path)
    service = ModificationApprovalService(engine)

    proposal = service.create_delete_proposal(preview)
    proposal_id = proposal["proposal_id"]

    assert service.approve(proposal_id)["status"] == "approved"
    assert service.approve(proposal_id)["status"] == "invalid_transition"


def test_changed_event_cannot_be_deleted(tmp_path):
    engine, event_id, preview = setup_case(tmp_path)
    service = ModificationApprovalService(engine)

    proposal = service.create_delete_proposal(preview)

    with Session(engine) as session:
        event = session.get(ScheduleEventDB, event_id)
        event.title = "Belajar Python Lanjutan"
        session.commit()

    result = service.approve(proposal["proposal_id"])

    assert result["status"] == "stale_preview"
    assert event_exists(engine, event_id)
