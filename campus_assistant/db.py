import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, config):
        self.config = config
        config.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = config.data_dir / "campus.sqlite3"
        with self.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)")
            for path in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
                if not conn.execute("SELECT 1 FROM schema_migrations WHERE version=?", (path.name,)).fetchone():
                    conn.executescript("BEGIN IMMEDIATE;\n" + path.read_text(encoding="utf-8"))
                    conn.execute("INSERT INTO schema_migrations VALUES (?)", (path.name,))

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_profile(self, kind="local"):
        ref = secrets.token_urlsafe(24)
        with self.connect() as conn:
            conn.execute("INSERT INTO profiles VALUES (?,?)", (ref, kind))
        return ref

    def require_profile(self, ref):
        from .errors import DomainError
        with self.connect() as conn:
            if not conn.execute("SELECT 1 FROM profiles WHERE id=?", (ref,)).fetchone():
                raise DomainError("not_found", "Local profile not found; create or pair a profile first.")
        return ref
