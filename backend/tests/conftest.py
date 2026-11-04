
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def migrated_database(tmp_path, monkeypatch):
    database_path = tmp_path / "scheduler_test.db"
    database_url = f"sqlite:///{database_path.as_posix()}"

    alembic_config = Config(
        str(PROJECT_ROOT / "alembic.ini")
    )

    alembic_config.set_main_option(
        "script_location",
        str(PROJECT_ROOT / "migrations"),
    )

    # migrations/env.py currently reads DATABASE_URL
    # directly from the environment.
    with monkeypatch.context() as patch:
        patch.setenv("DATABASE_URL", database_url)
        command.upgrade(alembic_config, "head")

    return database_url
