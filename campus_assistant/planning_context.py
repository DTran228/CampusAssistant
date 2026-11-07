"""Small, explicitly approved handoff; never a chat transcript or a raw calendar."""
import json
from .errors import DomainError
from .planner import load_plan, store_plan


def read_context(conn, profile):
    row = conn.execute("SELECT * FROM planning_contexts WHERE profile_id=?", (profile,)).fetchone()
    result = {"status": "ok", "revision": row["revision"] if row else 0, "context": None}
    if row and row["plan_id"]:
        # Check ownership again, even though the stored link was checked when written.
        plan = load_plan(conn, profile, row["plan_id"])
        result["context"] = {"summary": row["summary"], "preferences": json.loads(row["preferences"]),
                             "plan_ref": row["plan_id"], "selections": [s.model_dump() for s in plan.selections],
                             "updated_at": row["updated_at"]}
    return result


def get_planning_context(db, profile):
    db.require_profile(profile)
    with db.connect() as conn:
        conn.execute("BEGIN")
        return read_context(conn, profile)


def check_revision(conn, profile, expected):
    row = conn.execute("SELECT revision FROM planning_contexts WHERE profile_id=?", (profile,)).fetchone()
    revision = row["revision"] if row else 0
    if revision != expected:
        raise DomainError("stale_context", "Shared context changed. Reload it and review before saving again.")
    return revision


def save_planning_context(db, profile, request):
    db.require_profile(profile)
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        revision = check_revision(conn, profile, request.expected_revision)
        if request.plan_ref:
            load_plan(conn, profile, request.plan_ref)
            plan_ref = request.plan_ref
        else:
            plan_ref = store_plan(conn, db.config, profile, request.selection)
        conn.execute("""INSERT INTO planning_contexts VALUES (?,?,?,?,?,?)
            ON CONFLICT(profile_id) DO UPDATE SET summary=excluded.summary,
            preferences=excluded.preferences, plan_id=excluded.plan_id,
            revision=excluded.revision, updated_at=excluded.updated_at""",
                     (profile, request.summary, json.dumps(request.preferences), plan_ref,
                      revision + 1, db.config.now().isoformat()))
        return read_context(conn, profile)


def clear_planning_context(db, profile, expected_revision):
    db.require_profile(profile)
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        revision = check_revision(conn, profile, expected_revision)
        conn.execute("""INSERT INTO planning_contexts VALUES (?,'','[]',NULL,?,?)
            ON CONFLICT(profile_id) DO UPDATE SET summary='', preferences='[]', plan_id=NULL,
            revision=excluded.revision, updated_at=excluded.updated_at""",
                     (profile, revision + 1, db.config.now().isoformat()))
        return read_context(conn, profile)
