import json
import secrets
from collections import Counter
from datetime import timedelta
from .calendars import owned_calendar, export_ics
from .errors import DomainError
from .events import current_events
from .schemas import EventQuery, ExportRequest, utc


def overlaps(start, end, other_start, other_end, buffer_minutes=0):
    allowance = timedelta(minutes=buffer_minutes)
    return start < other_end + allowance and end + allowance > other_start


def exclusion_reasons(event, query, busy, now):
    a, b = utc(event["start"]), utc(event["end"])
    reasons = []
    if a < query.start or b > query.end or a < now:
        reasons.append("outside_dates")
    if event["status"] != "active":
        reasons.append("cancelled")
    if query.max_cost is not None:
        if event["cost"] is None:
            reasons.append("unknown_cost")
        elif event["cost"] > query.max_cost:
            reasons.append("over_budget")
    if event["registration_deadline"] and utc(event["registration_deadline"]) <= now:
        reasons.append("registration_closed")
    if query.free_food and event["free_food"] != "confirmed":
        reasons.append("food_not_confirmed")
    if any(overlaps(a, b, x, y, query.buffer_minutes) for x, y in busy):
        reasons.append("schedule_conflict")
    return reasons


def ranked_events(conn, config, profile, query, check_calendar=True):
    busy = []
    if query.calendar_ref and check_calendar:
        busy = owned_calendar(conn, profile, query.calendar_ref, query.start, query.end)
    included, excluded = [], []
    for event in current_events(conn, config):
        reasons = exclusion_reasons(event, query, busy, config.now())
        if reasons:
            excluded.append({"event_id": event["id"], "title": event["title"], "reasons": reasons})
            continue
        text = (event["title"] + " " + event["description"] + " " + " ".join(event["categories"])).casefold()
        matches = sorted({interest for interest in query.interests if interest.casefold() in text})
        event["matched_interests"] = matches
        event["schedule_checked"] = bool(query.calendar_ref and check_calendar)
        event["explanation"] = f"Matched: {', '.join(matches) or 'no explicit interest match'}. " + ("No conflict within stored availability. " if event["schedule_checked"] else "Personal availability not checked. ") + f"Source: {event['freshness']}. Unknown: {', '.join(event['unknown_fields']) or 'none'}."
        included.append(event)
    included.sort(key=lambda e: (-len(e["matched_interests"]), e["start"], e["id"]))
    return included, excluded


def discover(db, profile, query: EventQuery, recommend=False):
    with db.connect() as conn:
        conn.execute("BEGIN")
        included, excluded = ranked_events(conn, db.config, profile, query, check_calendar=recommend)
    counts = Counter(reason for event in excluded for reason in event["reasons"])
    return {"status": "ok", "query": query.model_dump(mode="json"), "events": included[:5] if recommend else included[:query.limit],
            "feasible_count": len(included), "excluded": excluded, "excluded_counts": dict(counts),
            "relaxations": (["Widen dates within 30 days", "Review budget or food requirements", "Choose a smaller time allowance"] if not included else []),
            "notice": "Ranked by explicit interest substring matches, then start time and ID. Options may conflict with each other; selection is checked separately. Time allowance is not walking time."}


def validate_selection(conn, config, profile, request: ExportRequest, require_fresh=True):
    query = request.query
    busy = owned_calendar(conn, profile, query.calendar_ref, query.start, query.end) if query.calendar_ref else []
    events = {event["id"]: event for event in current_events(conn, config)}
    selected = []
    for selection in request.selections:
        event = events.get(selection.event_id)
        if not event:
            raise DomainError("not_found", "Selected event not found")
        if event["revision"] != selection.revision:
            raise DomainError("stale_selection", "Source changed. Review the current revision before saving/exporting.")
        reasons = exclusion_reasons(event, query, busy, config.now())
        if reasons:
            raise DomainError("stale_selection", "Selection no longer fits: " + ", ".join(reasons))
        if require_fresh and event["freshness"] != "fresh":
            raise DomainError("unavailable_source", "Refresh the source before exporting stale or partially refreshed selections")
        if any(overlaps(utc(event["start"]), utc(event["end"]), utc(other["start"]), utc(other["end"]), query.buffer_minutes) for other in selected):
            raise DomainError("invalid_input", "Selected events conflict with each other")
        selected.append(event)
    return selected


def store_plan(conn, config, profile, request: ExportRequest):
    """Validate and insert inside the caller's transaction (also used by context saves)."""
    plan_ref = secrets.token_urlsafe(18)
    validate_selection(conn, config, profile, request, require_fresh=False)
    conn.execute("INSERT INTO plans VALUES (?,?,?,?,?)", (plan_ref, profile, request.query.calendar_ref, request.query.model_dump_json(), config.now().isoformat()))
    conn.executemany("INSERT INTO plan_items VALUES (?,?,?)", [(plan_ref, s.event_id, s.revision) for s in request.selections])
    return plan_ref


