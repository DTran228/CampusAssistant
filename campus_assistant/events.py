import csv
import hashlib
import http.client
import ipaddress
import io
import json
import logging
import socket
import ssl
import time
from datetime import timedelta
from urllib.parse import urljoin, urlsplit
from pydantic import ValidationError
from .calendars import expand_calendar
from .errors import DomainError
from .schemas import EventInput, utc

log = logging.getLogger(__name__)


def configure_source(db, source_id, title, url, kind="json", allow_local_fixture=False):
    parsed = urlsplit(url)
    if kind not in ("json", "csv", "ics") or (kind == "ics" and parsed.scheme not in ("http", "https")):
        raise DomainError("invalid_input", "Use a supported source format/URL")
    with db.connect() as conn:
        conn.execute("INSERT INTO event_sources(id,title,url,kind,allowed_host,allow_local_fixture) VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,url=excluded.url,kind=excluded.kind,allowed_host=excluded.allowed_host,allow_local_fixture=excluded.allow_local_fixture",
                     (source_id, title, url, kind, parsed.hostname, int(allow_local_fixture)))


def safe_fetch(source):
    """Pin the validated IP to the socket, preserving TLS hostname verification."""
    current = source["url"]
    deadline = time.monotonic() + 15
    for _ in range(4):
        parsed = urlsplit(current)
        if parsed.scheme not in ("https", "http") or parsed.hostname != source["allowed_host"] or parsed.username or parsed.password:
            raise DomainError("unavailable_source", "Feed redirect/host is not allowed")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = {a[4][0] for a in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)}
        if not addresses:
            raise DomainError("unavailable_source", "Feed has no address")
        for value in addresses:
            address = ipaddress.ip_address(value)
            allowed = address.is_loopback if source["allow_local_fixture"] else address.is_global
            if not allowed:
                raise DomainError("unavailable_source", "Private/local feed addresses are blocked")
        remaining = min(5, deadline - time.monotonic())
        if remaining <= 0:
            raise DomainError("unavailable_source", "Feed deadline exceeded")
        connection = http.client.HTTPConnection(parsed.hostname, port, timeout=remaining)
        try:
            connection.sock = socket.create_connection((sorted(addresses)[0], port), timeout=remaining)
            if parsed.scheme == "https":
                connection.sock = ssl.create_default_context().wrap_socket(connection.sock, server_hostname=parsed.hostname)
            connection.request("GET", (parsed.path or "/") + ("?" + parsed.query if parsed.query else ""), headers={"Accept": "text/calendar", "User-Agent": "CampusScout/0.1"})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                current = urljoin(current, response.getheader("Location", ""))
                continue
            if response.status != 200:
                raise DomainError("unavailable_source", f"Feed HTTP status {response.status}")
            payload = bytearray()
            while True:
                if time.monotonic() > deadline:
                    raise DomainError("unavailable_source", "Feed deadline exceeded")
                chunk = response.read(16384)
                if not chunk:
                    return bytes(payload)
                payload.extend(chunk)
                if len(payload) > 1024 * 1024:
                    raise DomainError("unavailable_source", "Feed exceeds 1 MiB")
        finally:
            connection.close()
    raise DomainError("unavailable_source", "Feed redirect limit exceeded")


def import_records(db, source_id, records, prior_errors=None):
    now = db.config.now().isoformat()
    report = {"status": "ok", "created": 0, "updated": 0, "unchanged": 0, "errors": list(prior_errors or [])}
    validated, seen = [], set()
    for number, record in enumerate(records, 1):
        try:
            item = EventInput.model_validate(record)
            if item.source_event_id in seen:
                raise ValueError("Duplicate source_event_id within import")
            seen.add(item.source_event_id)
            validated.append(item)
        except (ValidationError, ValueError) as exc:
            report["errors"].append({"record": number, "message": str(exc)[:500]})
    if not validated and (records or report["errors"]):
        report["status"] = "rejected"
        with db.connect() as conn:
            changed = conn.execute("UPDATE event_sources SET last_attempt=?,last_error=? WHERE id=?", (now, "No valid records; last snapshot retained", source_id)).rowcount
            if not changed:
                raise DomainError("not_found", "Configure source before importing")
        return report
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if not conn.execute("SELECT 1 FROM event_sources WHERE id=?", (source_id,)).fetchone():
            raise DomainError("not_found", "Configure source before importing")
        for item in validated:
            data = item.model_dump_json()
            existing = conn.execute("SELECT * FROM events WHERE source_id=? AND source_event_id=?", (source_id, item.source_event_id)).fetchone()
            if existing and existing["data"] == data:
                conn.execute("UPDATE events SET retrieved_at=? WHERE id=?", (now, existing["id"]))
                report["unchanged"] += 1
                continue
            event_id = hashlib.sha256(f"{source_id}:{item.source_event_id}".encode()).hexdigest()[:32]
            revision = existing["revision"] + 1 if existing else 1
            conn.execute("INSERT INTO events VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,data=excluded.data,retrieved_at=excluded.retrieved_at", (event_id, source_id, item.source_event_id, revision, data, now))
            conn.execute("INSERT INTO event_revisions VALUES (?,?,?,?)", (event_id, revision, data, now))
            report["updated" if existing else "created"] += 1
        report["status"] = "partial" if report["errors"] else "ok"
        conn.execute("UPDATE event_sources SET last_success=?,last_attempt=?,last_error=? WHERE id=?", (now, now, "Partial import; inspect report" if report["errors"] else None, source_id))
    return report


