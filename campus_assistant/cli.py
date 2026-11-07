import argparse
import getpass
import json
import sys
from pathlib import Path
from .config import Config, ROOT
from .db import Database
from .errors import DomainError
from .documents import build_index, pdf_source
from .events import configure_source, import_records, read_fixture, refresh_source
from .calendars import upload_calendar
from .privacy import consume_pairing


def demo(db):
    documents = json.loads((ROOT / "data/demo/documents.json").read_text(encoding="utf-8"))
    index = build_index(db, documents)
    configure_source(db, "demo", "Fictional Demo College events", "fixture://demo/events")
    report = import_records(db, "demo", read_fixture(ROOT / "data/demo/events.json"))
    return {"index": index, "events": report, "notice": "Fictional data. Set CAMPUS_NOW=2026-10-26T12:00:00-04:00 for the fixed walkthrough."}


def handoff_events(db, changed=False):
    configure_source(db, "handoff", "Fictional Robotics Club", "fixture://demo/handoff")
    records = read_fixture(ROOT / "data/demo/handoff-events.json")
    if changed:
        records = [dict(records[0], start="2026-10-27T14:15:00-04:00", end="2026-10-27T15:15:00-04:00")]
    return import_records(db, "handoff", records)


def main():
    parser = argparse.ArgumentParser(description="CampusScout local administration")
    parser.add_argument("--data-dir", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="Idempotent demo import; restores source contents, preserves private plans")
    sub.add_parser("demo-handoff", help="Import base demo plus two fictional robotics workshops")
    sub.add_parser("demo-reset", help="Reset ONLY a marked demo workspace, including its private sessions")
    sub.add_parser("init", help="Apply local SQLite migrations")
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=5555)
    index = sub.add_parser("index")
    index.add_argument("--manifest", type=Path)
    index.add_argument("--pdf", type=Path)
    index.add_argument("--title")
    index.add_argument("--url")
    index.add_argument("--category", default="general")
    index.add_argument("--backend", choices=["demo", "mpnet"], default="demo")
    source = sub.add_parser("source")
    source.add_argument("id")
    source.add_argument("url")
    source.add_argument("--title", default="Configured source")
    source.add_argument("--kind", choices=["json", "csv", "ics"], default="ics")
    source.add_argument("--allow-local-fixture", action="store_true", help="Explicit loopback-only HTTP fixture exemption")
    fixture = sub.add_parser("import-events")
    fixture.add_argument("source_id")
    fixture.add_argument("path", type=Path)
    refresh = sub.add_parser("refresh")
    refresh.add_argument("source_id")
    sub.add_parser("profile", help="Create a separate private MCP profile")
    sub.add_parser("pair", help="Consume a one-use code from My availability; prompts privately")
    availability = sub.add_parser("import-calendar")
    availability.add_argument("profile")
    availability.add_argument("path", type=Path)
    availability.add_argument("--start", required=True)
    availability.add_argument("--end", required=True)
    availability.add_argument("--timezone", required=True)
    change = sub.add_parser("demo-change", help="Move a fixture into a class conflict to demonstrate revalidation")
    change.add_argument("--workshop", action="store_true", help="Move the robotics workshop instead of the interview lab")
    fixture_server = sub.add_parser("fixture-server", help="Serve the checked-in demo ICS over localhost")
    fixture_server.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    config = Config()
    if args.data_dir:
        config.data_dir = args.data_dir.resolve()
    try:
        if args.command == "fixture-server":
            from functools import partial
            from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
            handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT / "data/demo"))
            ThreadingHTTPServer(("127.0.0.1", args.port), handler).serve_forever()
            return
        if args.command == "demo-reset":
            marker = config.data_dir / ".demo-workspace"
            database_path = config.data_dir / "campus.sqlite3"
            if database_path.exists() and not marker.exists():
                raise DomainError("invalid_input", "Refusing to reset an unmarked workspace. Use a new --data-dir for a disposable demo.")
            db = Database(config)
            with db.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                for table in ("plan_items", "plans", "busy_intervals", "calendars", "pairings", "web_sessions", "profiles", "event_revisions", "events", "event_sources", "active_index", "document_chunks", "document_sources", "document_revisions"):
                    conn.execute(f"DELETE FROM {table}")
            marker.write_text("Disposable demo workspace. Reset explicitly deletes local private records.\n", encoding="utf-8")
            result = demo(db)
        else:
            db = Database(config)
            if args.command == "serve":
                from .web import create_app
                create_app(config).run(host="127.0.0.1", port=args.port, debug=False)
                return
            if args.command == "demo-handoff":
                result = {"demo": demo(db), "handoff": handoff_events(db)}
            elif args.command == "demo":
                result = demo(db)
            elif args.command == "init":
                result = {"status": "ok", "database": str(db.path)}
            elif args.command == "index":
                if args.pdf:
                    if not args.title or not args.url:
                        raise DomainError("invalid_input", "--pdf requires --title and --url for evidence")
                    sources = [pdf_source(args.pdf, args.title, args.url, args.category)]
                elif args.manifest:
                    sources = json.loads(args.manifest.read_text(encoding="utf-8"))
                else:
                    raise DomainError("invalid_input", "Provide --pdf or --manifest; indexing replaces the full active corpus")
                result = build_index(db, sources, args.backend)
            elif args.command == "source":
                configure_source(db, args.id, args.title, args.url, args.kind, args.allow_local_fixture)
                result = {"status": "ok", "source": args.id}
            elif args.command == "import-events":
                result = import_records(db, args.source_id, read_fixture(args.path))
            elif args.command == "refresh":
                result = refresh_source(db, args.source_id)
            elif args.command == "profile":
                result = {"profile": db.create_profile(), "notice": "Private local capability. Store in CAMPUS_PROFILE; do not commit."}
            elif args.command == "pair":
                result = {"profile": consume_pairing(db, getpass.getpass("One-use pairing code: "))}
            elif args.command == "import-calendar":
                result = upload_calendar(db, args.profile, args.path.read_bytes(), args.start, args.end, args.timezone)
            elif args.workshop:
                result = handoff_events(db, changed=True)
            else:
                records = read_fixture(ROOT / "data/demo/events.json")
                event = dict(records[1], start="2026-10-27T14:15:00-04:00", end="2026-10-27T15:15:00-04:00")
                result = import_records(db, "demo", [event])
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (DomainError, ValueError, OSError) as exc:
        result = exc.result() if isinstance(exc, DomainError) else DomainError("invalid_input", str(exc)).result()
        print(json.dumps(result), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
