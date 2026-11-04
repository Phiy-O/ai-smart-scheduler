
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from modification_service import slot_matches_period

from app.main import create_app
from database import Base, make_engine
from models import ScheduleEventDB
from schedule_commands import (
    UpdateCommand,
    RescheduleCommand,
)


class FakeParser:
    def __init__(self, command):
        self.command = command

    def parse(self, instruction):
        return self.command


def make_case(tmp_path, command):
    db_url = f"sqlite:///{tmp_path / 'scheduler.db'}"
    engine = make_engine(db_url)

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        event = ScheduleEventDB(
            title="Belajar Python",
            event_date=date.today(),
            start_time="09:00",
            end_time="10:00",
            category="focus",
        )
        session.add(event)
        session.commit()
        event_id = event.id

    engine.dispose()

    app = create_app(
        database_url=db_url,
        parser=FakeParser(command),
    )

    return app, event_id


def test_ai_update_duration_end_to_end(tmp_path):
    command = UpdateCommand.model_validate({
        "action": "update",
        "target": {
            "task_name": "Belajar Python",
            "date_reference": "today",
        },
        "changes": {
            "duration_minutes": 90,
            "preferred_period": None,
        },
    })

    app, event_id = make_case(tmp_path, command)

    with TestClient(app) as client:
        response = client.post(
            "/ai/modifications",
            json={
                "instruction": (
                    "Ubah durasi Belajar Python "
                    "hari ini menjadi 90 menit"
                )
            },
        )

        assert response.status_code == 200, response.text

        proposal = response.json()
        assert proposal["status"] == "pending_approval"
        assert proposal["action"] == "update"
        assert proposal["after"]["end_time"] == "10:30"

        original = client.get(
            f"/schedules/{event_id}"
        ).json()
        assert original["end"] == "10:00"

        approved = client.post(
            "/modification-proposals/"
            f"{proposal['proposal_id']}/approve"
        )

        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"

        updated = client.get(
            f"/schedules/{event_id}"
        ).json()

        assert updated["id"] == event_id
        assert updated["start"] == "09:00"
        assert updated["end"] == "10:30"


def test_ai_update_approval_rejects_policy_violation(tmp_path):
    command = UpdateCommand.model_validate({
        "action": "update",
        "target": {
            "task_name": "Belajar Python",
            "date_reference": "today",
        },
        "changes": {
            "duration_minutes": 90,
            "preferred_period": None,
        },
    })

    app, event_id = make_case(tmp_path, command)

    with TestClient(app) as client:
        response = client.post(
            "/ai/modifications",
            json={
                "instruction": "Ubah durasi Belajar Python hari ini menjadi 90 menit",
            },
        )
        proposal = response.json()

        preferences = client.get("/preferences").json()
        preferences["max_focus_minutes"] = 60
        assert client.put("/preferences", json=preferences).status_code == 200

        approved = client.post(
            f"/modification-proposals/{proposal['proposal_id']}/approve"
        )

        assert approved.status_code == 409
        assert approved.json()["detail"]["status"] == "conflict_or_invalid"
        assert client.get(f"/schedules/{event_id}").json()["end"] == "10:00"


def test_ai_reschedule_date_end_to_end(tmp_path):
    command = RescheduleCommand.model_validate({
        "action": "reschedule",
        "target": {
            "task_name": "Belajar Python",
            "date_reference": "today",
        },
        "new_date_reference": "tomorrow",
        "new_period": None,
    })

    app, event_id = make_case(tmp_path, command)

    with TestClient(app) as client:
        response = client.post(
            "/ai/modifications",
            json={
                "instruction": (
                    "Pindahkan Belajar Python "
                    "dari hari ini ke besok"
                )
            },
        )

        assert response.status_code == 200, response.text

        proposal = response.json()
        assert proposal["status"] == "pending_approval"
        assert proposal["action"] == "reschedule"

        tomorrow = date.today() + timedelta(days=1)

        assert (
            proposal["after"]["event_date"]
            == tomorrow.isoformat()
        )

        # Before approval, the event stays today.
        original = client.get(
            f"/schedules/{event_id}"
        ).json()
        assert original["date"] == date.today().isoformat()

        approved = client.post(
            "/modification-proposals/"
            f"{proposal['proposal_id']}/approve"
        )

        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"

        updated = client.get(
            f"/schedules/{event_id}"
        ).json()

        assert updated["id"] == event_id
        assert updated["date"] == tomorrow.isoformat()
        assert updated["start"] == "09:00"
        assert updated["end"] == "10:00"


def test_ai_reschedule_period_end_to_end(tmp_path):
    command = RescheduleCommand.model_validate({
        "action": "reschedule",
        "target": {
            "task_name": "Belajar Python",
            "date_reference": "today",
        },
        "new_date_reference": None,
        "new_period": "afternoon",
    })

    app, event_id = make_case(tmp_path, command)

    with TestClient(app) as client:
        response = client.post(
            "/ai/modifications",
            json={
                "instruction": (
                    "Pindahkan Belajar Python "
                    "hari ini ke sore"
                )
            },
        )

        assert response.status_code == 200, response.text

        proposal = response.json()
        assert proposal["status"] == "pending_approval"

        before = proposal["before"]
        after = proposal["after"]

        assert before["id"] == after["id"] == event_id
        assert after["event_date"] == before["event_date"]

        # Slot must be in the afternoon period.
        assert slot_matches_period(
            after["start_time"],
            after["end_time"],
            "afternoon",
        )

        # No mutation before approval.
        original = client.get(
            f"/schedules/{event_id}"
        ).json()

        assert original["start"] == "09:00"
        assert original["end"] == "10:00"

        approved = client.post(
            "/modification-proposals/"
            f"{proposal['proposal_id']}/approve"
        )

        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"

        updated = client.get(
            f"/schedules/{event_id}"
        ).json()

        assert updated["id"] == event_id
        assert updated["start"] == after["start_time"]
        assert updated["end"] == after["end_time"]