import io
import re
from campus_assistant.web import create_app
from campus_assistant.cli import demo
from campus_assistant.config import ROOT
from campus_assistant.events import import_records, read_fixture


def client(app):
    web = app.test_client()
    html = web.get("/").text
    csrf = re.search(r'name="csrf-token" content="([^"]+)"', html)[1]
    return web, {"X-CSRF-Token": csrf}


def test_four_views_search_upload_plan_export_delete_and_isolation(db):
    demo(db)
    app = create_app(db.config)
    one, headers = client(app)
    two, other_headers = client(app)
    for path in ("/ask", "/events", "/availability", "/plan"):
        response = one.get(path)
        assert response.status_code == 200
        assert "Content-Security-Policy" in response.headers
    assert one.post("/api/search", json={"query": "library hours"}).status_code == 400
    found = one.post("/api/search", json={"query": "library hours"}, headers=headers)
    assert found.status_code == 200 and found.json["excerpts"][0]["page"] == 1
    query = {"start_date": "2026-10-26", "end_date": "2026-11-02", "timezone": "America/New_York", "interests": ["career"], "max_cost": 0}
    upload = one.post("/api/calendars", data={"start_date": query["start_date"], "end_date": query["end_date"], "timezone": query["timezone"], "calendar": (io.BytesIO((ROOT / "data/demo/classes.ics").read_bytes()), "classes.ics")}, headers=headers)
    assert upload.status_code == 200
    ref = upload.json["calendar_ref"]
    query["calendar_ref"] = ref
    assert two.post("/api/recommend", json=query, headers=other_headers).status_code == 404
    found = one.post("/api/recommend", json=query, headers=headers)
    assert found.status_code == 200
    assert found.json["events"][0]["source_event_id"] == "career-2"
    event = found.json["events"][0]
    body = {"query": found.json["query"], "selections": [{"event_id": event["id"], "revision": event["revision"]}]}
    saved = one.post("/api/plans", json=body, headers=headers)
    assert saved.status_code == 200
    plan = saved.json["plan_ref"]
    assert one.get("/api/plans").json["plans"][0]["valid"]
    assert two.get(f"/api/plans/{plan}").status_code == 404
    assert two.delete(f"/api/calendars/{ref}", headers=other_headers).status_code == 404
    assert one.post(f"/api/plans/{plan}/export", headers=headers).mimetype == "text/calendar"
    records = read_fixture(ROOT / "data/demo/events.json")
    import_records(db, "demo", [dict(records[1], location="New room")])
    assert one.post(f"/api/plans/{plan}/export", headers=headers).status_code == 409
    assert not one.get(f"/api/plans/{plan}").json["valid"]
    assert one.delete(f"/api/calendars/{ref}", headers=headers).status_code == 200
    check = one.get(f"/api/plans/{plan}").json
    assert any(c["reason"] == "availability_deleted_or_unavailable" for c in check["changes"])
    assert one.delete(f"/api/plans/{plan}", headers=headers).status_code == 200
    assert one.get("/api/plans").json["plans"] == []


def test_request_boundaries_escaping_and_pairing(db):
    from campus_assistant.privacy import consume_pairing
    from campus_assistant.errors import DomainError
    import pytest
    app = create_app(db.config)
    one, headers = client(app)
    assert one.post("/api/search", json={"query": "x"}, headers=headers).status_code == 400
    assert one.post("/api/search", json={"query": "test"}, headers=dict(headers, Origin="https://evil.example")).status_code == 400
    assert one.get("/", headers={"Host": "evil.example"}).status_code == 400
    assert "Access-Control-Allow-Origin" not in one.get("/").headers
    response = one.post("/api/calendars", data=b"x" * (1024 * 1024 + 20000), headers=headers)
    assert response.status_code == 413
    token = one.post("/api/pair", headers=headers).json["token"]
    profile = consume_pairing(db, token)
    assert db.require_profile(profile)
    with pytest.raises(DomainError):
        consume_pairing(db, token)
    assert "innerHTML" not in (ROOT / "static/js/script1.js").read_text(encoding="utf-8")


def test_review_save_clear_context_and_pairing_boundary(db):
    from campus_assistant.privacy import consume_pairing
    from campus_assistant.planning_context import get_planning_context
    demo(db)
    app = create_app(db.config)
    one, headers = client(app)
    two, other_headers = client(app)
    html = one.get('/plan').text
    assert 'Review before sharing' in html and 'Clear shared context' in html
    assert 'name="reviewed" type="checkbox" required' in html
    assert one.get('/api/planning-context').json['context'] is None
    query = {"start": "2026-10-26T16:00:00Z", "end": "2026-11-02T16:00:00Z", "interests": ["career"]}
    event = one.post('/api/recommend', json=query, headers=headers).json['events'][0]
    selection = {"query": query, "selections": [{"event_id": event['id'], "revision": event['revision']}]}
    body = {"summary": "My approved summary <script>", "preferences": ["career"], "selection": selection, "reviewed": True, "expected_revision": 0}
    assert one.post('/api/planning-context', json=body).status_code == 400
    assert one.post('/api/planning-context', json=dict(body, reviewed=False), headers=headers).status_code == 400
    saved = one.post('/api/planning-context', json=body, headers=headers)
    assert saved.status_code == 200
    plan_ref = saved.json['context']['plan_ref']
    assert one.post('/api/planning-context', json=body, headers=headers).status_code == 409
    assert two.get('/api/planning-context').json['context'] is None
    stolen = dict(body, plan_ref=plan_ref)
    del stolen['selection']
    assert two.post('/api/planning-context', json=stolen, headers=other_headers).status_code == 404
    assert two.delete('/api/planning-context', json={"expected_revision": 1}, headers=other_headers).status_code == 409
    assert one.get('/api/planning-context').json == saved.json
    profile = consume_pairing(db, one.post('/api/pair', headers=headers).json['token'])
    assert get_planning_context(db, profile) == saved.json
    assert one.delete('/api/planning-context', json={"expected_revision": 1}).status_code == 400
    cleared = one.delete('/api/planning-context', json={"expected_revision": 1}, headers=headers)
    assert cleared.status_code == 200 and cleared.json['context'] is None
    assert get_planning_context(db, profile)['context'] is None
    assert one.get(f'/api/plans/{plan_ref}').status_code == 200
    assert one.delete('/api/planning-context', json={"expected_revision": 1}, headers=headers).status_code == 409
    body = dict(stolen, expected_revision=2)
    assert one.post('/api/planning-context', json=body, headers=headers).status_code == 200
    assert one.delete(f'/api/plans/{plan_ref}', headers=headers).status_code == 200
    assert one.get('/api/planning-context').json == {"status": "ok", "revision": 4, "context": None}
