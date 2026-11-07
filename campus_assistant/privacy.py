import hashlib
import secrets
from datetime import timedelta
from .errors import DomainError
from .schemas import utc


def create_pairing(db, profile):
    token = secrets.token_urlsafe(24)
    with db.connect() as conn:
        conn.execute("INSERT INTO pairings VALUES (?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), profile, (db.config.now() + timedelta(minutes=10)).isoformat()))
    return {"token": token, "expires_in_minutes": 10, "notice": "Local pairing grants this MCP profile access to your calendars and plans. Keep the token private."}


def consume_pairing(db, token):
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        key = hashlib.sha256(token.encode()).hexdigest()
        row = conn.execute("SELECT * FROM pairings WHERE token_hash=?", (key,)).fetchone()
        if not row or utc(row["expires_at"]) <= db.config.now():
            raise DomainError("not_found", "Pairing token invalid or expired")
        conn.execute("DELETE FROM pairings WHERE token_hash=?", (key,))
        return row["profile_id"]
