"""Bounded RFC5545 subset with explicit rejection instead of silent availability."""
import secrets
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dateutil.rrule import rrulestr
from dateutil.tz import datetime_exists, datetime_ambiguous
from icalendar import Calendar, Event
from .errors import DomainError
from .schemas import utc

MAX_BYTES = 1024 * 1024
MAX_OCCURRENCES = 2000


def local_datetime(value, selected_timezone):
    zone = ZoneInfo(selected_timezone) if selected_timezone else None
    if not isinstance(value, (date, datetime)):
        raise ValueError("Invalid calendar date")
    if not isinstance(value, datetime):
        if zone is None:
            raise ValueError("Select timezone for all-day events")
        value = datetime.combine(value, time.min, zone)
    elif value.tzinfo is None:
        if zone is None:
            raise ValueError("Select timezone for floating times")
        value = value.replace(tzinfo=zone)
    if not datetime_exists(value):
        raise ValueError("Nonexistent local time at DST transition")
    if datetime_ambiguous(value):
        raise ValueError("Ambiguous local time; provide UTC for DST overlap")
    return value


def expand_calendar(raw, horizon_start, horizon_end, selected_timezone=None, busy_only=True):
    """Return UTC intervals and source components; no raw bytes persisted."""
    try:
        if len(raw) > MAX_BYTES or not raw.strip().startswith(b"BEGIN:VCALENDAR"):
            raise ValueError("Expected .ics calendar, at most 1 MiB")
        start, end = utc(horizon_start), utc(horizon_end)
        if not start < end <= start + timedelta(days=30):
            raise ValueError("Horizon must be positive and at most 30 days")
        if selected_timezone:
            ZoneInfo(selected_timezone)
        calendar = Calendar.from_ical(raw)
        if str(calendar.get("METHOD", "")).upper() not in ("", "PUBLISH"):
            raise ValueError("Only calendar snapshots (METHOD absent/PUBLISH) are supported")
        masters, overrides = {}, {}
        for component in calendar.walk("VEVENT"):
            if component.errors:
                raise ValueError("Malformed calendar component")
            for name in ("DTSTART", "DTEND", "RECURRENCE-ID", "EXDATE"):
                properties = component.get(name, [])
                for prop in properties if isinstance(properties, list) else [properties]:
                    if prop.params.get("TZID"):
                        ZoneInfo(str(prop.params["TZID"]))
            uid = str(component.get("UID", ""))
            if not uid:
                raise ValueError("Each calendar event needs UID")
            rid = component.get("RECURRENCE-ID")
            if rid:
                if rid.params.get("RANGE"):
                    raise ValueError("RECURRENCE-ID RANGE unsupported")
                key = (uid, utc(local_datetime(rid.dt, selected_timezone)))
                if key in overrides:
                    raise ValueError("Duplicate recurrence override")
                overrides[key] = component
            else:
                if uid in masters:
                    raise ValueError("Duplicate UID master")
                masters[uid] = component
        if any(uid not in masters for uid, _ in overrides):
            raise ValueError("Recurrence override without master")
        result = []

        def append(component, occurrence_start, duration, identity):
            if str(component.get("STATUS", "")).upper() == "CANCELLED":
                return
            if busy_only and str(component.get("TRANSP", "OPAQUE")).upper() == "TRANSPARENT":
                return
            occurrence_end = occurrence_start + duration
            a, b = utc(occurrence_start), utc(occurrence_end)
            if b <= a:
                raise ValueError("Calendar end must follow start")
            if a < end and b > start:
                result.append({"start": a, "end": b, "component": component, "identity": identity})
                if len(result) > MAX_OCCURRENCES:
                    raise ValueError("Occurrence cap exceeded")

        def timing(component):
            prop = component.get("DTSTART")
            if not prop:
                raise ValueError("Missing DTSTART")
            first = local_datetime(prop.dt, selected_timezone)
            if component.get("DTEND") and component.get("DURATION"):
                raise ValueError("DTEND and DURATION are mutually exclusive")
            if component.get("DTEND"):
                last = local_datetime(component.decoded("DTEND"), selected_timezone)
                if isinstance(prop.dt, datetime) != isinstance(component.decoded("DTEND"), datetime):
                    raise ValueError("DTSTART and DTEND types must match")
                duration = last - first
            elif component.get("DURATION"):
                duration = component.decoded("DURATION")
            elif not isinstance(prop.dt, datetime):
                duration = timedelta(days=1)
            else:
                raise ValueError("Timed busy event needs DTEND or DURATION")
            if duration <= timedelta(0) or duration > timedelta(days=366):
                raise ValueError("Invalid or excessive calendar duration")
            return first, duration

        for uid, master in masters.items():
            if str(master.get("STATUS", "")).upper() == "CANCELLED":
                continue
            first, duration = timing(master)
            if master.get("RDATE") or master.get("EXRULE"):
                raise ValueError("RDATE/EXRULE unsupported; export expanded events")
            excluded = set()
            exdates = master.get("EXDATE", [])
            for exclusion in exdates if isinstance(exdates, list) else [exdates]:
                excluded.update(utc(local_datetime(item.dt, selected_timezone)) for item in exclusion.dts)
            rule = master.get("RRULE")
            if rule:
                supported = {"FREQ", "INTERVAL", "COUNT", "UNTIL", "BYDAY", "BYMONTHDAY", "BYMONTH", "WKST", "BYSETPOS"}
                if set(rule) - supported or str(rule.get("FREQ", [""])[0]) not in {"DAILY", "WEEKLY", "MONTHLY", "YEARLY"}:
                    raise ValueError("Unsupported recurrence; use daily/weekly/monthly/yearly")
                if first < start - timedelta(days=3660):
                    raise ValueError("Recurrence anchor over 10 years old; export recent calendar")
                occurrences = rrulestr(rule.to_ical().decode(), dtstart=first)
            else:
                occurrences = [first]
            for count, occurrence in enumerate(occurrences):
                if count >= 10000:
                    raise ValueError("Recurrence expansion work cap exceeded")
                if utc(occurrence) >= end:
                    break
                key = (uid, utc(occurrence))
                if key in overrides or key[1] in excluded:
                    continue
                # RFC5545 invalid recurrence wall times do not occur.
                if not datetime_exists(occurrence):
                    continue
                if datetime_ambiguous(occurrence):
                    raise ValueError("Ambiguous recurring time; provide expanded UTC occurrences")
                append(master, occurrence, duration, f"{uid}/{key[1].isoformat()}" if rule else uid)
        for (uid, rid), override in overrides.items():
            if str(override.get("STATUS", "")).upper() == "CANCELLED":
                continue
            first, duration = timing(override)
            append(override, first, duration, f"{uid}/{rid.isoformat()}")
        return sorted(result, key=lambda item: item["start"])
    except DomainError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError, ZoneInfoNotFoundError) as exc:
        raise DomainError("calendar_unsupported", str(exc)) from exc


