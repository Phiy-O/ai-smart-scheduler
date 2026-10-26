
from datetime import date, timedelta

from experiments.archives.schedule_commands import CommandParser
from evidence_validation import validate_evidence
from schedule_repository import ScheduleRepository
from scheduling_engine import (
    SchedulingEngine,
    ScheduleRequest,
)


def parse_date_reference(reference):
    if reference == "today":
        return date.today()

    if reference == "tomorrow":
        return date.today() + timedelta(days=1)

    return None


class AIScheduler:
    def __init__(
        self,
        repository: ScheduleRepository,
        parser=None,
    ):
        self.repository = repository
        self.parser = parser or CommandParser()
        self.engine = SchedulingEngine(
            repository.preferences
        )

    def process(self, instruction: str):
        command = self.parser.parse(instruction)

        if command.action == "clarify":
            return {
                "status": "needs_clarification",
                "question": command.clarification_question,
            }

        if command.action != "create":
            return {
                "status": "unsupported_action",
                "action": command.action,
                "message": (
                    "Operasi ini belum didukung "
                    "oleh AI Scheduler V1."
                ),
            }

        evidence = validate_evidence(
            instruction, command
        )

        if not evidence.valid:
            return {
                "status": "evidence_rejected",
                "issues": evidence.issues,
            }

        if command.duration_minutes is None:
            return {
                "status": "needs_clarification",
                "question": "Berapa lama aktivitas ini?",
            }

        target_date = parse_date_reference(
            command.date_reference
        )

        if target_date is None:
            return {
                "status": "needs_clarification",
                "question": "Aktivitas ini untuk tanggal berapa?",
            }

        request = ScheduleRequest(
            title=command.task_name,
            event_date=target_date,
            duration_minutes=command.duration_minutes,
            preferred_period=command.preferred_period,
        )

        # Unified calendar state:
        # read existing activities from SQLite.
        existing_events = self.repository.list_events(
            target_date
        )

        suggestions = self.engine.recommend(
            request=request,
            events=existing_events,
            limit=3,
        )

        if not suggestions:
            return {
                "status": "no_available_slots",
                "message": (
                    "Tidak ditemukan slot yang sesuai "
                    "dengan kalender saat ini."
                ),
            }

        return {
            "status": "pending_approval",
            "command": command.model_dump(),
            "suggestions": [
                {
                    "title": s.title,
                    "date": s.date,
                    "start": s.start,
                    "end": s.end,
                    "score": s.score,
                    "reasons": s.reasons,
                }
                for s in suggestions
            ],
        }
