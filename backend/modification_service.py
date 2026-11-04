
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from models import ScheduleEventDB
from target_resolution import ScheduleEvent
from target_resolution_v2 import (
    TargetQuery,
    TargetResolverV2,
    ResolutionStatus,
)
from modification_preview import (
    ModificationAction,
    ModificationPreview,
    ModificationRequest,
)

from scheduling_engine import (
    SchedulingEngine,
    ScheduleRequest,
    to_minutes,
)
from preferences_repository import PreferencesRepository

MAX_CANDIDATES_SCAN = 500


def event_to_dict(event):
    return {
        "id": event.id,
        "title": event.title,
        "event_date": event.event_date.isoformat(),
        "start_time": event.start_time,
        "end_time": event.end_time,
        "category": event.category,
    }

PERIOD_WINDOWS = {
    "morning": (8 * 60, 12 * 60),
    "afternoon": (12 * 60, 18 * 60),
    "evening": (18 * 60, 20 * 60),
}


def slot_matches_period(
    start: str,
    end: str,
    period: str,
    instruction: str | None = None,
) -> bool:
    lower, upper = PERIOD_WINDOWS[period]

    if instruction:
        text = instruction.casefold()

        if period == "afternoon":
            if "sore" in text:
                lower = 15 * 60
            elif "siang" in text:
                upper = 15 * 60

    return (
        lower <= to_minutes(start)
        and to_minutes(end) <= upper
    )


def shift_end_time(start_time, old_start, old_end):
    fmt = "%H:%M"

    start = datetime.strptime(start_time, fmt)
    before_start = datetime.strptime(old_start, fmt)
    before_end = datetime.strptime(old_end, fmt)

    duration = before_end - before_start

    if duration <= timedelta(0):
        raise ValueError("Invalid existing event duration")

    new_end = start + duration

    if new_end.date() != start.date():
        raise ValueError("Reschedule crosses midnight")

    return new_end.strftime(fmt)


