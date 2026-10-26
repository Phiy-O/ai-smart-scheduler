
from datetime import date, datetime, timezone

from sqlalchemy import select, text

from database import make_session_factory
from models import (
    ScheduleEventDB,
    ScheduleProposalDB,
    ProposalOptionDB,
)

from proposal_lifecycle import (
    ProposalStatus,
    InvalidProposalTransition,
    effective_status,
    get_expiration,
    require_pending,
    utc_now,
)

from scheduling_engine import (
    SchedulingEngine,
    ScheduleRequest,
    UserPreferences,
    to_minutes,
)

from schedule_policy import (
    EventInput,
    validate_event,
    ScheduleConflictError,
    ScheduleValidationError,
)

from target_resolution import ScheduleEvent


class ApprovalService:

    def __init__(
        self,
        engine,
        preferences=None,
        preferences_provider=None,
    ):
        self.engine = engine
        self.Session = make_session_factory(engine)
        self._preferences = preferences or UserPreferences(
            day_start="08:00",
            day_end="20:00",
            productive_periods=["morning", "afternoon"],
            avoid_periods=["evening"],
            min_break_minutes=15,
            max_focus_minutes=120,
        )
        self._preferences_provider = preferences_provider
        self.scheduler = SchedulingEngine(self.preferences)

    @property
    def preferences(self):
        if self._preferences_provider is not None:
            return self._preferences_provider()
        return self._preferences
    
    @staticmethod
    def _refresh_expiration(proposal, now=None):
        now = now or utc_now()

        status = effective_status(
            proposal.status,
            proposal.expires_at,
            now,
        )

        if status == ProposalStatus.EXPIRED:
            proposal.status = ProposalStatus.EXPIRED.value

        return status

    def save_proposal(self, instruction, ai_result):
        if ai_result.get("status") != "pending_approval":
            raise ValueError("Only approved AI output stage accepted")

        command = ai_result["command"]
        if command["action"] != "create":
            raise ValueError("Only create proposal supported")

        title = command["task_name"]
        duration = command["duration_minutes"]
        suggestions = ai_result["suggestions"]

        if not title or not isinstance(duration, int) or duration <= 0:
            raise ValueError("Invalid activity")

        if not suggestions:
            raise ValueError("No options to save")

        proposed_date = date.fromisoformat(
            suggestions[0]["date"]
        )
        
        created_at = utc_now()
        proposal = ScheduleProposalDB(
            title=title,
            event_date=proposed_date,
            duration_minutes=duration,
            preferred_period=command.get("preferred_period"),
            original_instruction=instruction,
            status="pending",
            created_at=created_at,
            expires_at=get_expiration(created_at),
        )

        for item in suggestions:
            start = to_minutes(item["start"])
            end = to_minutes(item["end"])

            if (
                item["date"] != proposed_date.isoformat()
                or end - start != duration
                or item["title"] != title
            ):
                raise ValueError("Inconsistent AI proposal option")

            proposal.options.append(
                ProposalOptionDB(
                    start_time=item["start"],
                    end_time=item["end"],
                    score=item["score"],
                )
            )

        with self.Session.begin() as session:
            session.add(proposal)
            session.flush()

            result = {
                "proposal_id": proposal.id,
                "status": proposal.status,
                "options": [
                    {
                        "option_id": option.id,
                        "start": option.start_time,
                        "end": option.end_time,
                    }
                    for option in proposal.options
                ],
            }

        return result

    def approve(self, proposal_id: int, option_id: int):
        with self.Session() as session:
            # Acquire SQLite writer reservation before reading.
            # Prevents two approval transactions from both
            # reading the same free slot and then writing it.
            session.execute(text("BEGIN IMMEDIATE"))

            try:
                proposal = session.get(ScheduleProposalDB, proposal_id)

                if proposal is None:
                    session.rollback()
                    return {
                        "status": "not_found",
                        "proposal_id": proposal_id,
                    }

                current = self._refresh_expiration(proposal)

                # Pertahankan perilaku lama untuk duplicate approval.
                if current == ProposalStatus.APPROVED:
                    session.commit()

                    return {
                        "status": "already_processed",
                        "proposal_id": proposal_id,
                    }

                # Perilaku baru untuk rejected dan expired.
                if current in (
                    ProposalStatus.REJECTED,
                    ProposalStatus.EXPIRED,
                ):
                    session.commit()

                    return {
                        "status": "invalid_transition",
                        "proposal_id": proposal_id,
                        "proposal_status": current.value,
                    }

                # BARU PERIKSA OPTION
                option = session.get(ProposalOptionDB, option_id)

                if option is None or option.proposal_id != proposal_id:
                    session.rollback()
                    return {
                        "status": "invalid_option",
                    }

                # Lanjutkan logika approval lama:
                # validasi konflik, create event, update proposal, commit.

                # Load current committed schedule.
                rows = session.scalars(
                    select(ScheduleEventDB).where(
                        ScheduleEventDB.event_date
                        == proposal.event_date
                    )
                ).all()

                events = [
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

                start = to_minutes(option.start_time)
                end = to_minutes(option.end_time)

                request = ScheduleRequest(
                    title=proposal.title,
                    event_date=proposal.event_date,
                    duration_minutes=proposal.duration_minutes,
                    preferred_period=proposal.preferred_period,
                )

                candidate = EventInput(
                    title=proposal.title,
                    event_date=proposal.event_date,
                    start_time=option.start_time,
                    end_time=option.end_time,
                    category="focus",
                )

                try:
                    if (
                        end - start != proposal.duration_minutes
                    ):
                        raise ScheduleValidationError(
                            "Proposal duration mismatch"
                        )

                    validate_event(
                        candidate,
                        events,
                        self.preferences,
                    )

                except (ScheduleConflictError, ScheduleValidationError):
                    session.rollback()
                    return {
                        "status": "conflict_or_invalid",
                        "message": (
                            "Slot tidak lagi memenuhi aturan. "
                            "Buat rekomendasi baru."
                        ),
                    }
                    
                new_event = ScheduleEventDB(
                    title=proposal.title,
                    event_date=proposal.event_date,
                    start_time=option.start_time,
                    end_time=option.end_time,
                    category="focus",
                )

                session.add(new_event)
                session.flush()

                proposal.status = "approved"
                proposal.approved_option_id = option.id

                new_id = new_event.id
                session.commit()

                return {
                    "status": "approved",
                    "event_id": new_id,
                    "proposal_id": proposal_id,
                    "option_id": option_id,
                }

            except Exception:
                session.rollback()
                raise
    
    def reject(self, proposal_id: int):
        with self.Session() as session:
            # SQLite: acquire the write lock before reading.
            session.execute(text("BEGIN IMMEDIATE"))

            proposal = session.get(
                ScheduleProposalDB,
                proposal_id,
            )

            if proposal is None:
                session.rollback()
                return {
                    "status": "not_found",
                    "proposal_id": proposal_id,
                }

            current = self._refresh_expiration(proposal)

            if current != ProposalStatus.PENDING:
                session.commit()
                return {
                    "status": "invalid_transition",
                    "proposal_id": proposal_id,
                    "proposal_status": current.value,
                }

            proposal.status = ProposalStatus.REJECTED.value
            session.commit()

            return {
                "status": "rejected",
                "proposal_id": proposal_id,
            }

    def get_lifecycle(self, proposal_id: int):
        with self.Session() as session:
            session.execute(text("BEGIN IMMEDIATE"))

            proposal = session.get(
                ScheduleProposalDB,
                proposal_id,
            )

            if proposal is None:
                session.rollback()
                return None

            status = self._refresh_expiration(proposal)

            result = {
                "proposal_id": proposal.id,
                "status": status.value,
                "created_at": (
                    proposal.created_at.isoformat()
                    if proposal.created_at else None
                ),
                "expires_at": (
                    proposal.expires_at.isoformat()
                    if proposal.expires_at else None
                ),
                "approved_option_id": proposal.approved_option_id,
            }

            session.commit()
            return result

