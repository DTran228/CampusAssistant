import asyncio
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from icalendar import Calendar
from campus_assistant.config import ROOT
from campus_assistant.cli import demo
from campus_assistant.calendars import upload_calendar
from campus_assistant.planner import discover, save_plan
from campus_assistant.schemas import EventQuery, ExportRequest


def test_real_sdk_subprocess_workflow_and_cross_profile_denial(db):
    demo(db)
    profile = db.create_profile()
    other = db.create_profile()
    query = EventQuery(start="2026-10-26T16:00:00Z", end="2026-11-02T16:00:00Z", interests=["career"], max_cost=0)
    ref = upload_calendar(db, profile, (ROOT / "data/demo/classes.ics").read_bytes(), query.start, query.end, "America/New_York")["calendar_ref"]
    query.calendar_ref = ref
    expected = discover(db, profile, query, True)
    event = expected["events"][0]
    export = ExportRequest(query=query, selections=[{"event_id": event["id"], "revision": event["revision"]}])
    plan_ref = save_plan(db, profile, export)["plan_ref"]

    async def workflow(bound_profile):
        env = dict(os.environ, CAMPUS_DATA_DIR=str(db.config.data_dir), CAMPUS_PROFILE=bound_profile, CAMPUS_NOW=db.config.fixed_now)
        params = StdioServerParameters(command=sys.executable, args=["-m", "campus_assistant.mcp_server"], env=env, cwd=str(ROOT))
        async with asyncio.timeout(40):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    initialized = await session.initialize()
                    assert initialized.serverInfo.name == "CampusScout"
                    definitions = (await session.list_tools()).tools
                    assert {t.name for t in definitions} == {"search_campus_docs", "find_campus_events", "recommend_events", "revalidate_plan", "export_event_calendar", "save_planning_context", "get_planning_context"}
                    for tool in definitions:
                        assert tool.inputSchema["type"] == "object"
                        assert tool.outputSchema and "properties" in tool.outputSchema
                        assert "profile" not in tool.inputSchema.get("properties", {})
                    if bound_profile == other:
                        denied = await session.call_tool("recommend_events", query.model_dump(mode="json"))
                        assert denied.isError and denied.structuredContent["error"]["code"] == "not_found"
                        denied = await session.call_tool("revalidate_plan", {"plan_ref": plan_ref})
                        assert denied.isError and denied.structuredContent["error"]["code"] == "not_found"
                        return
                    bad = await session.call_tool("recommend_events", {"start": "floating", "end": "2026-11-02"})
                    assert bad.isError and bad.structuredContent["error"]["code"] == "invalid_input"
                    bad = await session.call_tool("search_campus_docs", {"query": "library", "limit": 500})
                    assert bad.isError
                    docs = await session.call_tool("search_campus_docs", {"query": "library hours", "limit": 3})
                    assert not docs.isError and docs.structuredContent["data"]["excerpts"][0]["page"] == 1
                    found = await session.call_tool("find_campus_events", query.model_dump(mode="json"))
                    assert not found.isError
                    result = await session.call_tool("recommend_events", query.model_dump(mode="json"))
                    assert not result.isError, result.content
                    assert [e["id"] for e in result.structuredContent["data"]["events"]] == [e["id"] for e in expected["events"]]
                    plan = await session.call_tool("revalidate_plan", {"plan_ref": plan_ref})
                    assert not plan.isError and plan.structuredContent["data"]["valid"]
                    output = await session.call_tool("export_event_calendar", export.model_dump(mode="json"))
                    assert not output.isError, output.content
                    assert len(Calendar.from_ical(output.structuredContent["data"]["ics"]).walk("VEVENT")) == 1
                    export.selections[0].revision += 1
                    stale = await session.call_tool("export_event_calendar", export.model_dump(mode="json"))
                    assert stale.isError and stale.structuredContent["error"]["code"] == "stale_selection"
    asyncio.run(workflow(profile))
    asyncio.run(workflow(other))


def test_independent_clients_resume_approved_context_and_recheck_moved_workshop(db):
    from eval.handoff_demo import exercise_handoff, SUMMARY, PREFERENCES
    previews = []
    def approve(preview):
        previews.append(preview)
        return True  # Explicit scripted fixture approval; not a human study.
    report = asyncio.run(exercise_handoff(db, approve, emit=lambda message: None))
    assert report["status"] == "passed" and all(report["checks"].values())
    assert report["summary"] == SUMMARY and report["preferences"] == PREFERENCES
    assert report["current_event_revision"] > report["saved_event_revision"]
    assert len(previews) == 2 and previews[0]["event"] != previews[1]["event"]
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM calendars").fetchone()[0] == 1
