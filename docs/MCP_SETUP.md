# Local MCP setup (SDK 1.26.0)

Web và MCP là hai giao diện của cùng Python services. Web không gọi vòng qua MCP. Một host bên ngoài điều phối tools; cài MCP không làm Llama 2 tự biết tool calling.

Tài liệu đã đối chiếu với SDK cài đặt:

- [Official Python SDK v1.26.0](https://github.com/modelcontextprotocol/python-sdk/tree/v1.26.0)
- [MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture)
- [Server concepts](https://modelcontextprotocol.io/docs/learn/server-concepts)

SDK low-level `Server`, `stdio_server`, `list_tools`, `call_tool` xử lý protocol. Pydantic validation trong handler trả typed `invalid_input` cho sai contract. stdout dành riêng protocol; diagnostics stderr. Chỉ stdio, không public endpoint.

## Profile riêng (PowerShell)

```powershell
Set-Location C:\dev\CampusAssistant
$env:CAMPUS_DATA_DIR='C:\dev\CampusAssistant\runtime'
$env:CAMPUS_NOW='2026-10-26T12:00:00-04:00'
.\.venv\Scripts\python.exe -m campus_assistant.cli demo
.\.venv\Scripts\python.exe -m campus_assistant.cli profile
```

Lưu opaque `profile` được trả về riêng tư. Nó không có quyền đọc calendar của web session khác. Import lịch fictional cho profile đó bằng:

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli import-calendar '<PROFILE>' data/demo/classes.ics --start '2026-10-26T00:00:00-04:00' --end '2026-11-02T00:00:00-05:00' --timezone America/New_York
```

## Pair web session (tùy chọn, explicit)

Trong **My availability**, bấm **Create private pairing code** chỉ khi muốn MCP dùng chung calendar/plan của session đó. Sau đó, ở terminal trên cùng máy/data directory:

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli pair
```

Nhập code khi được hỏi (tránh ghi vào shell history). Profile trả về gắn với session web đó. Code hết hạn sau 10 phút, dùng một lần. Không commit code/profile. Không có endpoint nhận user ID để tự nhận quyền truy cập.

## Host configuration example

Thay placeholders bằng **absolute paths** và private profile thực. Host có thể cần restart sau khi sửa config. `cwd` không được mọi host hỗ trợ: nếu thiếu, editable install vẫn cho phép import package; CAMPUS_DATA_DIR phải absolute.

```json
{
  "mcpServers": {
    "campus-scout": {
      "command": "C:\\ABSOLUTE\\CampusAssistant\\.venv\\Scripts\\python.exe",
      "args": ["-m", "campus_assistant.mcp_server"],
      "env": {
        "CAMPUS_DATA_DIR": "C:\\ABSOLUTE\\CampusAssistant\\runtime",
        "CAMPUS_PROFILE": "<PRIVATE_CREATED_OR_PAIRED_PROFILE>",
        "CAMPUS_NOW": "2026-10-26T12:00:00-04:00"
      }
    }
  }
}
```

macOS/Linux: command `/ABSOLUTE/CampusAssistant/.venv/bin/python`, data dir `/ABSOLUTE/CampusAssistant/runtime`. Bỏ `CAMPUS_NOW` khi dùng dữ liệu thực.

## Contracts and example workflow

`search_campus_docs` accepts `query`, optional `category`, `limit` 1..10. `find_campus_events`/`recommend_events` accept EventQuery fields directly. `revalidate_plan` accepts `plan_ref`. `export_event_calendar` accepts `selections` (up to five event_id/revision pairs) plus `query` containing dates and optional owned `calendar_ref`. Output has `status`, typed `data`, typed `error`; tool errors also set MCP `isError`.

EventQuery:

Discovery `limit` defaults to 50 and is bounded to 1..100. Recommendations always return at most five, with full feasible/excluded counts.

```json
{
  "start": "2026-10-26T16:00:00Z",
  "end": "2026-11-02T16:00:00Z",
  "interests": ["career", "workshop"],
  "max_cost": 0,
  "free_food": false,
  "buffer_minutes": 0,
  "calendar_ref": "<OWNED_CALENDAR_REFERENCE_OR_NULL>"
}
```

Discover → recommend using the uploaded calendar reference → inspect evidence and revisions → approve the fields to remember → save context → close A → open B on the same profile → retrieve context → revalidate → let the student choose. Recommendations never save automatically. References come from upload responses/web pairing; tools never accept filesystem paths or a caller-selected profile.

## Approved context contracts (seven tools total)

`get_planning_context` takes `{}`. New profiles return `data: {"status":"ok","revision":0,"context":null}`. A saved context contains `summary`, `preferences` (explicit interest strings), `plan_ref`, selected `event_id/revision` pairs and `updated_at`. It excludes full chats and raw class calendars. Clearing retains a revision counter and returns `context:null` with the newer revision.

Before calling `save_planning_context`, a client must display the **actual** summary, interests and selected events (title, time, ID/revision), allow editing and obtain the student's confirmation. `reviewed:true` records the client's assertion; the server cannot prove that a host displayed a confirmation. Treat saved text as student data, not executable instructions. Read the current context revision before previewing. Send exactly one plan source:

```json
{
  "summary": "Remember my robotics workshop choice; recheck the time against my classes.",
  "preferences": ["robotics", "workshop"],
  "expected_revision": 0,
  "reviewed": true,
  "selection": {
    "query": {
      "start": "2026-10-26T16:00:00Z",
      "end": "2026-11-02T16:00:00Z",
      "interests": ["robotics", "workshop"],
      "max_cost": 0,
      "calendar_ref": "<OWNED_UPLOADED_CALENDAR>"
    },
    "selections": [{"event_id": "<RECOMMENDED_EVENT_ID>", "revision": 1}]
  }
}
```

For an existing owned plan, omit `selection` and send `"plan_ref":"<OWNED_PLAN>"`. This supports sharing an already changed plan for later review; saving context does not certify current feasibility. New selections reuse `planner.py` validation and storage, atomically with the context. Source moves/cancellations preserve saved IDs/revisions until the student approves a new plan.

Summary: 1–1000 characters. Preferences: 0–20 interests, each 1–80 characters. A selection has 1–5 unique event/revision pairs and the existing bounded query. Inputs forbid extra fields. Errors use the existing structured envelope with `isError:true`: `stale_context` for an old context revision, `stale_selection` for changed/invalid event selections, `not_found` for foreign references, and `invalid_input` for malformed/unreviewed fields. A failed save leaves previous context and plans unchanged. On `stale_context`, reload, show the changed fields and ask for review again; never automatically overwrite.

B only needs `get_planning_context {}` after starting on the **same locally configured profile**. It reads `data.context.plan_ref` and calls `revalidate_plan`. That response supplies current times/revisions, previous times, conflict explanations and feasible alternatives. B should explain the conflict, offer keeping the old choice for later review or choosing a displayed alternative, and wait for the student's decision. Recommending an alternative does not replace the saved plan. Recheck before export.

Review/clear lives in web **My plan** on the paired session. `DELETE /api/planning-context` requires CSRF and `{"expected_revision":N}`; clearing leaves plans/availability intact. There is no extra MCP deletion tool in this release. Clearing local storage does not retract information already received in a host's conversation; remove host history separately if needed.

## Reproduce independent A → B on Windows

```powershell
Set-Location C:\dev\CampusAssistant
.\.venv\Scripts\python.exe -m eval.handoff_demo
```

Two previews request `yes`: initial workshop and separately chosen alternative. Use `--approve-fixture` for automated fictional approval. Each run creates a temporary data directory, uses the fixed October fixture clock, starts A via stdio, closes both its SDK session and server subprocess, moves the workshop into a class, then starts B with a fresh session/subprocess. A third profile tests isolation; another fresh session verifies clearing and an explicitly reviewed alternative export. No state/plan reference is copied from A into B's request; B fetches it from SQLite through MCP. The demo additionally tests cancellation, stale writes and failed saves, and writes `eval/results/handoff.json` without profile capabilities.

For two actual desktop hosts, configure both with the same absolute data directory and paired `CAMPUS_PROFILE` using the JSON above. Follow the robotics walkthrough in README (`demo-handoff`, then `demo-change --workshop` in a second terminal). Pairing is local setup once; it is not a plan code to transfer at every handoff. A different `cli profile` creates an unrelated identity and returns an empty context.

`tests/integration/test_mcp.py` retains all five original contracts and checks seven tool definitions. It runs the independent-client scenario over the official protocol, plus invalid arguments, page evidence, discover/recommend/export and isolation. `test_planning_context.py` covers populated migration, storage rollback and revision control. `test_web.py` exercises review/save/clear, CSRF, pairing parity and cross-session denial.

**External desktop-host smoke test: pending.** Protocol subprocess validation is not a claim that a particular desktop host configuration has been tried.
