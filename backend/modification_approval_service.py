
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from models import (
    ScheduleEventDB,
    ModificationProposalDB,
)
from modification_preview import ModificationPreview
from modification_service import event_to_dict
from proposal_lifecycle import get_expiration

from datetime import date

from sqlalchemy import select

from schedule_policy import (
    EventInput,
    validate_event,
    ScheduleConflictError,
    ScheduleValidationError,
)
from target_resolution import ScheduleEvent
from preferences_repository import PreferencesRepository


def utc_now():
    return datetime.now(timezone.utc)


def as_utc(value):
    # SQLite may return naive datetimes even when
    # DateTime(timezone=True) is configured.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class ModificationApprovalService:
    def __init__(self, engine):
        self.engine = engine
        self.preferences_repository = PreferencesRepository(engine)

    def create_proposal(
        self,
        preview: ModificationPreview,
    ) -> dict:
        if (
            preview.status != "preview_ready"
            or preview.action not in {
                "update", "reschedule", "delete"
            }
            or preview.target_id is None
            or preview.before is None
        ):
            raise ValueError("Invalid modification preview")

        if preview.action == "delete":
            if preview.after is not None:
                raise ValueError("Delete must have no after snapshot")
        else:
            if preview.after is None:
                raise ValueError("Missing after snapshot")
            
            if preview.after == preview.before:
                raise ValueError(
                    "Modification must change the schedule"
                )

            # The preview must modify the same event.
            if preview.after.get("id") != preview.target_id:
                raise ValueError("Target ID mismatch")

        with Session(self.engine) as session:
            session.execute(text("BEGIN IMMEDIATE"))

            event = session.get(
                ScheduleEventDB, preview.target_id
            )

            if event is None:
                session.rollback()
                return {"status": "target_not_found"}

            current = event_to_dict(event)

            if current != preview.before:
                session.rollback()
                return {"status": "stale_preview"}

            now = utc_now()

            proposal = ModificationProposalDB(
                action=preview.action,
                target_event_id=event.id,
                before_snapshot=current,
                after_snapshot=preview.after,
                status="pending",
                created_at=now,
                expires_at=get_expiration(now),
            )

            session.add(proposal)
            session.flush()

            result = {
                "status": "pending_approval",
                "proposal_id": proposal.id,
                "action": proposal.action,
                "before": current,
                "after": proposal.after_snapshot,
            }

            session.commit()
            return result

    def create_delete_proposal(self, preview):
        return self.create_proposal(preview)


    def approve(self, proposal_id: int) -> dict:
        with Session(self.engine) as session:
            session.execute(text("BEGIN IMMEDIATE"))

            proposal = session.get(
                ModificationProposalDB,
                proposal_id,
            )

            if proposal is None:
                session.rollback()
                return {"status": "not_found"}

            if proposal.status != "pending":
                session.commit()
                return {
                    "status": "invalid_transition",
                    "proposal_status": proposal.status,
                }

            if utc_now() >= as_utc(proposal.expires_at):
                proposal.status = "expired"
                session.commit()
                return {"status": "expired"}

            if proposal.action not in {
                "delete", "update", "reschedule"
            }:
                session.rollback()
                return {"status": "unsupported_action"}

            event = session.get(
                ScheduleEventDB,
                proposal.target_event_id,
            )

            if event is None:
                session.rollback()
                return {"status": "target_not_found"}

            current = event_to_dict(event)

            if current != proposal.before_snapshot:
                session.rollback()
                return {
                    "status": "stale_preview",
                    "message": (
                        "Jadwal berubah sejak preview dibuat"
                    ),
                }

            event_id = event.id

            if proposal.action == "delete":
                session.delete(event)

            else:
                after = proposal.after_snapshot

                if (
                    not isinstance(after, dict)
                    or after.get("id") != event_id
                ):
                    session.rollback()
                    return {"status": "invalid_proposal"}

                # Only allow known mutable event fields.
                # Immutable identity and category are preserved.
                if after.get("category") != current["category"]:
                    session.rollback()
                    return {"status": "invalid_proposal"}

                try:
                    new_date = date.fromisoformat(
                        after["event_date"]
                    )
                    new_title = after["title"]
                    new_start = after["start_time"]
                    new_end = after["end_time"]

                    candidate = EventInput(
                        title=new_title,
                        event_date=new_date,
                        start_time=new_start,
                        end_time=new_end,
                        category=current["category"],
                    )

                    # Exclude the target itself from
                    # overlap and break checks.
                    rows = session.scalars(
                        select(ScheduleEventDB).where(
                            ScheduleEventDB.event_date
                            == new_date,
                            ScheduleEventDB.id != event_id,
                        )
                    ).all()

                    other_events = [
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

                    validate_event(
                        candidate,
                        other_events,
                        self.preferences_repository.get(),
                    )

                except (
                    ValueError,
                    KeyError,
                    TypeError,
                    ScheduleConflictError,
                    ScheduleValidationError,
                ):
                    session.rollback()
                    return {
                        "status": "conflict_or_invalid",
                        "message": (
                            "Jadwal baru tidak memenuhi aturan. "
                            "Buat preview ulang."
                        ),
                    }

                event.title = new_title
                event.event_date = new_date
                event.start_time = new_start
                event.end_time = new_end

            proposal.status = "approved"
            session.commit()

            return {
                "status": "approved",
                "proposal_id": proposal_id,
                "action": proposal.action,
                "event_id": event_id,
                "deleted_event_id": (
                    event_id
                    if proposal.action == "delete"
                    else None
                ),
            }

    def reject(self, proposal_id: int) -> dict:
        with Session(self.engine) as session:
            session.execute(text("BEGIN IMMEDIATE"))

            proposal = session.get(
                ModificationProposalDB, proposal_id
            )

            if proposal is None:
                session.rollback()
                return {"status": "not_found"}

            if proposal.status != "pending":
                session.commit()
                return {
                    "status": "invalid_transition",
                    "proposal_status": proposal.status,
                }

            if utc_now() >= as_utc(proposal.expires_at):
                proposal.status = "expired"
                session.commit()
                return {"status": "expired"}

            proposal.status = "rejected"
            session.commit()

            return {
                "status": "rejected",
                "proposal_id": proposal_id,
            }
