
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import create_app
from database import Base, make_engine
from models import ScheduleEventDB
from schedule_commands import DeleteCommand


class FakeDeleteParser:
    def parse(self, instruction):
        return DeleteCommand.model_validate({
            "action": "delete",
            "target": {
                "task_name": "Belajar Python",
                "date_reference": "tomorrow",
            },
        })


def test_ai_delete_requires_approval(tmp_path):
    db_path = tmp_path / "scheduler.db"
    database_url = f"sqlite:///{db_path}"

    engine = make_engine(database_url)
    Base.metadata.create_all(engine)

    tomorrow = date.today() + timedelta(days=1)

    with Session(engine) as session:
        event = ScheduleEventDB(
            title="Belajar Python",
            event_date=tomorrow,
            start_time="09:00",
            end_time="10:30",
            category="focus",
        )
        session.add(event)
        session.commit()
        event_id = event.id

    engine.dispose()

    app = create_app(
        database_url=database_url,
        parser=FakeDeleteParser(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/ai/modifications",
            json={
                "instruction":
                    "Hapus jadwal Belajar Python besok"
            },
        )

        assert response.status_code == 200, response.text

        proposal = response.json()
        assert proposal["status"] == "pending_approval"
        assert proposal["action"] == "delete"
        assert proposal["before"]["id"] == event_id
        assert proposal["after"] is None

        proposal_id = proposal["proposal_id"]

        # Preview must not delete anything.
        before_approval = client.get(
            f"/schedules/{event_id}"
        )
        assert before_approval.status_code == 200

        # Explicit confirmation.
        approved = client.post(
            f"/modification-proposals/{proposal_id}/approve"
        )

        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        # Real database effect.
        after_approval = client.get(
            f"/schedules/{event_id}"
        )
        assert after_approval.status_code == 404

        # Duplicate approval must not execute again.
        duplicate = client.post(
            f"/modification-proposals/{proposal_id}/approve"
        )
        assert duplicate.status_code == 409
