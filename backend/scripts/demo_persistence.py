
from datetime import date, timedelta

from sqlalchemy import select

from database import make_engine, init_database
from models import ScheduleEventDB
from approval_service import ApprovalService
from scheduling_engine import (
    SchedulingEngine,
    ScheduleRequest,
    UserPreferences,
)
from target_resolution import ScheduleEvent


def main():
    # Separate demo DB so regular data remains untouched.
    engine = make_engine("sqlite:///scheduler_demo.db")
    init_database(engine)

    service = ApprovalService(engine)
    tomorrow = date.today() + timedelta(days=1)

    # First run: create demo events if absent.
    with service.Session.begin() as session:
        existing = session.scalar(
            select(ScheduleEventDB).where(
                ScheduleEventDB.title == "Kuliah DEMO",
                ScheduleEventDB.event_date == tomorrow,
            )
        )

        if existing is None:
            session.add_all([
                ScheduleEventDB(
                    title="Kuliah DEMO",
                    event_date=tomorrow,
                    start_time="08:00",
                    end_time="12:00",
                    category="fixed",
                ),
                ScheduleEventDB(
                    title="Istirahat DEMO",
                    event_date=tomorrow,
                    start_time="12:00",
                    end_time="13:00",
                    category="break",
                ),
            ])

    with service.Session() as session:
        rows = session.scalars(
            select(ScheduleEventDB).where(
                ScheduleEventDB.event_date == tomorrow
            )
        ).all()

        events = [
            ScheduleEvent(
                r.id, r.title, r.event_date,
                r.start_time, r.end_time, r.category
            )
            for r in rows
        ]

    request = ScheduleRequest(
        title="Belajar Python DEMO",
        event_date=tomorrow,
        duration_minutes=120,
        preferred_period="afternoon",
    )

    recommendations = service.scheduler.recommend(
        request, events, limit=3
    )

    if not recommendations:
        print("No available slots")
        return

    ai_result = {
        "status": "pending_approval",
        "command": {
            "action": "create",
            "task_name": request.title,
            "duration_minutes": request.duration_minutes,
            "date_reference": "tomorrow",
            "preferred_period": "afternoon",
        },
        "suggestions": [
            {
                "title": s.title,
                "date": s.date,
                "start": s.start,
                "end": s.end,
                "score": s.score,
            }
            for s in recommendations
        ],
    }

    proposal = service.save_proposal(
        "Belajar Python DEMO selama 2 jam besok siang",
        ai_result,
    )

    print("PROPOSAL SAVED:", proposal)

    selected = proposal["options"][0]

    result = service.approve(
        proposal_id=proposal["proposal_id"],
        option_id=selected["option_id"],
    )

    print("APPROVAL RESULT:", result)

    # Attempt the same approval again.
    second = service.approve(
        proposal_id=proposal["proposal_id"],
        option_id=selected["option_id"],
    )

    print("SECOND APPROVAL:", second)


if __name__ == "__main__":
    main()
