
from datetime import date

import pytest
from sqlalchemy import func, select

from database import make_engine, init_database
from models import ScheduleEventDB
from approval_service import ApprovalService
from scheduling_engine import ScheduleRequest


TEST_DATE = date(2030, 5, 10)


@pytest.fixture
def service(tmp_path):
    db_path = tmp_path / "test_scheduler.db"

    engine = make_engine(
        f"sqlite:///{db_path.as_posix()}"
    )
    init_database(engine)

    yield ApprovalService(engine)
    engine.dispose()


def make_proposal(service):
    request = ScheduleRequest(
        "Belajar Python",
        TEST_DATE,
        60,
        "morning",
    )

    suggestions = service.scheduler.recommend(
        request, events=[], limit=3
    )

    result = {
        "status": "pending_approval",
        "command": {
            "action": "create",
            "task_name": request.title,
            "duration_minutes": 60,
            "date_reference": "tomorrow",
            "preferred_period": "morning",
        },
        "suggestions": [
            {
                "title": s.title,
                "date": s.date,
                "start": s.start,
                "end": s.end,
                "score": s.score,
            }
            for s in suggestions
        ],
    }

    return service.save_proposal(
        "Tambahkan belajar Python selama 1 jam",
        result,
    )


def count_events(service):
    with service.Session() as session:
        return session.scalar(
            select(func.count()).select_from(ScheduleEventDB)
        )


def test_proposal_is_persisted(service):
    proposal = make_proposal(service)

    assert proposal["status"] == "pending"
    assert proposal["proposal_id"] > 0
    assert len(proposal["options"]) > 0
    assert count_events(service) == 0


def test_approval_creates_event(service):
    proposal = make_proposal(service)
    option = proposal["options"][0]

    result = service.approve(
        proposal["proposal_id"], option["option_id"]
    )

    assert result["status"] == "approved"
    assert count_events(service) == 1


def test_duplicate_approval_is_blocked(service):
    proposal = make_proposal(service)
    option = proposal["options"][0]

    first = service.approve(
        proposal["proposal_id"], option["option_id"]
    )
    second = service.approve(
        proposal["proposal_id"], option["option_id"]
    )

    assert first["status"] == "approved"
    assert second["status"] == "already_processed"
    assert count_events(service) == 1


def test_conflict_is_rechecked(service):
    proposal = make_proposal(service)
    option = proposal["options"][0]

    # Another event occupies the slot after
    # the proposal has been generated.
    with service.Session.begin() as session:
        session.add(
            ScheduleEventDB(
                title="Meeting mendadak",
                event_date=TEST_DATE,
                start_time=option["start"],
                end_time=option["end"],
                category="fixed",
            )
        )

    result = service.approve(
        proposal["proposal_id"], option["option_id"]
    )

    assert result["status"] == "conflict_or_invalid"
    assert count_events(service) == 1


def test_invalid_option_is_rejected(service):
    proposal = make_proposal(service)

    result = service.approve(
        proposal["proposal_id"], option_id=999999
    )

    assert result["status"] == "invalid_option"
    assert count_events(service) == 0


def test_option_from_other_proposal_is_rejected(service):
    first = make_proposal(service)
    second = make_proposal(service)

    foreign_option = second["options"][0]["option_id"]

    result = service.approve(
        first["proposal_id"], foreign_option
    )

    assert result["status"] == "invalid_option"
    assert count_events(service) == 0
