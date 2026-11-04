
from types import SimpleNamespace

from ai_scheduler import AIScheduler


class StubParser:
    def __init__(self, command):
        self.command = command

    def parse(self, instruction):
        return self.command


def make_scheduler(command):
    # Only tests early rejection paths.
    # The repository must never be accessed.
    scheduler = AIScheduler.__new__(AIScheduler)
    scheduler.parser = StubParser(command)
    return scheduler


def make_create_command(**overrides):
    fields = {
        "action": "create",
        "task_name": "belajar Python",
        "date_reference": "tomorrow",
        "preferred_period": None,
        "duration_minutes": 90,
    }
    fields.update(overrides)

    return SimpleNamespace(
        **fields,
        model_dump=lambda mode="python": fields.copy(),
    )


def test_missing_explicit_date_is_blocked():
    command = make_create_command(
        date_reference=None,
    )

    scheduler = make_scheduler(command)

    result = scheduler.process(
        "Tambahkan belajar Python besok selama 90 menit"
    )

    assert result["status"] == "evidence_rejected"
    assert any(
        "date_reference" in issue
        for issue in result["issues"]
    )


def test_hallucinated_duration_is_blocked():
    command = make_create_command(
        duration_minutes=60,
    )

    scheduler = make_scheduler(command)

    result = scheduler.process(
        "Tambahkan belajar Python besok"
    )

    assert result["status"] == "evidence_rejected"
    assert any(
        "duration_minutes" in issue
        for issue in result["issues"]
    )


def test_missing_explicit_period_is_blocked():
    command = make_create_command(
        preferred_period=None,
    )

    scheduler = make_scheduler(command)

    result = scheduler.process(
        "Tambahkan belajar Python besok pagi 90 menit"
    )

    assert result["status"] == "evidence_rejected"
    assert any(
        "preferred_period" in issue
        for issue in result["issues"]
    )
