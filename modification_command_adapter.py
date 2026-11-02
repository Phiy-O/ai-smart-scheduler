
from dataclasses import dataclass
from datetime import date, timedelta

from schedule_commands import (
    UpdateCommand,
    RescheduleCommand,
    DeleteCommand,
)
from modification_preview import (
    ModificationAction,
    ModificationRequest,
)


@dataclass(frozen=True)
class AdaptationResult:
    status: str
    request: ModificationRequest | None = None
    reason: str | None = None


def resolve_date_reference(
    reference: str | None,
    today: date,
) -> date | None:
    if reference is None:
        return None

    if reference == "today":
        return today

    if reference == "tomorrow":
        return today + timedelta(days=1)

    raise ValueError(
        f"Unsupported date reference: {reference}"
    )


def adapt_modification_command(
    command: UpdateCommand | RescheduleCommand | DeleteCommand,
    reference_date: date,
) -> AdaptationResult:

    if not isinstance(
        command,
        (UpdateCommand, RescheduleCommand, DeleteCommand),
    ):
        return AdaptationResult(
            status="unsupported_command",
            reason="Not a modification command",
        )

    target_title = command.target.task_name.strip()

    if not target_title:
        return AdaptationResult(
            status="insufficient_evidence",
            reason="Missing target title",
        )

    target_date = resolve_date_reference(
        command.target.date_reference,
        reference_date,
    )

    if isinstance(command, DeleteCommand):
        return AdaptationResult(
            status="ready",
            request=ModificationRequest(
                action=ModificationAction.DELETE,
                target_title=target_title,
                target_date=target_date,
            ),
        )

    if isinstance(command, UpdateCommand):
        duration = command.changes.duration_minutes
        period = command.changes.preferred_period

        if duration is None and period is None:
            return AdaptationResult(
                status="insufficient_evidence",
                reason="No update changes provided",
            )

        return AdaptationResult(
            status="unsupported_change",
            reason=(
                "Duration and preferred-period updates "
                "need dedicated preview support"
            ),
        )

    if isinstance(command, RescheduleCommand):
        new_date = resolve_date_reference(
            command.new_date_reference,
            reference_date,
        )

        if new_date is None and command.new_period is None:
            return AdaptationResult(
                status="insufficient_evidence",
                reason="No reschedule destination provided",
            )

        if command.new_period is not None:
            return AdaptationResult(
                status="requires_slot_selection",
                reason=(
                    "A target period requires scheduling-engine "
                    "slot recommendations"
                ),
            )

        return AdaptationResult(
            status="ready",
            request=ModificationRequest(
                action=ModificationAction.RESCHEDULE,
                target_title=target_title,
                target_date=target_date,
                new_date=new_date,
            ),
        )
