from datetime import datetime, timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware datetime required")
    return value.astimezone(timezone.utc)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Search(Contract):
    query: str = Field(min_length=2, max_length=1000)
    category: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=3, ge=1, le=10)


class EventInput(Contract):
    source_event_id: str = Field(min_length=1, max_length=300)
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=10000)
    source_url: str = Field(max_length=2000)
    organizer: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=500)
    timezone: str = "America/New_York"
    start: datetime
    end: datetime
    status: Literal["active", "cancelled"] = "active"
    categories: list[Annotated[str, Field(max_length=100)]] = Field(default_factory=list, max_length=20)
    cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    registration_deadline: datetime | None = None
    free_food: Literal["confirmed", "absent", "unknown"] = "unknown"
    dietary: Literal["confirmed", "absent", "unknown"] = "unknown"

    @field_validator("source_url")
    @classmethod
    def source_link(cls, value):
        from urllib.parse import urlsplit
        if urlsplit(value).scheme not in ("https", "http", "fixture"):
            raise ValueError("Source must be an http(s) or fixture URL")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        ZoneInfo(value)
        return value

    @field_validator("start", "end", "registration_deadline")
    @classmethod
    def aware(cls, value):
        return utc(value) if value is not None else None

    @model_validator(mode="after")
    def duration(self):
        if self.end <= self.start:
            raise ValueError("Event end must follow start")
        return self


class EventQuery(Contract):
    start: datetime
    end: datetime
    interests: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(default_factory=list, max_length=20)
    max_cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    free_food: bool = False
    buffer_minutes: int = Field(default=0, ge=0, le=120)
    calendar_ref: str | None = Field(default=None, min_length=1, max_length=100)
    limit: int = Field(default=50, ge=1, le=100)

    @field_validator("start", "end")
    @classmethod
    def aware(cls, value):
        return utc(value)

    @model_validator(mode="after")
    def horizon(self):
        from datetime import timedelta
        if not self.start < self.end <= self.start + timedelta(days=30):
            raise ValueError("Planning horizon must be positive and at most 30 days")
        return self


class Selection(Contract):
    event_id: str = Field(min_length=1, max_length=100)
    revision: int = Field(ge=1)


class ExportRequest(Contract):
    selections: list[Selection] = Field(min_length=1, max_length=5)
    query: EventQuery

    @model_validator(mode="after")
    def unique(self):
        if len({s.event_id for s in self.selections}) != len(self.selections):
            raise ValueError("Duplicate selected event")
        return self


class SavePlan(ExportRequest):
    pass


class SavePlanningContext(Contract):
    summary: str = Field(min_length=1, max_length=1000)
    preferences: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(max_length=20)
    expected_revision: int = Field(ge=0)
    reviewed: Literal[True]
    plan_ref: str | None = Field(default=None, min_length=1, max_length=100)
    selection: ExportRequest | None = None

    @model_validator(mode="after")
    def one_plan_source(self):
        if (self.plan_ref is None) == (self.selection is None):
            raise ValueError("Supply one owned plan_ref or a reviewed selection")
        return self


class ContextRevision(Contract):
    expected_revision: int = Field(ge=0)


class PlanningContext(Contract):
    summary: str
    preferences: list[str]
    plan_ref: str
    selections: list[Selection]
    updated_at: str


class ContextOutput(Contract):
    status: Literal["ok"]
    revision: int
    context: PlanningContext | None


class ToolResult(Contract):
    status: str
    data: dict | None = None
    error: dict | None = None
