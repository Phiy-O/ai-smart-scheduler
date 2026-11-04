
from datetime import date, timedelta
from alembic import command
from alembic.config import Config
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from schedule_commands import CreateCommand


class FakeParser:
    def parse(self, instruction):
        return CreateCommand(
            action="create",
            task_name="belajar Python",
            duration_minutes=120,
            date_reference="tomorrow",
            preferred_period="afternoon",
        )


INSTRUCTION = (
    "Tambahkan belajar Python selama 2 jam besok siang."
)


@pytest.fixture
def client(migrated_database):
    app = create_app(
        database_url=migrated_database,
        parser=FakeParser(),
    )

    with TestClient(app) as test_client:
        yield test_client


def default_preferences():
    return {
        "day_start": "08:00",
        "day_end": "20:00",
        "productive_periods": ["morning", "afternoon"],
        "avoid_periods": ["evening"],
        "min_break_minutes": 15,
        "max_focus_minutes": 120,
    }


def test_get_default_preferences(client):
    response = client.get("/preferences")

    assert response.status_code == 200
    assert response.json() == default_preferences()


def test_save_preferences(client):
    payload = default_preferences()
    payload["min_break_minutes"] = 30

    response = client.put(
        "/preferences", json=payload
    )

    assert response.status_code == 200

    saved = client.get("/preferences").json()
    assert saved["min_break_minutes"] == 30


def test_reject_invalid_time_range(client):
    payload = default_preferences()
    payload["day_start"] = "20:00"
    payload["day_end"] = "08:00"

    response = client.put(
        "/preferences", json=payload
    )

    assert response.status_code == 422


def test_reject_conflicting_periods(client):
    payload = default_preferences()
    payload["avoid_periods"] = ["morning"]

    response = client.put(
        "/preferences", json=payload
    )

    assert response.status_code == 422


def test_preferences_change_ai_recommendations(client):
    initial = client.post(
        "/ai/schedule",
        json={"instruction": INSTRUCTION},
    )

    assert initial.status_code == 200
    assert initial.json()["status"] == "pending_approval"

    # New window is too short for a 120-minute session.
    payload = default_preferences()
    payload["day_start"] = "09:00"
    payload["day_end"] = "10:00"

    updated = client.put(
        "/preferences", json=payload
    )
    assert updated.status_code == 200

    next_result = client.post(
        "/ai/schedule",
        json={"instruction": INSTRUCTION},
    )

    assert next_result.status_code == 200
    assert next_result.json()["status"] == "no_available_slots"


def test_old_proposal_revalidated_with_new_preferences(client):
    response = client.post(
        "/ai/schedule",
        json={"instruction": INSTRUCTION},
    )

    assert response.status_code == 200

    proposal = response.json()
    assert proposal["status"] == "pending_approval"

    # User changes their allowed scheduling hours.
    payload = default_preferences()
    payload["day_start"] = "09:00"
    payload["day_end"] = "10:00"

    assert client.put(
        "/preferences", json=payload
    ).status_code == 200

    option = proposal["options"][0]

    approval = client.post(
        f"/proposals/{proposal['proposal_id']}/approve",
        json={"option_id": option["option_id"]},
    )

    assert approval.status_code == 409
    assert (
        approval.json()["detail"]["status"]
        == "conflict_or_invalid"
    )


def test_manual_scheduling_uses_new_preferences(client):
    payload = default_preferences()
    payload["day_start"] = "10:00"
    payload["day_end"] = "16:00"

    assert client.put(
        "/preferences", json=payload
    ).status_code == 200

    tomorrow = (
        date.today() + timedelta(days=1)
    ).isoformat()

    result = client.post(
        "/schedules",
        json={
            "title": "Aktivitas pagi",
            "event_date": tomorrow,
            "start_time": "08:00",
            "end_time": "09:00",
            "category": "fixed",
        },
    )

    assert result.status_code == 422
