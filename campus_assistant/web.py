import hmac
import json
import secrets
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, g, jsonify, render_template, request, Response
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException
from .config import Config, ROOT
from .db import Database
from .errors import DomainError
from .schemas import EventQuery, ExportRequest, Search, SavePlanningContext, ContextRevision
from .answers import answer
from .planner import discover, save_plan, revalidate_plan, export_selection, export_plan
from .calendars import upload_calendar, local_datetime
from .privacy import create_pairing
from .planning_context import get_planning_context, save_planning_context, clear_planning_context


def parse_query(data, config):
    data = dict(data)
    if "start_date" in data:
        zone = data.pop("timezone", config.timezone)
        for key in ("start", "end"):
            data[key] = local_datetime(datetime.combine(datetime.fromisoformat(data.pop(key + "_date")).date(), time.min), zone)
    return EventQuery.model_validate(data)


def create_app(config=None):
    config = config or Config()
    app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))
    db = Database(config)
    app.config.update(DATABASE=db, MAX_CONTENT_LENGTH=1024 * 1024 + 16384, TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"])

    @app.before_request
    def session_boundary():
        if request.endpoint == "static":
            return
        ref = request.cookies.get("campus_session")
        with db.connect() as conn:
            row = conn.execute("SELECT * FROM web_sessions WHERE id=?", (ref,)).fetchone() if ref else None
            if row:
                g.session_ref, g.profile, g.csrf = row["id"], row["profile_id"], row["csrf"]
                g.new_session = False
            else:
                g.session_ref, g.profile, g.csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24), secrets.token_urlsafe(24)
                g.new_session = True
                conn.execute("INSERT INTO profiles VALUES (?,?)", (g.profile, "web"))
                conn.execute("INSERT INTO web_sessions VALUES (?,?,?)", (g.session_ref, g.profile, g.csrf))
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            csrf = request.headers.get("X-CSRF-Token", "")
            if not hmac.compare_digest(csrf, g.csrf):
                raise DomainError("invalid_input", "Missing or invalid CSRF token; refresh this page")
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/"):
                raise DomainError("invalid_input", "Cross-origin changes rejected")

    @app.after_request
    def response_boundary(response):
        if getattr(g, "new_session", False):
            response.set_cookie("campus_session", g.session_ref, httponly=True, samesite="Strict", secure=request.is_secure)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.errorhandler(DomainError)
    def domain_error(exc):
        code = 404 if exc.code == "not_found" else 409 if exc.code in ("stale_selection", "stale_context") else 503 if exc.code == "unavailable_source" else 400
        return jsonify(exc.result()), code

    @app.errorhandler(ValidationError)
    @app.errorhandler(ValueError)
    @app.errorhandler(KeyError)
    def invalid_input(exc):
        return jsonify(DomainError("invalid_input", "Invalid input. Check timezone, dates (max 30 days), numeric limits, and required fields.").result()), 400

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(DomainError("invalid_input", exc.description).result()), exc.code

    @app.errorhandler(Exception)
    def unexpected_error(exc):
        app.logger.error("Request failed (%s)", type(exc).__name__)
        return jsonify(DomainError("internal_error", "Request failed; see local server diagnostics.").result()), 500

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "local"}

    @app.get("/")
    @app.get("/ask")
    @app.get("/events")
    @app.get("/availability")
    @app.get("/plan")
    def home():
        view = request.path.strip("/") or "events"
        now = config.now().astimezone(ZoneInfo(config.timezone))
        return render_template("index.html", view=view, campus=config.campus_name, timezone=config.timezone,
                               start_date=now.date().isoformat(), end_date=(now + timedelta(days=7)).date().isoformat(),
                               csrf=g.csrf, fixed_now=config.fixed_now, demo_mode=config.demo_mode)

    @app.post("/ask")
    @app.post("/api/search")
    def search():
        return answer(db, Search.model_validate(request.get_json()))

    @app.post("/api/events")
    def events():
        return discover(db, g.profile, parse_query(request.get_json(), config))

    @app.post("/api/recommend")
    def recommend():
        return discover(db, g.profile, parse_query(request.get_json(), config), recommend=True)

    @app.get("/api/calendars")
    def calendars():
        with db.connect() as conn:
            rows = conn.execute("SELECT c.*,COUNT(b.calendar_id) AS intervals FROM calendars c LEFT JOIN busy_intervals b ON b.calendar_id=c.id WHERE profile_id=? GROUP BY c.id ORDER BY c.created_at DESC", (g.profile,)).fetchall()
        return {"calendars": [{k: r[k] for k in ("id", "timezone", "horizon_start", "horizon_end", "intervals")} for r in rows]}

    @app.post("/api/calendars")
    def upload():
        file = request.files.get("calendar")
        if not file or not file.filename.lower().endswith(".ics"):
            raise DomainError("invalid_input", "Choose a .ics file up to 1 MiB")
        query = parse_query({k: request.form[k] for k in ("start_date", "end_date", "timezone")}, config)
        return upload_calendar(db, g.profile, file.read(1024 * 1024 + 1), query.start, query.end, request.form["timezone"])

    @app.delete("/api/calendars/<ref>")
    def delete_calendar(ref):
        with db.connect() as conn:
            changed = conn.execute("DELETE FROM calendars WHERE id=? AND profile_id=?", (ref, g.profile)).rowcount
        if not changed:
            raise DomainError("not_found", "Calendar not found in this session")
        return {"status": "ok"}

    @app.post("/api/pair")
    def pair():
        return create_pairing(db, g.profile)

    @app.get("/api/plans")
    def plans():
        with db.connect() as conn:
            refs = [r[0] for r in conn.execute("SELECT id FROM plans WHERE profile_id=? ORDER BY created_at DESC", (g.profile,))]
        return {"plans": [revalidate_plan(db, g.profile, ref) for ref in refs]}

    @app.get("/api/planning-context")
    def context_get():
        return get_planning_context(db, g.profile)

    @app.post("/api/planning-context")
    def context_save():
        return save_planning_context(db, g.profile, SavePlanningContext.model_validate(request.get_json()))

    @app.delete("/api/planning-context")
    def context_clear():
        value = ContextRevision.model_validate(request.get_json())
        return clear_planning_context(db, g.profile, value.expected_revision)

    @app.post("/api/plans")
    def save():
        return save_plan(db, g.profile, ExportRequest.model_validate(request.get_json()))

    @app.get("/api/plans/<ref>")
    def revalidate(ref):
        return revalidate_plan(db, g.profile, ref)

    @app.delete("/api/plans/<ref>")
    def delete_plan(ref):
        with db.connect() as conn:
            changed = conn.execute("DELETE FROM plans WHERE id=? AND profile_id=?", (ref, g.profile)).rowcount
        if not changed:
            raise DomainError("not_found", "Plan not found in this session")
        return {"status": "ok"}

    @app.post("/api/export")
    def export():
        result = export_selection(db, g.profile, ExportRequest.model_validate(request.get_json()))
        return Response(result["ics"], mimetype="text/calendar", headers={"Content-Disposition": 'attachment; filename="campus-events.ics"'})

    @app.post("/api/plans/<ref>/export")
    def export_saved(ref):
        result = export_plan(db, g.profile, ref)
        return Response(result["ics"], mimetype="text/calendar", headers={"Content-Disposition": 'attachment; filename="campus-events.ics"'})

    return app
