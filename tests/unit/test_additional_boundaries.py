import json
from datetime import timedelta
import pytest
from campus_assistant.config import ROOT
from campus_assistant.events import configure_source, import_records, read_fixture, current_events, safe_fetch
from campus_assistant.documents import build_index
from campus_assistant.retrieval import search_docs
from campus_assistant.schemas import Search, EventQuery, ExportRequest
from campus_assistant.planner import discover, export_selection
from campus_assistant.errors import DomainError


def test_csv_json_parity_and_all_bad_records_preserve_last_good(db):
    json_rows = read_fixture(ROOT / "data/demo/events.json")
    csv_rows = read_fixture(ROOT / "data/demo/events.csv")
    configure_source(db, "demo", "Demo", "fixture://demo")
    import_records(db, "demo", json_rows)
    assert import_records(db, "demo", csv_rows)["unchanged"] == 6
    report = import_records(db, "demo", [{"title": "broken"}])
    assert report["status"] == "rejected" and report["errors"]
    with db.connect() as conn:
        events = current_events(conn, db.config)
    assert len(events) == 6 and all(e["freshness"] == "refresh_failed" for e in events)


def test_stale_source_blocks_export_and_refresh_recovers(db):
    configure_source(db, "demo", "Demo", "fixture://demo")
    rows = read_fixture(ROOT / "data/demo/events.json")
    import_records(db, "demo", rows)
    query = EventQuery(start="2026-10-26T16:00:00Z", end="2026-11-02T16:00:00Z")
    event = discover(db, None, query, True)["events"][0]
    request = ExportRequest(query=query, selections=[{"event_id": event["id"], "revision": event["revision"]}])
    with db.connect() as conn:
        conn.execute("UPDATE events SET retrieved_at=?", ((db.config.now() - timedelta(days=3)).isoformat(),))
    with pytest.raises(DomainError) as error:
        export_selection(db, None, request)
    assert error.value.code == "unavailable_source"
    import_records(db, "demo", rows)
    assert export_selection(db, None, request)["ics"].startswith("BEGIN:VCALENDAR")


def test_metadata_page_corruption_rejected_and_llm_failure_falls_back(db, monkeypatch):
    from campus_assistant import answers
    build_index(db, json.loads((ROOT / "data/demo/documents.json").read_text()))
    monkeypatch.setenv("CAMPUS_LLM_PATH", "missing-model.gguf")
    def failure():
        raise OSError("Model unavailable")
    monkeypatch.setattr(answers, "local_model", failure)
    result = answers.answer(db, Search(query="library hours"))
    assert result["generation"] == "unavailable" and result["excerpts"]
    path = next((db.config.data_dir / "indexes").glob("*.json"))
    chunks = json.loads(path.read_text())
    chunks[0]["page"] = 999
    path.write_text(json.dumps(chunks))
    with pytest.raises(DomainError):
        search_docs(db, Search(query="library"))


def test_redirect_revalidation_and_size_limits(monkeypatch):
    import campus_assistant.events as events
    class Socket:
        def close(self):
            pass
    class Response:
        status = 302
        def getheader(self, name, default=""):
            return "http://169.254.169.254/metadata"
    class Connection:
        def __init__(self, *args, **kwargs):
            pass
        def request(self, *args, **kwargs):
            pass
        def getresponse(self):
            return Response()
        def close(self):
            pass
    monkeypatch.setattr(events.socket, "getaddrinfo", lambda *a, **k: [(None, None, None, None, ("8.8.8.8", 80))])
    monkeypatch.setattr(events.socket, "create_connection", lambda *a, **k: Socket())
    monkeypatch.setattr(events.http.client, "HTTPConnection", Connection)
    with pytest.raises(DomainError, match="not allowed"):
        safe_fetch({"url": "http://public.example/feed", "allowed_host": "public.example", "allow_local_fixture": False})
    Response.status = 200
    Response.read = lambda self, size: b"x" * size
    with pytest.raises(DomainError, match="exceeds"):
        safe_fetch({"url": "http://public.example/feed", "allowed_host": "public.example", "allow_local_fixture": False})
