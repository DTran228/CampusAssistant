import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("CAMPUS_DATA_DIR", "runtime")).resolve())
    campus_name: str = field(default_factory=lambda: os.getenv("CAMPUS_NAME", "Fictional Demo College"))
    timezone: str = field(default_factory=lambda: os.getenv("CAMPUS_TIMEZONE", "America/New_York"))
    fixed_now: str | None = field(default_factory=lambda: os.getenv("CAMPUS_NOW") or None)
    profile: str | None = field(default_factory=lambda: os.getenv("CAMPUS_PROFILE") or None)
    stale_hours: int = 48
    demo_mode: bool = field(default_factory=lambda: os.getenv("CAMPUS_DEMO", "1") == "1")

    def __post_init__(self):
        self.data_dir = Path(self.data_dir).resolve()
        ZoneInfo(self.timezone)

    def now(self):
        value = datetime.fromisoformat(self.fixed_now) if self.fixed_now else datetime.now(timezone.utc)
        if value.tzinfo is None:
            raise ValueError("CAMPUS_NOW must have a timezone")
        return value.astimezone(timezone.utc)
