import json
import pytest
from icalendar import Calendar
from campus_assistant.config import ROOT
from campus_assistant.events import configure_source, import_records, read_fixture
from campus_assistant.calendars import upload_calendar
from campus_assistant.planner import discover, save_plan, revalidate_plan, export_plan, export_selection
from campus_assistant.schemas import EventQuery, ExportRequest
from campus_assistant.errors import DomainError


def setup(db):
    profile = db.create_profile()
    records = read_fixture(ROOT / "data/demo/events.json")
    configure_source(db, "demo", "Fictional", "fixture://events")
    import_records(db, "demo", records)
    query = EventQuery(start="2026-10-26T16:00:00Z", end="2026-11-02T16:00:00Z", interests=["career"], max_cost=0)
    calendar = upload_calendar(db, profile, (ROOT / "data/demo/classes.ics").read_bytes(), query.start, query.end, "America/New_York")
    query.calendar_ref = calendar["calendar_ref"]
    return profile, records, query


def test_complete_recommend_save_revalidate_export_and_source_move(db):
    profile, records, query = setup(db)
    result = discover(db, profile, query, True)
    assert result["events"][0]["source_event_id"] == "career-2"
    assert result["excluded_counts"]["schedule_conflict"] == 1
    event = result["events"][0]
    request = ExportRequest(query=query, selections=[{"event_id": event["id"], "revision": event["revision"]}])
    ref = save_plan(db, profile, request)["plan_ref"]
    assert revalidate_plan(db, profile, ref)["valid"]
    exported = export_plan(db, profile, ref)
    parsed = Calendar.from_ical(exported["ics"])
    component = parsed.walk("VEVENT")[0]
    assert str(component["UID"]) == f"{event['id']}@campusscout.local"
    assert component.decoded("DTSTART").isoformat() == "2026-10-28T20:00:00+00:00"
    assert str(component["URL"]) == event["source_url"]
    changed = dict(records[1], start="2026-10-27T14:15:00-04:00", end="2026-10-27T15:15:00-04:00")
    import_records(db, "demo", [changed])
    check = revalidate_plan(db, profile, ref)
    assert not check["valid"]
    assert {c["reason"] for c in check["changes"]} >= {"source_changed", "schedule_conflict"}
    assert check["alternatives"]
    with pytest.raises(DomainError) as error:
        export_plan(db, profile, ref)
    assert error.value.code == "stale_selection"
    with pytest.raises(DomainError):
        revalidate_plan(db, db.create_profile(), ref)


def test_cancelled_and_conflicting_selection_and_stale_source(db):
    profile, records, query = setup(db)
    query.calendar_ref = None
    events = discover(db, profile, query, True)["events"]
    first = events[0]
    request = ExportRequest(query=query, selections=[{"event_id": first["id"], "revision": first["revision"]}])
    ref = save_plan(db, profile, request)["plan_ref"]
    old = next(r for r in records if r["source_event_id"] == first["source_event_id"])
    import_records(db, "demo", [dict(old, status="cancelled")])
    assert not revalidate_plan(db, profile, ref)["valid"]
    with pytest.raises(DomainError):
        export_selection(db, profile, request)
    import_records(db, "demo", [dict(records[2], start=records[1]["start"], end=records[1]["end"])])
    candidates = discover(db, profile, query, True)["events"]
    request = ExportRequest(query=query, selections=[{"event_id": e["id"], "revision": e["revision"]} for e in candidates])
    with pytest.raises(DomainError, match="each other"):
        export_selection(db, profile, request)


def test_export_rechecks_latest_revision_even_without_revalidation(db):
    profile, records, query = setup(db)
    event = discover(db, profile, query, True)["events"][0]
    request = ExportRequest(query=query, selections=[{"event_id": event["id"], "revision": event["revision"]}])
    import_records(db, "demo", [dict(records[1], location="Changed room")])
    with pytest.raises(DomainError) as error:
        export_selection(db, profile, request)
    assert error.value.code == "stale_selection"
