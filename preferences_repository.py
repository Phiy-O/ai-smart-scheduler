
from sqlalchemy import select, text

from database import make_session_factory
from models import UserPreferencesDB
from scheduling_engine import UserPreferences


class PreferencesRepository:
    def __init__(self, engine):
        self.Session = make_session_factory(engine)

    @staticmethod
    def to_domain(row):
        return UserPreferences(
            day_start=row.day_start,
            day_end=row.day_end,
            productive_periods=list(row.productive_periods),
            avoid_periods=list(row.avoid_periods),
            min_break_minutes=row.min_break_minutes,
            max_focus_minutes=row.max_focus_minutes,
        )

    def get(self) -> UserPreferences:
        with self.Session() as session:
            row = session.get(UserPreferencesDB, 1)

            if row is None:
                return UserPreferences()

            return self.to_domain(row)

    def save(self, payload) -> UserPreferences:
        data = payload.model_dump()

        with self.Session() as session:
            session.execute(text("BEGIN IMMEDIATE"))

            try:
                row = session.get(UserPreferencesDB, 1)

                if row is None:
                    row = UserPreferencesDB(id=1, **data)
                    session.add(row)
                else:
                    for key, value in data.items():
                        setattr(row, key, value)

                session.flush()
                result = self.to_domain(row)
                session.commit()

                return result
            except Exception:
                session.rollback()
                raise
