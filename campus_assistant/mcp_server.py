"""Official MCP SDK v1.26 stdio transport, bound to one local profile."""
import asyncio
import json
import logging
import sys
from typing import Generic, Literal, TypeVar
from pydantic import BaseModel, Field, ValidationError
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from .config import Config
from .db import Database
from .errors import DomainError
from .schemas import Contract, Search, EventInput, EventQuery, ExportRequest, SavePlanningContext, ContextOutput
from .retrieval import search_docs
from .planner import discover, revalidate_plan, export_selection
from .planning_context import save_planning_context, get_planning_context


class PlanReference(Contract):
    plan_ref: str = Field(min_length=1, max_length=100)


class Evidence(Contract):
    id: str
    source_id: str
    title: str
    url: str
    category: str
    page: int = Field(ge=1)
    text: str
    content_hash: str
    evidence_id: str
    score: float


class SearchOutput(Contract):
    status: str
    excerpts: list[Evidence]
    index_revision: str
    backend: str
    indexed_at: str
    freshness: str
    notice: str


class EventView(EventInput):
    id: str
    revision: int
    retrieved_at: str
    freshness: str
    source_id: str
    source_title: str
    unknown_fields: list[str]
    matched_interests: list[str] = Field(default_factory=list)
    schedule_checked: bool = False
    explanation: str = ""
    saved_revision: int | None = None


class Exclusion(Contract):
    event_id: str
    title: str
    reasons: list[str]


class DiscoveryOutput(Contract):
    status: str
    query: EventQuery
    events: list[EventView]
    feasible_count: int
    excluded: list[Exclusion]
    excluded_counts: dict[str, int]
    relaxations: list[str]
    notice: str


class PlanOutput(Contract):
    status: str
    plan_ref: str
    valid: bool
    changes: list[dict]
    items: list[EventView]
    alternatives: list[EventView]
    request: ExportRequest
    notice: str


class CalendarOutput(Contract):
    status: str
    filename: str
    ics: str
    notice: str


class ErrorOutput(Contract):
    code: str
    message: str


T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    status: Literal["ok", "error"]
    data: T | None = None
    error: ErrorOutput | None = None


def build_server(db, profile):
    db.require_profile(profile)
    server = Server("CampusScout", version="0.1.0")
    contracts = {
        "search_campus_docs": (Search, SearchOutput, "Search trusted document excerpts with page evidence."),
        "find_campus_events": (EventQuery, DiscoveryOutput, "Discover current events. Personal availability is not checked."),
        "recommend_events": (EventQuery, DiscoveryOutput, "Rank up to five options against owned availability; no saving."),
        "revalidate_plan": (PlanReference, PlanOutput, "Check an owned plan for source changes and conflicts."),
        "export_event_calendar": (ExportRequest, CalendarOutput, "Export reviewed revisions; reject stale or conflicting selections."),
        "save_planning_context": (SavePlanningContext, ContextOutput, "Save only user-reviewed summary, preferences and owned plan or selection. Read context revision first."),
        "get_planning_context": (Contract, ContextOutput, "Resume this profile's approved context without an ID. Revalidate its plan before relying on saved times.")}

    @server.list_tools()
    async def list_tools():
        return [types.Tool(name=name, description=description, inputSchema=input_model.model_json_schema(), outputSchema=Envelope[output_model].model_json_schema()) for name, (input_model, output_model, description) in contracts.items()]

    # Pydantic performs the input validation here so malformed arguments receive typed errors.
    @server.call_tool(validate_input=False)
    async def call_tool(name, arguments):
        try:
            if name not in contracts:
                raise DomainError("not_found", "Unknown tool")
            input_model, output_model, _ = contracts[name]
            value = input_model.model_validate(arguments)
            if name == "search_campus_docs":
                data = search_docs(db, value)
            elif name == "find_campus_events":
                data = discover(db, profile, value)
            elif name == "recommend_events":
                data = discover(db, profile, value, recommend=True)
            elif name == "revalidate_plan":
                data = revalidate_plan(db, profile, value.plan_ref)
            elif name == "save_planning_context":
                data = save_planning_context(db, profile, value)
            elif name == "get_planning_context":
                data = get_planning_context(db, profile)
            else:
                data = export_selection(db, profile, value)
            return Envelope[output_model](status="ok", data=data).model_dump(mode="json")
        except ValidationError:
            error = DomainError("invalid_input", "Arguments do not match the bounded tool contract")
        except DomainError as exc:
            error = exc
        except Exception as exc:
            logging.error("MCP tool %s failed (%s)", name, type(exc).__name__)
            error = DomainError("unavailable_source", "Tool unavailable; inspect local configuration")
        payload = {"status": "error", "data": None, "error": {"code": error.code, "message": error.message}}
        return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(payload))], structuredContent=payload, isError=True)

    return server


async def run():
    config = Config()
    if not config.profile:
        raise DomainError("invalid_input", "Set CAMPUS_PROFILE to an explicitly created/paired local profile")
    db = Database(config)
    server = build_server(db, config.profile)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main():
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    try:
        asyncio.run(run())
    except DomainError as exc:
        logging.error("%s: %s", exc.code, exc.message)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
