
from datetime import datetime, timedelta, timezone

import pytest

from proposal_lifecycle import (
    ProposalStatus,
    InvalidProposalTransition,
    effective_status,
    require_pending,
)


NOW = datetime(
    2026, 10, 26, 10, 0, tzinfo=timezone.utc
)


def test_pending_proposal_is_valid():
    expiration = NOW + timedelta(hours=1)

    result = effective_status(
        "pending", expiration, NOW
    )

    assert result == ProposalStatus.PENDING


def test_pending_proposal_expires():
    expiration = NOW - timedelta(minutes=1)

    result = effective_status(
        "pending", expiration, NOW
    )

    assert result == ProposalStatus.EXPIRED


def test_exact_expiration_boundary():
    assert effective_status(
        "pending", NOW, NOW
    ) == ProposalStatus.EXPIRED


def test_approved_does_not_expire_again():
    expiration = NOW - timedelta(days=1)

    assert effective_status(
        "approved", expiration, NOW
    ) == ProposalStatus.APPROVED


def test_rejected_cannot_be_approved():
    with pytest.raises(InvalidProposalTransition):
        require_pending(
            "rejected",
            NOW + timedelta(hours=1),
            NOW,
        )


def test_expired_cannot_be_approved():
    with pytest.raises(InvalidProposalTransition):
        require_pending(
            "pending",
            NOW - timedelta(seconds=1),
            NOW,
        )


def test_legacy_proposal_has_no_expiration():
    assert effective_status(
        "pending", None, NOW
    ) == ProposalStatus.PENDING
