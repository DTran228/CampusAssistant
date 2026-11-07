# CampusScout — Campus Assistant

A local college personal project: find source-linked events, check class conflicts, save a reviewed plan, and export an iCalendar file. Also search document excerpts with page references. Flask + SQLite + vanilla JavaScript; the same Python functions serve web and an official-SDK stdio MCP server.

**The supplied campus, events and document pages are fictional.** No university account, paid service, API key or LLM is required. No Google Calendar writes or attendance registration occur.

The frontend uses the **Overprint** theme: newsprint surfaces, local Anybody/Archivo fonts, teal/orange ink fields and square controls. The four existing workflows remain intact. See [frontend design and verification](docs/FRONTEND_DESIGN.md) and the shared [design system](design.md).

## Run on Windows PowerShell

Use Python 3.12 (supported: 3.11–3.13). Run each command separately. The existing `.env` is not automatically loaded or overwritten; set environment variables explicitly.

```powershell
Set-Location C:\dev\CampusAssistant
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
$env:CAMPUS_NOW='2026-10-26T12:00:00-04:00'
.\.venv\Scripts\python.exe -m campus_assistant.cli demo
.\.venv\Scripts\python.exe -m campus_assistant.cli serve
```

Open [CampusScout](http://127.0.0.1:5555). Stop with Ctrl+C. It binds only 127.0.0.1. If this workspace already has `.venv`, start at pip install or the demo command. On this workstation, `python` is a Windows Store alias and `py` has no installed interpreter; the environment was created with the Python 3.12 bundled with Codex. To recreate here if needed:

```powershell
& 'C:\Users\Duc Tran\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m venv .venv
```

## macOS / Linux

```sh
cd /absolute/path/CampusAssistant
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
export CAMPUS_NOW='2026-10-26T12:00:00-04:00'
.venv/bin/python -m campus_assistant.cli demo
.venv/bin/python -m campus_assistant.cli serve
```

Dependency installation needs package-registry access once. Default tests/runtime then run offline; the optional MPNet model download is separate. Windows was locally exercised; Linux/macOS commands and the CI matrix are supplied, not claimed as locally executed.

## Reproducible walkthrough

### Current handoff — November 7, 2026: assistant A → B

Windows demo with **independent official-SDK MCP clients and server subprocesses**, without a desktop host or model:

```powershell
Set-Location C:\dev\CampusAssistant
.\.venv\Scripts\python.exe -m eval.handoff_demo
```

Read the exact summary, interests, event and revision displayed by A, then type `yes` to approve. A exits completely. The fixture source moves the robotics workshop into a class; a fresh B requests `get_planning_context {}` without a copied plan code, revalidates the returned plan and explains the conflict. The demo also checks a foreign profile, stale/failed saves, cancellation, clearing and a separately approved alternative. It prompts again before saving the alternative. Each run uses a new temporary SQLite directory and deletes only that demo directory on exit.

For an unattended **scripted fictional approval**, use `.\.venv\Scripts\python.exe -m eval.handoff_demo --approve-fixture`. Results go to `eval/results/handoff.json`; this is software evidence, not student participation or measured time savings.

To reproduce the same changed-workshop scenario in the web UI:

```powershell
$env:CAMPUS_DATA_DIR='C:\dev\CampusAssistant\runtime\handoff-demo'
$env:CAMPUS_NOW='2026-10-26T12:00:00-04:00'
.\.venv\Scripts\python.exe -m campus_assistant.cli demo-handoff
.\.venv\Scripts\python.exe -m campus_assistant.cli serve
```

1. Open **My availability**, import `data/demo/classes.ics` for Oct 26–Nov 2, timezone `America/New_York`.
2. In **Explore events**, use the same dates, interests `robotics, workshop`, cost 0 and the uploaded availability. Select **Robotics workshop: build a rover**, initially Wednesday Oct 28, 16:00–17:00 EDT, and save it.
3. In **My plan → Review before sharing**, choose that plan, enter/edit a short summary and the interests you want remembered. Inspect the event names, current times and saved versions, tick the review checkbox and click **Save approved context**. Nothing shares the full chat or raw calendar.
4. To use this web profile in both MCP hosts, perform the one-time local pairing in [MCP setup](docs/MCP_SETUP.md). Configure A and B with the same private profile and data directory. A calls `get_planning_context`; after A closes, B calls it with `{}` too. No plan ID needs to be copied between assistants.
5. In another PowerShell terminal, set the **same** data directory and clock, then run:

```powershell
$env:CAMPUS_DATA_DIR='C:\dev\CampusAssistant\runtime\handoff-demo'
$env:CAMPUS_NOW='2026-10-26T12:00:00-04:00'
.\.venv\Scripts\python.exe -m campus_assistant.cli demo-change --workshop
```

6. B calls `revalidate_plan` with the reference returned by `get_planning_context`. Or refresh **My plan**: the workshop now runs Tuesday Oct 27, **14:15–15:15 EDT**, overlapping classes **14:00–15:30**. Source revision changes from 1 to 2 in a fresh demo. Export is blocked. **Robotics workshop: sensors lab**, Thursday Oct 29, 16:00–17:00 EDT, is offered for review. Choose it in Explore and save/share a new plan only if desired; the original selection is retained.
7. **Clear shared context** removes the summary, interests and context link; original plans/availability remain. A fresh client sees `context: null`. A different profile sees its own empty state and cannot read or overwrite the first profile's plan. Deleting a linked plan also clears its shared context.

The fixture clock intentionally remains in October so these fictional event dates are reproducible. `demo-handoff` restores original event contents but preserves private plans and revision history; existing plans therefore still need review. Use a new data directory for a fresh revision-1 demonstration. The older career-event walkthrough follows.

1. Keep the fixed clock above. Explore events: use Oct 26 through Nov 2 (end exclusive), `career, workshop`, max cost 0. All times use the configured campus timezone.
2. Open **My availability**. Upload `data/demo/classes.ics`, timezone `America/New_York`, same date range. Raw calendar/titles are discarded; only busy intervals are stored.
3. Return to **Explore events**, select that availability, and Find events. The Tuesday resume workshop conflicts with classes; the Wednesday interview lab ranks first. Read reasons, source/update time, and unknown fields.
4. Select **Interview practice lab**, Save to my plan, then open **My plan**. Export `.ics` and import it manually into a calendar if desired.
5. In another terminal, with the same data directory and fixed clock, run:

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli demo-change
```

Refresh My plan: the source revision moved into a class conflict. Old selection is invalid and export is blocked. Alternatives are suggestions, never silent replacements. Review current details in Explore and save a new selection.

6. Run `python -m campus_assistant.cli demo` using the appropriate environment Python to restore fixture event contents. Revision history and private plans remain; an old saved revision still requires review. Delete plans/availability through their views when finished.
7. **Ask campus questions**: try “How long can I reserve a group study room?” Inspect the fictional library excerpt, page 2, source identity, backend and indexing time. This is evidence search, not a verified real-campus policy answer.

### Full disposable demo reset

For a clean session/database each time, use a dedicated demo directory. First call marks it disposable; subsequent calls explicitly delete its sessions, calendars, plans, event history and active document metadata. Existing unmarked databases are refused. Other workspace data is not touched.

```powershell
$env:CAMPUS_DATA_DIR='C:\dev\CampusAssistant\runtime\disposable-demo'
.\.venv\Scripts\python.exe -m campus_assistant.cli demo-reset
.\.venv\Scripts\python.exe -m campus_assistant.cli serve
```

Do not use a demo-reset workspace for real private data. Old immutable index files can remain until the disposable directory is removed manually.

## Document ingestion

Default demo is a clearly labeled **lexical fixture backend**, not an embedding quality claim. It works without model download. Rebuild the full active corpus from a trusted local manifest:

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli index --manifest data/demo/documents.json --backend demo
```

Real embeddings preserve the original `all-mpnet-base-v2`/FAISS approach, with safe JSON + SQLite metadata and no pickle deserialization:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[retrieval]'
$env:HF_HOME='C:\dev\CampusAssistant\runtime\model-cache'
.\.venv\Scripts\python.exe -m campus_assistant.cli index --manifest data/demo/documents.json --backend mpnet
.\.venv\Scripts\python.exe -m eval.smoke_retrieval
```

For the exact tested Windows retrieval dependency snapshot, use `pip install -r requirements-retrieval-lock.txt` with the environment Python. The default lock intentionally excludes these large model dependencies. Set `CAMPUS_NAME`, `CAMPUS_TIMEZONE`, and `CAMPUS_DEMO=0` only after replacing fictional inputs with actual configured sources; changing a label does not validate a source.

`index` **replaces the whole active corpus**. Single trusted PDF example (use a real supplied path/title/source):

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli index --pdf 'C:\ABSOLUTE\handbook.pdf' --title 'Campus handbook' --url 'https://YOUR-CAMPUS.example/handbook.pdf' --category academic --backend mpnet
```

Use one complete manifest for multiple documents (schema illustrated in `data/demo/documents.json`; pages are extracted text). PDFs: max 20 MiB/500 pages, encrypted/scanned images unsupported; OCR is not implemented. No source PDFs or inherited GGUF model were supplied. The checked-in legacy FAISS/pickle artifacts are preserved but never loaded.

Optional generation only: install `.[llm]`, set `CAMPUS_LLM_PATH` to your GGUF path and `CAMPUS_GPU_LAYERS` (default 0). Model loads lazily once/process. This optional native build may need a compiler; it is not part of the default tested dependency lock. Citation IDs are validated; factual support still needs review. Model failure leaves excerpts and planning available. No immigration/legal eligibility decisions.

## Event inputs and explicit refresh

Validated JSON and CSV fixtures (`data/demo/events.json`, `events.csv`) and a bounded ICS HTTP adapter. Configure sources only through the local CLI; visitors cannot provide arbitrary fetch URLs. CSV categories use semicolons; blank cost means unknown. Prices use the single configured demo dollar unit; currency conversion is not implemented.

Local HTTP demo, terminal 1:

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli fixture-server --port 8766
```

Terminal 2 (same environment):

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli source local-feed 'http://127.0.0.1:8766/feed.ics' --kind ics --title 'Local fictional HTTP feed' --allow-local-fixture
.\.venv\Scripts\python.exe -m campus_assistant.cli refresh local-feed
.\.venv\Scripts\python.exe -m campus_assistant.cli refresh local-feed
```

Second refresh is idempotent. Stop fixture server, refresh again: command fails clearly and existing events remain, labeled refresh_failed. For a real public feed, use an authorized public URL **without** `--allow-local-fixture`; configured host and redirects are validated, private IPs blocked, IP pinned to the connection. No real university feed has been supplied or validated.

CSV example:

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli source csv-demo 'fixture://csv-demo' --kind csv
.\.venv\Scripts\python.exe -m campus_assistant.cli import-events csv-demo data/demo/events.csv
```

Separate source IDs intentionally represent separate identities; similar titles are never auto-merged. Import reports list bad records; explicit STATUS cancellation updates history. Missing events are not cancellations. Refresh is manual, not background/realtime.

## Checks and evaluation

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q -m 'not real_retrieval'
.\.venv\Scripts\python.exe -m eval.run
```

In a restricted Windows sandbox where the system temporary directory is denied, first create `tmp` with `New-Item -ItemType Directory -Force tmp`, then add `--basetemp=tmp/pytest-local` to pytest. Local socket/MCP subprocess tests require loopback/process permissions. They still use no external network service. Do not replace protocol tests with direct function calls.

Optional real model test:

```powershell
$env:CAMPUS_REAL_RETRIEVAL='1'
.\.venv\Scripts\python.exe -m pytest tests/integration/test_real_retrieval.py -q
Remove-Item Env:CAMPUS_REAL_RETRIEVAL
```

See [evaluation methodology](docs/EVALUATION.md) and raw [offline results](eval/results/offline.json). 36 planner cases count false feasible recommendations **and** missed valid options. 40 question/evidence annotations are agent-authored and human-reviewable, split by source/topic; they are not independent human validation. Latency is local tiny-workload median with raw samples, not stable p95 or production SLA. User impact remains unmeasured; study template contains no fictional participants.

GitHub Actions defines Windows/Linux offline checks with no API keys/large model download. A local run does not prove hosted CI ran.

## MCP and API

See [MCP setup](docs/MCP_SETUP.md) for required private profile, explicit one-use web pairing, absolute-path Windows/client examples, seven tool contracts and protocol-test evidence. External desktop-host validation is separate from SDK subprocess validation.

Web views: `/ask`, `/events`, `/availability`, `/plan`. APIs use relative same-origin paths and structured JSON. Start with a GET view to receive a server session and CSRF meta token; send it as `X-CSRF-Token` for POST/DELETE. Supported endpoints: `POST /api/search` (Search), `POST /api/events` or `/api/recommend` (EventQuery), `GET/POST /api/calendars` (multipart upload), `DELETE /api/calendars/<ref>`, `GET/POST /api/plans` (ExportRequest), `GET/DELETE /api/plans/<ref>`, `POST /api/plans/<ref>/export`, `POST /api/export` (ExportRequest), `POST /api/pair`. All private references are scoped to the server session. `GET /health` reports local app status, not availability of external sources/models.

`GET/POST/DELETE /api/planning-context` reads, saves or clears the session's approved context. POST uses `SavePlanningContext` (same as MCP); DELETE takes `{"expected_revision": N}`. Both require CSRF. `stale_context` returns HTTP 409; reload and review before retrying. No profile ID is accepted from callers.

## What to understand before extending

- Python, not the model, decides schedule feasibility. Ranking is explicit interest matches then time; it does not claim an optimal itinerary.
- Source freshness means last successful retrieval/indexing, not proof the source publisher is current. Export blocks stale/failed sources until refresh. Source revision changes need explicit review.
- Uploads cover only a stored horizon of at most 30 days. Unsupported recurrence returns an error instead of silently marking time free. Deleting availability invalidates affected plans.
- MCP profile/session IDs are local capabilities, not public authentication. This is a single-machine project; public multi-user hosting needs separate authentication and operations review.
- Never use fixture Recall@3, finite test success or synthetic demo tasks as achieved student impact. Real feed, real documents, actual user study and optional LLM support evaluation remain separate validations.

More: [architecture/tradeoffs](docs/ARCHITECTURE.md), [provenance](docs/PROVENANCE.md), [contribution record](docs/CONTRIBUTIONS.md), [resume evidence](docs/RESUME_EVIDENCE.md), [milestone/verification record](docs/MILESTONES.md), [study protocol](docs/STUDY_PROTOCOL.md).

The November 7 handoff baseline was **69 offline tests passed**. The completed handoff suite passed **75 tests**, with one real-model test deselected; the final UI display check also passed all three web tests. See the [Vietnamese Windows walkthrough](docs/HANDOFF_NOVEMBER_7.md), [handoff verification](eval/results/handoff-verification.json), [protocol demo results](eval/results/handoff.json) and [handoff test XML](eval/results/handoff-tests.xml). The older [verification](eval/results/verification.json) and [screenshots](docs/screenshots/plan-changed.jpg) describe the October implementation, including its separate real-model check. Hosted CI and a specific external desktop MCP host remain unverified. Student impact is unmeasured; no 30% time reduction is claimed.
