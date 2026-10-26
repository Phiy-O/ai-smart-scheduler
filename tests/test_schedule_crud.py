
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


TEST_DATE = "2030-05-10"
NEXT_DATE = "2030-05-11"


@pytest.fixture
def client(tmp_path):
    path = tmp_path / "crud_test.db"
    app = create_app(
        database_url=f"sqlite:///{path.as_posix()}",
    )

    with TestClient(app) as test_client:
        yield test_client


def create_event(
    client,
    title="Belajar Python",
    event_date=TEST_DATE,
    start="13:00",
    end="15:00",
    category="focus",
):
    return client.post(
        "/schedules",
        json={
            "title": title,
            "event_date": event_date,
            "start_time": start,
            "end_time": end,
            "category": category,
        },
    )


def test_get_schedule_by_id(client):
    created = create_event(client)
    assert created.status_code == 201

    event_id = created.json()["id"]
    response = client.get(f"/schedules/{event_id}")

    assert response.status_code == 200
    assert response.json()["title"] == "Belajar Python"


def test_update_title(client):
    created = create_event(client)
    event_id = created.json()["id"]

    response = client.patch(
        f"/schedules/{event_id}",
        json={"title": "Belajar AI"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Belajar AI"
    assert response.json()["start"] == "13:00"


def test_reschedule_event(client):
    created = create_event(client)
    event_id = created.json()["id"]

    response = client.patch(
        f"/schedules/{event_id}",
        json={
            "event_date": NEXT_DATE,
            "start_time": "14:00",
            "end_time": "16:00",
        },
    )

    assert response.status_code == 200
    assert response.json()["date"] == NEXT_DATE
    assert response.json()["start"] == "14:00"


def test_update_conflict_rolls_back(client):
    first = create_event(client)
    assert first.status_code == 201

    second = create_event(
        client,
        title="Meeting",
        start="16:00",
        end="17:00",
        category="fixed",
    )
    assert second.status_code == 201

    second_id = second.json()["id"]

    response = client.patch(
        f"/schedules/{second_id}",
        json={
            "start_time": "14:00",
            "end_time": "15:00",
        },
    )

    assert response.status_code == 409

    unchanged = client.get(
        f"/schedules/{second_id}"
    ).json()

    assert unchanged["start"] == "16:00"
    assert unchanged["end"] == "17:00"


def test_update_excludes_itself(client):
    created = create_event(client)
    event_id = created.json()["id"]

    response = client.patch(
        f"/schedules/{event_id}",
        json={"title": "Python Advanced"},
    )

    assert response.status_code == 200


def test_delete_event(client):
    created = create_event(client)
    event_id = created.json()["id"]

    response = client.delete(
        f"/schedules/{event_id}"
    )

    assert response.status_code == 204

    lookup = client.get(f"/schedules/{event_id}")
    assert lookup.status_code == 404


def test_delete_missing_event(client):
    response = client.delete("/schedules/999999")
    assert response.status_code == 404


def test_update_missing_event(client):
    response = client.patch(
        "/schedules/999999",
        json={"title": "Testing"},
    )

    assert response.status_code == 404


def test_reject_empty_update(client):
    created = create_event(client)
    event_id = created.json()["id"]

    response = client.patch(
        f"/schedules/{event_id}",
        json={},
    )

    assert response.status_code == 422


def test_reject_null_update(client):
    created = create_event(client)
    event_id = created.json()["id"]

    response = client.patch(
        f"/schedules/{event_id}",
        json={"start_time": None},
    )

    assert response.status_code == 422


def test_reject_unknown_field(client):
    created = create_event(client)
    event_id = created.json()["id"]

    response = client.patch(
        f"/schedules/{event_id}",
        json={"user_id": 999},
    )

    assert response.status_code == 422


def test_reject_invalid_time(client):
    created = create_event(client)
    event_id = created.json()["id"]

    response = client.patch(
        f"/schedules/{event_id}",
        json={
            "start_time": "16:00",
            "end_time": "15:00",
        },
    )

    assert response.status_code == 422


def test_update_to_other_date_checks_conflict(client):
    first = create_event(
        client,
        title="Jadwal tujuan",
        event_date=NEXT_DATE,
        start="14:00",
        end="16:00",
    )
    assert first.status_code == 201

    second = create_event(
        client,
        title="Aktivitas asal",
        event_date=TEST_DATE,
        start="13:00",
        end="15:00",
    )
    assert second.status_code == 201

    event_id = second.json()["id"]

    response = client.patch(
        f"/schedules/{event_id}",
        json={
            "event_date": NEXT_DATE,
            "start_time": "14:00",
            "end_time": "16:00",
        },
    )

    assert response.status_code == 409

    unchanged = client.get(
        f"/schedules/{event_id}"
    )

    assert unchanged.json()["date"] == TEST_DATE