def upload_calendar(db, profile, raw, start, end, selected_timezone):
    db.require_profile(profile)
    intervals = expand_calendar(raw, start, end, selected_timezone)
    ref = secrets.token_urlsafe(18)
    with db.connect() as conn:
        conn.execute("INSERT INTO calendars VALUES (?,?,?,?,?,?)", (ref, profile, selected_timezone, utc(start).isoformat(), utc(end).isoformat(), db.config.now().isoformat()))
        conn.executemany("INSERT INTO busy_intervals VALUES (?,?,?)", [(ref, i["start"].isoformat(), i["end"].isoformat()) for i in intervals])
    return {"calendar_ref": ref, "intervals": len(intervals), "horizon_start": utc(start).isoformat(), "horizon_end": utc(end).isoformat(), "notice": "Raw calendar and event titles discarded."}


def owned_calendar(conn, profile, ref, start, end):
    row = conn.execute("SELECT * FROM calendars WHERE id=? AND profile_id=?", (ref, profile)).fetchone()
    if not row:
        raise DomainError("not_found", "Calendar not found in this profile")
    if utc(start) < utc(row["horizon_start"]) or utc(end) > utc(row["horizon_end"]):
        raise DomainError("invalid_input", "Date range exceeds stored availability; upload that horizon first")
    return [(utc(r["start"]), utc(r["end"])) for r in conn.execute("SELECT start,end FROM busy_intervals WHERE calendar_id=?", (ref,))]


def export_ics(events, now):
    calendar = Calendar()
    calendar.add("prodid", "-//CampusScout//Local planner//EN")
    calendar.add("version", "2.0")
    calendar.add("method", "PUBLISH")
    for item in events:
        event = Event()
        event.add("uid", f"{item['id']}@campusscout.local")
        event.add("dtstamp", utc(now))
        event.add("sequence", item["revision"])
        event.add("dtstart", utc(item["start"]))
        event.add("dtend", utc(item["end"]))
        event.add("summary", item["title"])
        event.add("description", item["description"] + "\nSource: " + item["source_url"])
        event.add("url", item["source_url"])
        if item.get("location"):
            event.add("location", item["location"])
        calendar.add_component(event)
    return calendar.to_ical().decode("utf-8")
