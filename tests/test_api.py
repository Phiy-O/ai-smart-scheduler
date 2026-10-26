
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from experiments.archives.schedule_commands import (
    CreateCommand,
    ClarifyCommand,
)


class FakeParser:
    def parse(self, instruction: str):
        if "tidak jelas" in instruction.lower():
            return ClarifyCommand(
                action="clarify",
                clarification_question=(
                    "Aktivitas apa yang ingin dijadwalkan?"
                ),
            )

        return CreateCommand(
            action="create",
            task_name="belajar Python",
            duration_minutes=120,
            date_reference="tomorrow",
            preferred_period="afternoon",
        )


@pytest.fixture
def client(tmp_path):
    database_path = tmp_path / "api_test.db"

    app = create_app(
        database_url=(
            f"sqlite:///{database_path.as_posix()}"
        ),
        parser=FakeParser(),
    )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def tomorrow():
    return (date.today() + timedelta(days=1)).isoformat()


AI_INSTRUCTION = (
    "Tambahkan belajar Python selama "
    "2 jam besok siang."
)


def create_manual_event(
    client,
    tomorrow,
    title="Kuliah",
    start="08:00",
    end="12:00",
    category="fixed",
):
    return client.post(
        "/schedules",
        json={
            "title": title,
            "event_date": tomorrow,
            "start_time": start,
            "end_time": end,
            "category": category,
        },
    )


def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_manual_schedule_creation(client, tomorrow):
    response = create_manual_event(
        client, tomorrow
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Kuliah"

    calendar = client.get(
        "/schedules",
        params={"event_date": tomorrow},
    )

    assert calendar.status_code == 200
    assert len(calendar.json()["events"]) == 1


def test_manual_schedule_conflict(client, tomorrow):
    first = create_manual_event(
        client, tomorrow
    )
    assert first.status_code == 201

    second = create_manual_event(
        client,
        tomorrow,
        title="Meeting",
        start="09:00",
        end="10:00",
    )

    assert second.status_code == 409


def test_invalid_payload(client, tomorrow):
    response = client.post(
        "/schedules",
        json={
            "title": "",
            "event_date": tomorrow,
            "start_time": "08:00",
            "end_time": "09:00",
            "category": "fixed",
        },
    )

    assert response.status_code == 422


def test_ai_proposal_is_persisted(client):
    response = client.post(
        "/ai/schedule",
        json={"instruction": AI_INSTRUCTION},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "pending_approval"
    assert data["proposal_id"] > 0
    assert len(data["options"]) > 0

    proposal = client.get(
        f"/proposals/{data['proposal_id']}"
    )

    assert proposal.status_code == 200
    assert proposal.json()["status"] == "pending"


def test_ambiguous_instruction(client):
    response = client.post(
        "/ai/schedule",
        json={
            "instruction": "Instruksi tidak jelas"
        },
    )

    assert response.status_code == 200
    assert (
        response.json()["status"]
        == "needs_clarification"
    )


def test_approval_persists_schedule(client, tomorrow):
    response = client.post(
        "/ai/schedule",
        json={"instruction": AI_INSTRUCTION},
    )

    assert response.status_code == 200

    proposal = response.json()
    proposal_id = proposal["proposal_id"]
    option_id = proposal["options"][0]["option_id"]

    approval = client.post(
        f"/proposals/{proposal_id}/approve",
        json={"option_id": option_id},
    )

    assert approval.status_code == 200
    assert approval.json()["status"] == "approved"

    calendar = client.get(
        "/schedules",
        params={"event_date": tomorrow},
    )

    events = calendar.json()["events"]

    assert len(events) == 1
    assert events[0]["title"] == "belajar Python"


def test_duplicate_approval_returns_conflict(client):
    response = client.post(
        "/ai/schedule",
        json={"instruction": AI_INSTRUCTION},
    )

    data = response.json()
    proposal_id = data["proposal_id"]
    option_id = data["options"][0]["option_id"]

    endpoint = f"/proposals/{proposal_id}/approve"
    payload = {"option_id": option_id}

    first = client.post(endpoint, json=payload)
    second = client.post(endpoint, json=payload)

    assert first.status_code == 200
    assert second.status_code == 409
    assert (
        second.json()["detail"]["status"]
        == "already_processed"
    )


def test_approval_rechecks_new_conflict(client, tomorrow):
    response = client.post(
        "/ai/schedule",
        json={"instruction": AI_INSTRUCTION},
    )

    data = response.json()
    proposal_id = data["proposal_id"]
    option = data["options"][0]

    # Insert a manual event AFTER AI made its proposal.
    new_event = create_manual_event(
        client,
        tomorrow,
        title="Meeting mendadak",
        start=option["start"],
        end=option["end"],
    )

    assert new_event.status_code == 201

    approval = client.post(
        f"/proposals/{proposal_id}/approve",
        json={"option_id": option["option_id"]},
    )

    assert approval.status_code == 409
    assert (
        approval.json()["detail"]["status"]
        == "conflict_or_invalid"
    )