def save_plan(db, profile, request: ExportRequest):
    db.require_profile(profile)
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        plan_ref = store_plan(conn, db.config, profile, request)
    return {"status": "ok", "plan_ref": plan_ref}


def load_plan(conn, profile, plan_ref):
    row = conn.execute("SELECT * FROM plans WHERE id=? AND profile_id=?", (plan_ref, profile)).fetchone()
    if not row:
        raise DomainError("not_found", "Plan not found in this profile")
    items = conn.execute("SELECT event_id,revision FROM plan_items WHERE plan_id=? ORDER BY event_id", (plan_ref,)).fetchall()
    return ExportRequest(selections=[dict(r) for r in items], query=EventQuery.model_validate_json(row["request"]))


def revalidate_plan(db, profile, plan_ref):
    with db.connect() as conn:
        conn.execute("BEGIN")
        request = load_plan(conn, profile, plan_ref)
        events = {e["id"]: e for e in current_events(conn, db.config)}
        changes, items = [], []
        try:
            busy = owned_calendar(conn, profile, request.query.calendar_ref, request.query.start, request.query.end) if request.query.calendar_ref else []
        except DomainError:
            busy = []
            changes.append({"reason": "availability_deleted_or_unavailable"})
        for selection in request.selections:
            event = events[selection.event_id]
            items.append(dict(event, saved_revision=selection.revision))
            if event["revision"] != selection.revision:
                old = conn.execute("SELECT data FROM event_revisions WHERE event_id=? AND revision=?", (event["id"], selection.revision)).fetchone()
                previous = json.loads(old["data"])
                changed_fields = [key for key in previous if previous[key] != event.get(key)]
                changes.append({"event_id": event["id"], "reason": "source_changed", "changed_fields": changed_fields, "old_revision": selection.revision, "current_revision": event["revision"],
                                "previous_start": previous["start"], "previous_end": previous["end"],
                                "current_start": event["start"], "current_end": event["end"],
                                "explanation": "The source changed since you saved this selection. Review the previous and current times; your saved selection is unchanged."})
            for reason in exclusion_reasons(event, request.query, busy, db.config.now()):
                change = {"event_id": event["id"], "reason": reason}
                if reason == "schedule_conflict":
                    change["explanation"] = f"The current time of {event['title']} overlaps your stored class availability, including a {request.query.buffer_minutes}-minute time allowance. Choose another option or review your availability; this event cannot be exported."
                changes.append(change)
            if event["freshness"] != "fresh":
                changes.append({"event_id": event["id"], "reason": "source_" + event["freshness"]})
        for i, event in enumerate(items):
            for other in items[:i]:
                if overlaps(utc(event["start"]), utc(event["end"]), utc(other["start"]), utc(other["end"]), request.query.buffer_minutes):
                    changes.append({"event_id": event["id"], "reason": "selected_events_conflict", "other_event_id": other["id"]})
        alternatives = []
        if not any(c["reason"] == "availability_deleted_or_unavailable" for c in changes):
            candidates, _ = ranked_events(conn, db.config, profile, request.query)
            retained = [e for e in items if e["revision"] == e["saved_revision"] and not exclusion_reasons(e, request.query, busy, db.config.now())]
            alternatives = [e for e in candidates if e["id"] not in {s.event_id for s in request.selections} and not any(overlaps(utc(e["start"]), utc(e["end"]), utc(other["start"]), utc(other["end"]), request.query.buffer_minutes) for other in retained)][:5]
    return {"status": "ok", "plan_ref": plan_ref, "valid": not changes, "changes": changes, "items": items, "alternatives": alternatives, "request": request.model_dump(mode="json"), "notice": "Alternatives are suggestions only; the saved selection was not replaced."}


def export_selection(db, profile, request: ExportRequest):
    with db.connect() as conn:
        # Serializes source refreshes and the last validation, including private interval changes.
        conn.execute("BEGIN IMMEDIATE")
        events = validate_selection(conn, db.config, profile, request)
        text = export_ics(events, db.config.now())
    return {"status": "ok", "filename": "campus-events.ics", "ics": text, "notice": "Import this file yourself. No calendar was modified and no attendance was registered."}


def export_plan(db, profile, plan_ref):
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        request = load_plan(conn, profile, plan_ref)
        events = validate_selection(conn, db.config, profile, request)
        text = export_ics(events, db.config.now())
    return {"status": "ok", "filename": "campus-events.ics", "ics": text}
