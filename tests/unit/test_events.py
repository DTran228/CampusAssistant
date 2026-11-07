import json
import pytest
from campus_assistant.config import ROOT
from campus_assistant.events import configure_source, import_records, read_fixture, current_events, safe_fetch
from campus_assistant.schemas import EventQuery
from campus_assistant.planner import discover
from campus_assistant.errors import DomainError


def seed(db):
    configure_source(db, "demo", "Fictional events", "fixture://events")
    records = read_fixture(ROOT / "data/demo/events.json")
    import_records(db, "demo", records)
    return records


def test_idempotency_cancellation_revision_and_missing_is_not_cancellation(db):
    records = seed(db)
    assert import_records(db, "demo", records)["unchanged"] == 6
    changed = dict(records[0], status="cancelled")
    assert import_records(db, "demo", [changed])["updated"] == 1
    with db.connect() as conn:
        events = current_events(conn, db.config)
    assert len(events) == 6
    event = next(e for e in events if e["source_event_id"] == "career-1")
    assert event["revision"] == 2 and event["status"] == "cancelled"
    assert next(e for e in events if e["source_event_id"] == "career-2")["status"] == "active"


def test_filter_dates_budget_food_and_bad_record_report(db):
    records = seed(db)
    report = import_records(db, "demo", [records[0], dict(records[1], end="2026-10-20T12:00:00Z")])
    assert report["status"] == "partial" and len(report["errors"]) == 1
    query = EventQuery(start="2026-10-26T16:00:00Z", end="2026-11-02T16:00:00Z", max_cost=0, free_food=True)
    found = discover(db, None, query)["events"]
    assert [e["source_event_id"] for e in found] == ["tech-1"]
    assert found[0]["dietary"] == "unknown"


def test_remote_private_feed_blocked():
    with pytest.raises(DomainError, match="blocked"):
        safe_fetch({"url": "http://127.0.0.1/feed", "allowed_host": "127.0.0.1", "allow_local_fixture": False})
