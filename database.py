
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(database_url="sqlite:///scheduler.db"):
    engine = create_engine(
        database_url,
        connect_args={"timeout": 10},
    )

    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.close()

    return engine


def make_session_factory(engine):
    return sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )


def init_database(engine):
    import models  # Register ORM models
    Base.metadata.create_all(engine)