def read_fixture(path):
    from pathlib import Path
    path = Path(path)
    if path.stat().st_size > 1024 * 1024:
        raise DomainError("invalid_input", "Fixture exceeds 1 MiB")
    if path.suffix.lower() == ".json":
        records = json.loads(path.read_text(encoding="utf-8"))
    elif path.suffix.lower() == ".csv":
        records = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
        for row in records:
            row["categories"] = [s.strip() for s in row.get("categories", "").split(";") if s.strip()]
            for key in ("cost", "registration_deadline", "organizer", "location"):
                if not row.get(key):
                    row[key] = None
    else:
        raise DomainError("invalid_input", "Use JSON or CSV fixture")
    if not isinstance(records, list) or len(records) > 10000:
        raise DomainError("invalid_input", "Expected at most 10000 event records")
    return records


def refresh_source(db, source_id):
    with db.connect() as conn:
        source = conn.execute("SELECT * FROM event_sources WHERE id=?", (source_id,)).fetchone()
    if not source or source["kind"] != "ics":
        raise DomainError("not_found", "Configured ICS source not found")
    try:
        raw = safe_fetch(source)
        now = db.config.now()
        # A malformed VEVENT is reported individually. Recurrence groups stay together.
        from icalendar import Calendar
        calendar = Calendar.from_ical(raw)
        if not raw.strip().startswith(b"BEGIN:VCALENDAR"):
            raise ValueError("Not an ICS calendar")
        if str(calendar.get("METHOD", "")).upper() not in ("", "PUBLISH"):
            raise ValueError("Only snapshot feeds (METHOD absent/PUBLISH) supported")
        groups, errors, records = {}, [], []
        for component in calendar.walk("VEVENT"):
            groups.setdefault(str(component.get("UID", "")), []).append(component)
        for uid, components in groups.items():
            try:
                group = Calendar()
                group.add("version", "2.0")
                for component in components:
                    group.add_component(component)
                # Cancellation with a UID may omit DTSTART/DTEND; preserve existing fields.
                master = next((c for c in components if not c.get("RECURRENCE-ID")), None)
                if master is not None and str(master.get("STATUS", "")).upper() == "CANCELLED":
                    with db.connect() as conn:
                        previous = conn.execute("SELECT source_event_id,data FROM events WHERE source_id=?", (source_id,)).fetchall()
                    records.extend(dict(json.loads(r["data"]), status="cancelled") for r in previous if r["source_event_id"] == uid or r["source_event_id"].startswith(uid + "/"))
                    continue
                occurrences = expand_calendar(group.to_ical(), now, now + timedelta(days=30), db.config.timezone, busy_only=False)
                for occurrence in occurrences:
                    c = occurrence["component"]
                    date_value = c.decoded("DTSTART")
                    zone = str(c["DTSTART"].params.get("TZID") or getattr(getattr(date_value, "tzinfo", None), "key", "") or ("UTC" if getattr(date_value, "tzinfo", None) is not None and date_value.utcoffset() == timedelta(0) else db.config.timezone))
                    records.append({"source_event_id": occurrence["identity"], "title": str(c.get("SUMMARY", "Untitled event")), "description": str(c.get("DESCRIPTION", "")), "source_url": str(c.get("URL", source["url"])), "organizer": str(c["ORGANIZER"]) if c.get("ORGANIZER") else None, "location": str(c["LOCATION"]) if c.get("LOCATION") else None, "timezone": zone or "UTC", "start": occurrence["start"], "end": occurrence["end"]})
                # Explicit cancelled recurrence instances update previously imported occurrences.
                for c in components:
                    if c.get("RECURRENCE-ID") and str(c.get("STATUS", "")).upper() == "CANCELLED":
                        from .calendars import local_datetime
                        identity = f"{uid}/{utc(local_datetime(c.decoded('RECURRENCE-ID'), db.config.timezone)).isoformat()}"
                        with db.connect() as conn:
                            old = conn.execute("SELECT data FROM events WHERE source_id=? AND source_event_id=?", (source_id, identity)).fetchone()
                        if old:
                            records.append(dict(json.loads(old["data"]), status="cancelled"))
            except (DomainError, ValueError, TypeError, KeyError) as exc:
                errors.append({"uid": uid, "message": str(exc)[:300]})
        return import_records(db, source_id, records, errors)
    except (DomainError, OSError, ValueError, http.client.HTTPException) as exc:
        with db.connect() as conn:
            conn.execute("UPDATE event_sources SET last_attempt=?,last_error=? WHERE id=?", (db.config.now().isoformat(), "Refresh failed; last snapshot retained", source_id))
        log.warning("Source %s refresh failed (%s)", source_id, type(exc).__name__)
        raise DomainError("unavailable_source", "Refresh failed; last good events retained") from exc


def current_events(conn, config):
    output = []
    for row in conn.execute("SELECT e.*,s.last_error,s.last_success,s.title AS source_title FROM events e JOIN event_sources s ON s.id=e.source_id"):
        item = json.loads(row["data"])
        age = config.now() - utc(row["retrieved_at"])
        freshness = "refresh_failed" if row["last_error"] else "stale" if age.total_seconds() > config.stale_hours * 3600 else "fresh"
        item.update(id=row["id"], revision=row["revision"], retrieved_at=row["retrieved_at"], freshness=freshness, source_id=row["source_id"], source_title=row["source_title"], unknown_fields=[key for key in ("cost", "organizer", "location", "registration_deadline") if item.get(key) is None] + [key for key in ("free_food", "dietary") if item.get(key) == "unknown"])
        output.append(item)
    return output
