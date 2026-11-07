from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import pytest
from campus_assistant.config import ROOT
from campus_assistant.events import configure_source, refresh_source, current_events
from campus_assistant.errors import DomainError


def test_http_refresh_idempotent_failure_and_explicit_cancel(db):
    class Handler(BaseHTTPRequestHandler):
        payload = (ROOT / "data/demo/feed.ics").read_bytes()
        status = 200

        def do_GET(self):
            self.send_response(self.status)
            self.end_headers()
            self.wfile.write(self.payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        configure_source(db, "feed", "Local HTTP fixture", f"http://127.0.0.1:{server.server_port}/feed.ics", "ics", True)
        assert refresh_source(db, "feed")["created"] == 1
        assert refresh_source(db, "feed")["unchanged"] == 1
        Handler.status = 503
        with pytest.raises(DomainError):
            refresh_source(db, "feed")
        with db.connect() as conn:
            events = current_events(conn, db.config)
        assert len(events) == 1 and events[0]["freshness"] == "refresh_failed"
        Handler.status = 200
        Handler.payload = Handler.payload.replace(b"SUMMARY:", b"STATUS:CANCELLED\nSUMMARY:")
        assert refresh_source(db, "feed")["updated"] == 1
        with db.connect() as conn:
            assert current_events(conn, db.config)[0]["status"] == "cancelled"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
