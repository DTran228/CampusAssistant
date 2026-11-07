import sqlite3
import pytest
from pydantic import ValidationError
from campus_assistant.db import Database
from campus_assistant.errors import DomainError
from campus_assistant.planner import discover, save_plan
from campus_assistant.planning_context import get_planning_context, save_planning_context, clear_planning_context
from campus_assistant.schemas import SavePlanningContext, ExportRequest
from tests.integration.test_planner import setup


def reviewed(db):
    profile, records, query = setup(db)
    event = discover(db, profile, query, True)["events"][0]
    selection = ExportRequest(query=query, selections=[{"event_id": event["id"], "revision": event["revision"]}])
    request = SavePlanningContext(summary="A reviewed workshop plan.", preferences=["career", "workshop"],
                                  expected_revision=0, reviewed=True, selection=selection)
    return profile, request


def test_context_ownership_clear_and_stale_writes(db):
    profile, request = reviewed(db)
    assert get_planning_context(db, profile) == {"status": "ok", "revision": 0, "context": None}
    saved = save_planning_context(db, profile, request)
    assert saved["revision"] == 1
    assert saved["context"]["selections"] == [s.model_dump() for s in request.selection.selections]
    assert "calendar_ref" not in saved["context"] and "query" not in saved["context"]
    other = db.create_profile()
    assert get_planning_context(db, other)["context"] is None
    stolen = request.model_copy(update={"selection": None, "plan_ref": saved["context"]["plan_ref"]})
    with pytest.raises(DomainError, match="this profile"):
        save_planning_context(db, other, stolen)
    with pytest.raises(DomainError) as error:
        save_planning_context(db, profile, request)
    assert error.value.code == "stale_context"
    cleared = clear_planning_context(db, profile, 1)
    assert cleared == {"status": "ok", "revision": 2, "context": None}
    with pytest.raises(DomainError):
        save_planning_context(db, profile, stolen.model_copy(update={"expected_revision": 1}))
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM calendars").fetchone()[0] == 1
        assert conn.execute("SELECT summary,preferences FROM planning_contexts").fetchone()[:] == ("", "[]")
    assert save_planning_context(db, profile, stolen.model_copy(update={"expected_revision": 2}))["revision"] == 3


def test_atomic_failure_preserves_context_and_does_not_orphan_plan(db):
    profile, request = reviewed(db)
    saved = save_planning_context(db, profile, request)
    with db.connect() as conn:
        conn.execute("CREATE TRIGGER fail_context BEFORE UPDATE ON planning_contexts BEGIN SELECT RAISE(ABORT, 'disk write failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        save_planning_context(db, profile, request.model_copy(update={"expected_revision": 1}))
    assert get_planning_context(db, profile) == saved
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0] == 1
    stale = request.model_copy(deep=True, update={"expected_revision": 1})
    stale.selection.selections[0].revision += 1
    with pytest.raises(DomainError) as error:
        save_planning_context(db, profile, stale)
    assert error.value.code == "stale_selection"
    assert get_planning_context(db, profile) == saved


def test_context_contract_is_bounded_and_requires_review(db):
    _, request = reviewed(db)
    body = request.model_dump(mode="json")
    for change in ({"reviewed": False}, {"summary": "x" * 1001}, {"preferences": ["x"] * 21},
                   {"plan_ref": "also-a-plan"}, {"selection": None}, {"profile": "untrusted"}):
        with pytest.raises(ValidationError):
            SavePlanningContext.model_validate(dict(body, **change))


def test_migration_preserves_populated_database_and_deleting_plan_clears_context(db):
    # Reconstruct the pre-handoff schema with an existing populated plan.
    with db.connect() as conn:
        conn.execute("DROP TRIGGER clear_deleted_plan_context")
        conn.execute("DROP TABLE planning_contexts")
        conn.execute("DELETE FROM schema_migrations WHERE version='002_planning_context.sql'")
    profile, request = reviewed(db)
    plan = save_plan(db, profile, request.selection)["plan_ref"]
    upgraded = Database(db.config)
    saved = save_planning_context(upgraded, profile, request.model_copy(update={"selection": None, "plan_ref": plan}))
    assert saved["context"]["plan_ref"] == plan
    with upgraded.connect() as conn:
        conn.execute("DELETE FROM plans WHERE id=? AND profile_id=?", (plan, profile))
    assert get_planning_context(upgraded, profile) == {"status": "ok", "revision": 2, "context": None}
