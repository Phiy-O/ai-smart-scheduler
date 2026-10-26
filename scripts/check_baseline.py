
from sqlalchemy import create_engine, inspect

from database import Base
import models


engine = create_engine("sqlite:///scheduler.db")
inspector = inspect(engine)

expected = {
    name
    for name in Base.metadata.tables
}

actual = set(inspector.get_table_names())

print("Expected:", sorted(expected))
print("Actual:", sorted(actual))

missing = expected - actual

if missing:
    raise RuntimeError(
        f"Missing tables: {sorted(missing)}"
    )

for table in sorted(expected):
    expected_columns = {
        col.name for col in Base.metadata.tables[table].columns
    }
    actual_columns = {
        col["name"] for col in inspector.get_columns(table)
    }

    if expected_columns != actual_columns:
        raise RuntimeError(
            f"Column mismatch in {table}: "
            f"expected={sorted(expected_columns)}, "
            f"actual={sorted(actual_columns)}"
        )

    print(f"OK: {table}")

engine.dispose()
print("Baseline structural check passed")
