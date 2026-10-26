
from datetime import date

from sqlalchemy import select, text

from database import make_session_factory
from models import ScheduleEventDB
from scheduling_engine import SchedulingEngine, UserPreferences
from target_resolution import ScheduleEvent
from schedule_policy import EventInput, validate_event


class ScheduleRepository:
    def __init__(self, engine, preferences=None):
        self.Session = make_session_factory(engine)
        self.preferences = preferences or UserPreferences(
            day_start="08:00",
            day_end="20:00",
            productive_periods=["morning", "afternoon"],
            avoid_periods=["evening"],
            min_break_minutes=15,
            max_focus_minutes=120,
        )
        self.scheduler = SchedulingEngine(self.preferences)

    @staticmethod
    def to_domain(row):
        return ScheduleEvent(
            id=row.id,
            title=row.title,
            event_date=row.event_date,
            start_time=row.start_time,
            end_time=row.end_time,
            category=row.category,
        )

    def _events_for_date(self, session, event_date):
        rows = session.scalars(
            select(ScheduleEventDB).where(
                ScheduleEventDB.event_date == event_date
            )
        ).all()
        return [self.to_domain(row) for row in rows]

    def list_events(self, event_date: date):
        with self.Session() as session:
            events = self._events_for_date(session, event_date)
            return sorted(events, key=lambda e: e.start_time)

    def get_event(self, event_id: int):
        with self.Session() as session:
            row = session.get(ScheduleEventDB, event_id)
            return self.to_domain(row) if row else None

    def create_event(
        self,
        title: str,
        event_date: date,
        start_time: str,
        end_time: str,
        category: str = "fixed",
    ):
        candidate = EventInput(
            title=title,
            event_date=event_date,
            start_time=start_time,
            end_time=end_time,
            category=category,
        )

        with self.Session() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            try:
                existing = self._events_for_date(
                    session, event_date
                )
                validate_event(
                    candidate, existing, self.preferences
                )

                row = ScheduleEventDB(
                    title=title.strip(),
                    event_date=event_date,
                    start_time=start_time,
                    end_time=end_time,
                    category=category,
                )
                session.add(row)
                session.flush()

                result = self.to_domain(row)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise

    def update_event(self, event_id: int, changes: dict):
        allowed = {
            "title", "event_date",
            "start_time", "end_time", "category",
        }

        if not changes or not set(changes).issubset(allowed):
            raise ValueError("No valid changes provided")

        with self.Session() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            try:
                row = session.get(ScheduleEventDB, event_id)

                if row is None:
                    session.rollback()
                    return None

                # Merge partial input with current values.
                merged = {
                    "title": row.title,
                    "event_date": row.event_date,
                    "start_time": row.start_time,
                    "end_time": row.end_time,
                    "category": row.category,
                }
                merged.update(changes)

                candidate = EventInput(**merged)

                existing = self._events_for_date(
                    session, candidate.event_date
                )

                validate_event(
                    candidate,
                    existing,
                    self.preferences,
                    exclude_id=event_id,
                )

                for key, value in merged.items():
                    setattr(row, key, value)

                session.flush()
                result = self.to_domain(row)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise

    def delete_event(self, event_id: int) -> bool:
        with self.Session() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            try:
                row = session.get(ScheduleEventDB, event_id)

                if row is None:
                    session.rollback()
                    return False

                session.delete(row)
                session.commit()
                return True
            except Exception:
                session.rollback()
                raise