class ModificationService:
    def __init__(self, engine):
        self.engine = engine
        self.resolver = TargetResolverV2()
        self.preferences_repository = PreferencesRepository(engine)

    def _load_events(self, target_date=None):
        with Session(self.engine) as session:
            statement = select(ScheduleEventDB)

            if target_date is not None:
                statement = statement.where(
                    ScheduleEventDB.event_date == target_date
                )

            statement = statement.order_by(
                ScheduleEventDB.event_date,
                ScheduleEventDB.start_time,
                ScheduleEventDB.id,
            ).limit(MAX_CANDIDATES_SCAN + 1)

            rows = session.scalars(statement).all()

            if len(rows) > MAX_CANDIDATES_SCAN:
                raise ValueError(
                    "Too many schedules to resolve safely"
                )

            return [
                ScheduleEvent(
                    id=row.id,
                    title=row.title,
                    event_date=row.event_date,
                    start_time=row.start_time,
                    end_time=row.end_time,
                    category=row.category,
                )
                for row in rows
            ]

    def preview(self, request: ModificationRequest):
        action = request.action

        if not isinstance(action, ModificationAction):
            action = ModificationAction(action)


        if action == ModificationAction.UPDATE:
            if (
                request.new_title is None
                and request.new_duration_minutes is None
            ):
                return ModificationPreview(
                    status="invalid_request",
                    action=action.value,
                    reason="No update changes provided",
                )

            if (
                request.new_duration_minutes is not None
                and request.new_duration_minutes <= 0
            ):
                return ModificationPreview(
                    status="invalid_request",
                    action=action.value,
                    reason="Duration must be positive",
                )

        if action == ModificationAction.RESCHEDULE:
            if (
                request.new_date is None
                and request.new_start_time is None
                and request.new_period is None
            ):
                return ModificationPreview(
                    status="invalid_request",
                    action=action.value,
                    reason="New date, time, or period required",
                )

        query = TargetQuery(
            title=request.target_title,
            event_date=request.target_date,
            start_time=request.target_start_time,
            period=request.target_period,
        )

        try:
            events = self._load_events(
                target_date=request.target_date
            )
        except ValueError as exc:
            return ModificationPreview(
                status="insufficient_evidence",
                action=action.value,
                reason=str(exc),
            )

        resolution = self.resolver.resolve(query, events)

        if resolution.status != ResolutionStatus.MATCHED:
            return ModificationPreview(
                status=resolution.status.value,
                action=action.value,
                candidates=[
                    event_to_dict(event)
                    for event in resolution.candidates
                ],
                reason=resolution.reason,
            )

        target = resolution.candidates[0]
        before = event_to_dict(target)
        
        selected_slot = None

        if (
            action == ModificationAction.RESCHEDULE
            and request.new_period is not None
        ):
            destination_date = (
                request.new_date or target.event_date
            )

            duration = (
                to_minutes(target.end_time)
                - to_minutes(target.start_time)
            )

            if duration <= 0:
                return ModificationPreview(
                    status="invalid_request",
                    action=action.value,
                    reason="Invalid existing duration",
                )

            # Load schedules on the destination date,
            # excluding the event being moved.
            destination_events = [
                event
                for event in self._load_events(
                    target_date=destination_date
                )
                if event.id != target.id
            ]

            schedule_request = ScheduleRequest(
                title=target.title,
                event_date=destination_date,
                duration_minutes=duration,
                preferred_period=request.new_period,
                time_hint=request.time_hint,
            )

            suggestions = SchedulingEngine(
                self.preferences_repository.get()
            ).recommend(
                request=schedule_request,
                events=destination_events,
                limit=20,
            )

            matching_slots = [
                slot
                for slot in suggestions
                if (
                    slot_matches_period(
                        slot.start,
                        slot.end,
                        request.new_period,
                        request.time_hint,
                    )
                    and (
                        destination_date != target.event_date
                        or slot.start != target.start_time
                        or slot.end != target.end_time
                    )
                )
            ]

            if not matching_slots:
                return ModificationPreview(
                    status="no_available_slots",
                    action=action.value,
                    target_id=target.id,
                    before=before,
                    reason=(
                        "No available slot in requested period"
                    ),
                )

            selected_slot = matching_slots[0]

        if action == ModificationAction.DELETE:
            after = None
        else:
            after = before.copy()

            if action == ModificationAction.UPDATE:
                if request.new_title is not None:
                    after["title"] = request.new_title.strip()

                if request.new_duration_minutes is not None:
                    start = datetime.strptime(
                        target.start_time, "%H:%M"
                    )

                    end = start + timedelta(
                        minutes=request.new_duration_minutes
                    )

                    if end.date() != start.date():
                        return ModificationPreview(
                            status="invalid_request",
                            action=action.value,
                            reason="Duration crosses midnight",
                        )

                    after["end_time"] = end.strftime("%H:%M")


            elif action == ModificationAction.RESCHEDULE:
                if selected_slot is not None:
                    after["event_date"] = (
                        request.new_date or target.event_date
                    ).isoformat()
                    after["start_time"] = selected_slot.start
                    after["end_time"] = selected_slot.end

                else:
                    if request.new_date is not None:
                        after["event_date"] = (
                            request.new_date.isoformat()
                        )

                    if request.new_start_time is not None:
                        try:
                            after["end_time"] = shift_end_time(
                                request.new_start_time,
                                target.start_time,
                                target.end_time,
                            )
                        except ValueError as exc:
                            return ModificationPreview(
                                status="invalid_request",
                                action=action.value,
                                reason=str(exc),
                            )

                        after["start_time"] = (
                            request.new_start_time
                        )

        return ModificationPreview(
            status="preview_ready",
            action=action.value,
            target_id=target.id,
            before=before,
            after=after,
            reason="Confirmation required",
        )
