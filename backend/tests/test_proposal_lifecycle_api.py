
from datetime import date, timedelta
from urllib import response

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from models import ScheduleProposalDB
from proposal_lifecycle import utc_now
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture
def client_and_db(migrated_database):
    app = create_app(database_url=migrated_database)

    with TestClient(app) as client:
        yield client, migrated_database


def create_proposal(database_url, *, expired=False):
    engine = create_engine(database_url)

    created_at = utc_now() - (
        timedelta(hours=25)
        if expired
        else timedelta(minutes=5)
    )

    expires_at = created_at + timedelta(hours=24)

    with Session(engine) as session:
        proposal = ScheduleProposalDB(
            title="Belajar Python",
            event_date=date.today() + timedelta(days=1),
            duration_minutes=60,
            preferred_period="afternoon",
            original_instruction="Belajar Python besok siang",
            status="pending",
            created_at=created_at,
            expires_at=expires_at,
        )

        session.add(proposal)
        session.commit()
        proposal_id = proposal.id

    engine.dispose()
    return proposal_id


def test_reject_pending_proposal(client_and_db):
    client, db_url = client_and_db
    proposal_id = create_proposal(db_url)

    response = client.post(
        f"/proposals/{proposal_id}/reject"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_reject_twice_returns_conflict(client_and_db):
    client, db_url = client_and_db
    proposal_id = create_proposal(db_url)

    client.post(f"/proposals/{proposal_id}/reject")

    response = client.post(
        f"/proposals/{proposal_id}/reject"
    )

    assert response.status_code == 409


def test_reject_missing_proposal(client_and_db):
    client, _ = client_and_db

    response = client.post(
        "/proposals/999999/reject"
    )

    assert response.status_code == 404


def test_reject_expired_proposal(client_and_db):
    client, db_url = client_and_db
    proposal_id = create_proposal(
        db_url, expired=True
    )

    response = client.post(
        f"/proposals/{proposal_id}/reject"
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]["proposal_status"]
        == "expired"
    )


def test_expired_status_is_persisted(client_and_db):
    client, db_url = client_and_db
    proposal_id = create_proposal(
        db_url, expired=True
    )

    client.post(
        f"/proposals/{proposal_id}/reject"
    )

    engine = create_engine(db_url)

    with Session(engine) as session:
        proposal = session.get(
            ScheduleProposalDB,
            proposal_id,
        )
        assert proposal.status == "expired"

    engine.dispose()


def test_rejected_proposal_cannot_be_approved(client_and_db):
    client, db_url = client_and_db
    proposal_id = create_proposal(db_url)

    assert client.post(
        f"/proposals/{proposal_id}/reject"
    ).status_code == 200

    response = client.post(
        f"/proposals/{proposal_id}/approve",
        json={"option_id": 1},
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]["proposal_status"]
        == "rejected"
    )


def test_expired_proposal_cannot_be_approved(client_and_db):
    client, db_url = client_and_db
    proposal_id = create_proposal(
        db_url, expired=True
    )

    response = client.post(
        f"/proposals/{proposal_id}/approve",
        json={"option_id": 1},
    )
    print("STATUS:", response.status_code)
    print("BODY:", response.json())

    assert response.status_code == 409
    assert (
        response.json()["detail"]["proposal_status"]
        == "expired"
    )
    
