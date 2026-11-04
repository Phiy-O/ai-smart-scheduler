
from dataclasses import dataclass
from datetime import date

from scheduling_engine import UserPreferences, to_minutes
from target_resolution import ScheduleEvent


CATEGORIES = {"fixed", "focus", "break"}


class ScheduleConflictError(ValueError):
    pass


class ScheduleValidationError(ValueError):
    pass


@dataclass
class EventInput:
    title: str
    event_date: date
    start_time: str
    end_time: str
    category: str = "fixed"


def validate_event(
    candidate: EventInput,
    existing: list[ScheduleEvent],
    preferences: UserPreferences,
    exclude_id: int | None = None,
) -> None:
    if not candidate.title.strip():
        raise ScheduleValidationError("Title is required")

    if len(candidate.title) > 200:
        raise ScheduleValidationError("Title is too long")

    if candidate.category not in CATEGORIES:
        raise ScheduleValidationError("Invalid category")

    try:
        start = to_minutes(candidate.start_time)
        end = to_minutes(candidate.end_time)
    except (ValueError, AttributeError) as exc:
        raise ScheduleValidationError(
            "Invalid time format"
        ) from exc

    if start >= end:
        raise ScheduleValidationError(
            "End must be later than start"
        )

    day_start = to_minutes(preferences.day_start)
    day_end = to_minutes(preferences.day_end)

    if start < day_start or end > day_end:
        raise ScheduleValidationError(
            "Outside allowed scheduling hours"
        )

    if (
        candidate.category == "focus"
        and end - start > preferences.max_focus_minutes
    ):
        raise ScheduleValidationError(
            "Focus duration exceeds allowed limit"
        )

    from scheduling_engine import SchedulingEngine
    scheduler = SchedulingEngine(preferences)

    if not scheduler.is_allowed(start, end):
        raise ScheduleValidationError(
            "Overlaps an avoided period"
        )

    for event in existing:
        if event.id == exclude_id:
            continue

        other_start = to_minutes(event.start_time)
        other_end = to_minutes(event.end_time)

        # Break activities occupy real time, but do not
        # introduce an additional buffer around themselves.
        gap = (
            0
            if candidate.category == "break"
            or event.category == "break"
            else preferences.min_break_minutes
        )

        conflict = (
            start < other_end + gap
            and end > other_start - gap
        )

        if conflict:
            raise ScheduleConflictError(
                f"Conflicts with event #{event.id}: "
                f"{event.title}"
            )
