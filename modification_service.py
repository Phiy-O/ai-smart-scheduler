
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

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
            if not request.new_title or not request.new_title.strip():
                return ModificationPreview(
                    status="invalid_request",
                    action=action.value,
                    reason="New title is required",
                )

        if action == ModificationAction.RESCHEDULE:
            if (
                request.new_date is None
                and request.new_start_time is None
            ):
                return ModificationPreview(
                    status="invalid_request",
                    action=action.value,
                    reason="New date or start time required",
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

        if action == ModificationAction.DELETE:
            after = None
        else:
            after = before.copy()

            if action == ModificationAction.UPDATE:
                after["title"] = request.new_title.strip()

            elif action == ModificationAction.RESCHEDULE:
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
