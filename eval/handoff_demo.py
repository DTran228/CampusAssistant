"""Offline A -> shutdown -> source refresh -> independent B, through real MCP stdio."""
import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys
import tempfile
from campus_assistant.calendars import upload_calendar
from campus_assistant.cli import handoff_events
from campus_assistant.config import Config, ROOT
from campus_assistant.db import Database
from campus_assistant.planning_context import clear_planning_context
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SUMMARY = "Remember my robotics workshop choice; recheck its time against my classes before export."
PREFERENCES = ["robotics", "workshop"]


@asynccontextmanager
async def client(db, profile):
    env = dict(os.environ, CAMPUS_DATA_DIR=str(db.config.data_dir), CAMPUS_PROFILE=profile, CAMPUS_NOW=db.config.fixed_now)
    params = StdioServerParameters(command=sys.executable, args=["-m", "campus_assistant.mcp_server"], env=env, cwd=str(ROOT))
    async with asyncio.timeout(40):
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


async def call(session, name, arguments, error=None):
    result = await session.call_tool(name, arguments)
    payload = result.structuredContent
    if error:
        assert result.isError and payload["error"]["code"] == error, payload
        return payload
    assert not result.isError and payload["status"] == "ok", payload
    return payload["data"]


async def exercise_handoff(db, approve, emit=print):
    handoff_events(db)
    profile, other = db.create_profile(), db.create_profile()
    query = {"start": "2026-10-26T16:00:00Z", "end": "2026-11-02T16:00:00Z", "interests": PREFERENCES, "max_cost": 0}
    query["calendar_ref"] = upload_calendar(db, profile, (ROOT / "data/demo/classes.ics").read_bytes(), query["start"], query["end"], "America/New_York")["calendar_ref"]
    async with client(db, profile) as a:
        empty = await call(a, "get_planning_context", {})
        assert empty["context"] is None and empty["revision"] == 0
        events = await call(a, "recommend_events", query)
        chosen = events["events"][0]
        assert chosen["source_event_id"] == "robotics-workshop" and chosen["schedule_checked"]
        selection = {"query": query, "selections": [{"event_id": chosen["id"], "revision": chosen["revision"]}]}
        preview = {"summary": SUMMARY, "preferences": PREFERENCES, "event": chosen["title"], "start": chosen["start"], "end": chosen["end"], "selections": selection["selections"]}
        emit("A preview: " + json.dumps(preview, ensure_ascii=False))
        if not approve(preview):
            raise RuntimeError("Student declined; no context saved")
        body = {"summary": SUMMARY, "preferences": PREFERENCES, "selection": selection, "reviewed": True, "expected_revision": 0}
        saved = await call(a, "save_planning_context", body)
        assert saved["context"]["summary"] == SUMMARY and saved["context"]["preferences"] == PREFERENCES
        assert saved["context"]["selections"] == selection["selections"]
        bad = dict(selection, selections=[{"event_id": chosen["id"], "revision": 999}])
        await call(a, "save_planning_context", dict(body, selection=bad, expected_revision=1), "stale_selection")
        assert await call(a, "get_planning_context", {}) == saved
        with db.connect() as conn:
            assert conn.execute("SELECT COUNT(*) FROM plans WHERE profile_id=?", (profile,)).fetchone()[0] == 1
    emit("A closed; its MCP server subprocess has exited.")
    handoff_events(db, changed=True)
    emit("Fixture source refreshed: workshop moved to Tuesday Oct 27, 14:15-15:15 America/New_York.")
    async with client(db, profile) as b:
        resumed = await call(b, "get_planning_context", {})  # No copied plan ID.
        assert resumed == saved
        plan_ref = resumed["context"]["plan_ref"]
        checked = await call(b, "revalidate_plan", {"plan_ref": plan_ref})
        reasons = {c["reason"] for c in checked["changes"]}
        assert not checked["valid"] and {"source_changed", "schedule_conflict"} <= reasons
        current = checked["items"][0]
        assert current["revision"] > chosen["revision"] and current["saved_revision"] == chosen["revision"]
        assert checked["request"]["selections"] == selection["selections"]
        moved = next(c for c in checked["changes"] if c["reason"] == "source_changed")
        conflict = next(c for c in checked["changes"] if c["reason"] == "schedule_conflict")
        assert moved["previous_start"] == chosen["start"] and conflict["explanation"]
        await call(b, "export_event_calendar", selection, "stale_selection")
        await call(b, "save_planning_context", body, "stale_context")
        assert await call(b, "get_planning_context", {}) == saved
        assert checked["alternatives"] and checked["alternatives"][0]["source_event_id"] == "robotics-alternative"
        alternative = checked["alternatives"][0]
        emit("B: " + conflict["explanation"])
        emit("B choice: keep the original for later review, or choose " + alternative["title"] + " at " + alternative["start"])
        # Even a source cancellation must retain the original choice and revision.
        from campus_assistant.events import import_records, read_fixture
        record = read_fixture(ROOT / "data/demo/handoff-events.json")[0]
        import_records(db, "handoff", [dict(record, status="cancelled")])
        cancelled = await call(b, "revalidate_plan", {"plan_ref": plan_ref})
        assert any(c["reason"] == "cancelled" for c in cancelled["changes"])
        assert await call(b, "get_planning_context", {}) == saved
    async with client(db, other) as c:
        assert (await call(c, "get_planning_context", {}))["context"] is None
        await call(c, "revalidate_plan", {"plan_ref": plan_ref}, "not_found")
        stolen = {"summary": "overwrite", "preferences": [], "plan_ref": plan_ref, "expected_revision": 0, "reviewed": True}
        await call(c, "save_planning_context", stolen, "not_found")
        await call(c, "save_planning_context", body, "not_found")
        await call(c, "get_planning_context", {"profile": profile}, "invalid_input")
    # The clear action itself is exposed in My plan; HTTP/CSRF is tested separately.
    assert clear_planning_context(db, profile, 1)["context"] is None
    async with client(db, profile) as after_clear:
        assert (await call(after_clear, "get_planning_context", {})) == {"status": "ok", "revision": 2, "context": None}
        await call(after_clear, "save_planning_context", body, "stale_context")
        assert (await call(after_clear, "revalidate_plan", {"plan_ref": plan_ref}))["request"]["selections"] == selection["selections"]
        # Only an explicitly approved new choice creates a new plan; the original survives.
        alternative_selection = {"query": query, "selections": [{"event_id": alternative["id"], "revision": alternative["revision"]}]}
        alternative_summary = "I chose the sensors lab after reviewing the original workshop conflict."
        preview = {"summary": alternative_summary, "preferences": PREFERENCES, "event": alternative["title"], "start": alternative["start"], "selections": alternative_selection["selections"]}
        emit("New choice preview: " + json.dumps(preview, ensure_ascii=False))
        if not approve(preview):
            raise RuntimeError("Student declined replacement; original plan remains, context stays cleared")
        replacement = await call(after_clear, "save_planning_context", {"summary": alternative_summary, "preferences": PREFERENCES, "selection": alternative_selection, "expected_revision": 2, "reviewed": True})
        assert replacement["context"]["plan_ref"] != plan_ref
        assert (await call(after_clear, "revalidate_plan", {"plan_ref": replacement["context"]["plan_ref"]}))["valid"]
        exported = await call(after_clear, "export_event_calendar", alternative_selection)
        assert "BEGIN:VCALENDAR" in exported["ics"]
    return {"status": "passed", "transport": "official Python MCP SDK stdio subprocess clients; no desktop host",
            "summary": SUMMARY, "preferences": PREFERENCES, "workshop": chosen["title"],
            "previous_start": chosen["start"], "current_start": current["start"],
            "saved_event_revision": chosen["revision"], "current_event_revision": current["revision"],
            "conflict_reasons": sorted(reasons), "conflict_explanation": conflict["explanation"],
            "alternatives": [e["title"] for e in checked["alternatives"]],
            "checks": {"independent_a_b": True, "exact_context_resumed": True, "failed_save_preserves_context": True,
                       "stale_write_denied": True, "foreign_read_write_denied": True, "cancelled_selection_preserved": True,
                       "clear_visible_to_fresh_client": True, "clear_preserves_plan_calendar": True,
                       "reviewed_alternative_exported": True},
            "user_impact": {"participants": 0, "time_savings": None}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve-fixture", action="store_true", help="Scripted fixture approval, not a real student study")
    parser.add_argument("--output", type=Path, default=ROOT / "eval/results/handoff.json")
    args = parser.parse_args()
    def approve(preview):
        return args.approve_fixture or input("Save these reviewed fields? Type yes: ").strip().lower() == "yes"
    (ROOT / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mcp-handoff-", dir=ROOT / "tmp") as directory:
        db = Database(Config(data_dir=Path(directory), fixed_now="2026-10-26T16:00:00Z"))
        report = asyncio.run(exercise_handoff(db, approve))
    from eval.run import provenance
    report["provenance"] = provenance()
    report["approval"] = "scripted fictional fixture" if args.approve_fixture else "interactive local demo; not a study"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
