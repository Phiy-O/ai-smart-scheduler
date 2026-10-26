
from datetime import datetime, timedelta, timezone
from enum import Enum


PROPOSAL_TTL = timedelta(hours=24)


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class InvalidProposalTransition(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_expiration(
    created_at: datetime,
) -> datetime:
    if created_at.tzinfo is None:
        # Existing application timestamps are interpreted
        # as UTC for this initial implementation.
        created_at = created_at.replace(tzinfo=timezone.utc)

    return created_at + PROPOSAL_TTL


def effective_status(
    status: str,
    expires_at: datetime | None,
    now: datetime | None = None,
) -> ProposalStatus:
    current = ProposalStatus(status)

    if current != ProposalStatus.PENDING:
        return current

    if expires_at is None:
        return current

    now = now or utc_now()

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now >= expires_at:
        return ProposalStatus.EXPIRED

    return current


def require_pending(
    status: str,
    expires_at: datetime | None,
    now: datetime | None = None,
) -> None:
    current = effective_status(
        status, expires_at, now
    )

    if current != ProposalStatus.PENDING:
        raise InvalidProposalTransition(
            f"Proposal is {current.value}, not pending"
        )
