from campus_assistant.db import Database
from pathlib import Path
import campus_assistant


def test_migrations_repeat_and_profiles_are_private(db):
    Database(db.config)
    first, second = db.create_profile(), db.create_profile()
    assert first != second
    assert db.require_profile(first) == first
    with db.connect() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        expected = {p.name for p in (Path(campus_assistant.__file__).parent / "migrations").glob("*.sql")}
        applied = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
        assert applied == expected
