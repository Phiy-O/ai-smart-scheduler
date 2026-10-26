
from datetime import date, timedelta

import pytest

from ai_scheduler import AIScheduler
from approval_service import ApprovalService
from database import make_engine, init_database
from schedule_repository import ScheduleRepository
from experiments.archives.schedule_commands import CreateCommand
from scheduling_engine import to_minutes
from schedule_policy import ScheduleConflictError


class FakeParser:
    def parse(self, instruction):
        return CreateCommand(
            action="create",
            task_name="belajar Python",
            duration_minutes=120,
            date_reference="tomorrow",
            preferred_period="afternoon",
        )


INSTRUCTION = (
    "Tambahkan belajar Python "
    "selama 2 jam besok siang."
)


@pytest.fixture
def context(tmp_path):
    path = tmp_path / "unified_test.db"
    engine = make_engine(f"sqlite:///{path.as_posix()}")
    init_database(engine)

    repository = ScheduleRepository(engine)
    ai = AIScheduler(
        repository=repository,
        parser=FakeParser(),
    )
    approval = ApprovalService(
        engine,
        preferences=repository.preferences,
    )

    yield repository, ai, approval
    engine.dispose()



def test_manual_event_is_visible_to_ai(context):
    repository, ai, _ = context
    tomorrow = date.today() + timedelta(days=1)

    repository.create_event(
        "Kuliah", tomorrow,
        "08:00", "12:00",
        category="fixed",
    )

    result = ai.process(INSTRUCTION)

    assert result["status"] == "pending_approval"

    for option in result["suggestions"]:
        assert to_minutes(option["start"]) >= 12 * 60 + 15



def test_manual_conflict_is_rejected(context):
    repository, _, _ = context
    tomorrow = date.today() + timedelta(days=1)

    repository.create_event(
        "Meeting", tomorrow,
        "13:00", "14:00",
    )

    with pytest.raises(ScheduleConflictError):
        repository.create_event(
            "Belajar", tomorrow,
            "13:30", "14:30",
        )


def test_approval_updates_shared_calendar(context):
    repository, ai, approval = context
    tomorrow = date.today() + timedelta(days=1)

    ai_result = ai.process(INSTRUCTION)
    assert ai_result["status"] == "pending_approval"

    proposal = approval.save_proposal(
        INSTRUCTION, ai_result
    )
    option = proposal["options"][0]

    approved = approval.approve(
        proposal["proposal_id"],
        option["option_id"],
    )

    assert approved["status"] == "approved"

    events = repository.list_events(tomorrow)

    assert len(events) == 1
    assert events[0].title == "belajar Python"
    assert events[0].start_time == option["start"]
    assert events[0].end_time == option["end"]


def test_ai_sees_approved_event(context):
    repository, ai, approval = context

    initial = ai.process(INSTRUCTION)
    assert initial["status"] == "pending_approval"

    proposal = approval.save_proposal(
        INSTRUCTION, initial
    )
    option = proposal["options"][0]

    result = approval.approve(
        proposal["proposal_id"],
        option["option_id"],
    )
    assert result["status"] == "approved"

    # The same AI request now reads the updated DB.
    next_result = ai.process(INSTRUCTION)

    if next_result["status"] == "pending_approval":
        for suggestion in next_result["suggestions"]:
            new_start = to_minutes(suggestion["start"])
            new_end = to_minutes(suggestion["end"])

            saved_start = to_minutes(option["start"])
            saved_end = to_minutes(option["end"])

            assert (
                new_end <= saved_start - 15
                or new_start >= saved_end + 15
            )
    else:
        assert next_result["status"] == "no_available_slots"


def test_manual_break_can_touch_existing_event(context):
    repository, _, _ = context
    tomorrow = date.today() + timedelta(days=1)

    repository.create_event(
        "Kuliah", tomorrow,
        "08:00", "12:00",
    )

    rest = repository.create_event(
        "Istirahat", tomorrow,
        "12:00", "13:00",
        category="break",
    )

    assert rest.category == "break"
    assert len(repository.list_events(tomorrow)) == 2
