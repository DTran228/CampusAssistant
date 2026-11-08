# Developer guide

Start with the [README quick start](../README.md#quick-start) to run the app and try the robotics demo. This guide holds the setup details and commands that are not needed for a first visit.

## Environment and configuration

Python 3.11–3.13 is supported; recorded local runs used Python 3.12 on Windows. Install the default pinned environment with `python -m pip install -r requirements-lock.txt` using the Python inside your virtual environment. Dependency installation needs package-registry access once. Optional retrieval and LLM dependencies are separate.

The application **does not automatically load `.env`**. Set variables in the same shell used to start Flask or MCP. [`.env.example`](../.env.example) documents them.

| Variable | Purpose |
| --- | --- |
| `CAMPUS_DATA_DIR` | SQLite and index directory; defaults to `runtime`, resolved from the working directory. Use the same absolute directory for web and paired MCP clients. |
| `CAMPUS_NOW` | Timezone-aware fixed clock for fixtures. Use `2026-10-26T12:00:00-04:00` for the demo; leave unset with real data. |
| `CAMPUS_NAME`, `CAMPUS_TIMEZONE` | Campus label and display timezone; defaults are fictional and `America/New_York`. |
| `CAMPUS_DEMO` | Demo labeling, enabled by default. Set `0` only after replacing fictional sources. Changing a label does not validate the source. |
| `CAMPUS_PROFILE` | Private profile capability for an MCP process. Create or explicitly pair it using the CLI. |
| `CAMPUS_LLM_PATH`, `CAMPUS_GPU_LAYERS` | Optional local GGUF model path and generation settings. GPU layers default to `0`. |

Flask binds to `127.0.0.1`, port `5555` by default. Change only the port with:

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli serve --port 5556
```

The CLI also accepts `--data-dir` **before** its subcommand:

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli --data-dir runtime/demo init
.\.venv\Scripts\python.exe -m campus_assistant.cli --help
```

On macOS/Linux, use `.venv/bin/python` and `export NAME='value'` in place of the Windows executable and `$env:NAME='value'`. Commands and a cross-platform CI workflow are supplied; the recorded local checks were on Windows.

## Demo contents and resets

| Command | Behavior |
| --- | --- |
| `demo` | Imports the fictional documents and six base events. Restores source contents while preserving private plans and revision history. |
| `demo-handoff` | Runs the base demo and adds the two robotics workshops used by the current README. |
| `demo-change` | Moves the interview lab into a class conflict for the earlier career-event walkthrough. |
| `demo-change --workshop` | Moves the robotics workshop into a class conflict for the current handoff. |
| `demo-reset` | Resets a marked disposable demo workspace, including private sessions, calendars, plans and source history. Refuses an existing unmarked database. |

Use a dedicated directory for a destructive reset. First invocation marks a new directory disposable; later resets explicitly delete its records:

```powershell
$env:CAMPUS_DATA_DIR=(Join-Path $PWD 'runtime/disposable-demo')
$env:CAMPUS_NOW='2026-10-26T12:00:00-04:00'
.\.venv\Scripts\python.exe -m campus_assistant.cli demo-reset
.\.venv\Scripts\python.exe -m campus_assistant.cli demo-handoff
.\.venv\Scripts\python.exe -m campus_assistant.cli serve
```

Do not put real private data in that workspace. Resetting can leave old immutable index files until the disposable directory is manually removed. Use a new data directory when you want a fresh revision-1 demonstration; restoring event contents does not erase revision history.

### Earlier career-event walkthrough

With the same fixed clock, run `demo`, upload `data/demo/classes.ics` for Oct 26–Nov 2, and search `career, workshop` with maximum cost `0` and that availability. The resume workshop conflicts with classes; **Interview practice lab** fits on Wednesday Oct 28, 16:00–17:00 EDT. Save it, run `demo-change` in another terminal with the same data directory and clock, then recheck My plan. Its moved time conflicts with class, so export is blocked. The robotics example in README is the current primary walkthrough.

## Documents and optional models

Default search uses a **lexical fixture backend**, with no model download. Rebuild the active corpus from a trusted manifest:

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli index --manifest data/demo/documents.json --backend demo
```

`index` replaces the **whole active corpus**. For multiple documents, use one complete manifest, following [`data/demo/documents.json`](../data/demo/documents.json).

### Real MPNet / FAISS retrieval

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[retrieval]'
$env:HF_HOME=(Join-Path $PWD 'runtime/model-cache')
.\.venv\Scripts\python.exe -m campus_assistant.cli index --manifest data/demo/documents.json --backend mpnet
.\.venv\Scripts\python.exe -m eval.smoke_retrieval
```

The embedding backend uses `all-mpnet-base-v2` with FAISS. For the recorded Windows dependency snapshot, install [`requirements-retrieval-lock.txt`](../requirements-retrieval-lock.txt). The default lock excludes the large retrieval dependencies. The legacy FAISS/pickle files are preserved for provenance and never loaded automatically.

Trusted local PDF example, using your own actual path/title/source:

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli index --pdf 'C:\ABSOLUTE\handbook.pdf' --title 'Campus handbook' --url 'https://YOUR-CAMPUS.example/handbook.pdf' --category academic --backend mpnet
```

PDF limits: 20 MiB / 500 pages; encrypted/scanned image PDFs and OCR are unsupported. No real campus PDF or GGUF model is supplied. Search returns excerpts and evidence; it does not establish real policy. Confirm administrative guidance with the responsible office. The application does not make immigration/legal eligibility decisions.

### Optional local generation

Install `.[llm]` with the environment Python and set `CAMPUS_LLM_PATH` to your trusted GGUF file. This native package may require a compiler and is not in the default tested lock. The model loads lazily, once per process. Citation identifiers are validated, but factual support still needs review; generation failure leaves excerpts and event planning available.

## Event sources and explicit refresh

JSON/CSV fixtures and an ICS HTTP adapter feed the same revisioned event store. Source configuration is a local CLI/admin task. Visitors cannot submit arbitrary fetch URLs. There is no background refresh or automatic cancellation inferred from an event disappearing.

### Local HTTP fixture feed

Terminal 1, from the repo root:

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli fixture-server --port 8766
```

Terminal 2, with the same data directory and clock as your app:

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli source local-feed 'http://127.0.0.1:8766/feed.ics' --kind ics --title 'Local fictional HTTP feed' --allow-local-fixture
.\.venv\Scripts\python.exe -m campus_assistant.cli refresh local-feed
.\.venv\Scripts\python.exe -m campus_assistant.cli refresh local-feed
```

The second refresh is idempotent. Stop the fixture server and refresh again: the command fails, retains existing events, and labels the source `refresh_failed`.

For a real public source, use an authorized public URL **without** `--allow-local-fixture`. The adapter validates configured hosts and redirects, blocks private addresses, and pins the checked IP to the connection. No real university feed has been supplied or validated.

### CSV import

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli source csv-demo 'fixture://csv-demo' --kind csv
.\.venv\Scripts\python.exe -m campus_assistant.cli import-events csv-demo data/demo/events.csv
```

CSV categories use semicolons; blank cost is unknown. Prices use the configured demo dollar unit, without currency conversion. Different source IDs are distinct identities; similar titles are never auto-merged. Import reports expose invalid records. Explicit source cancellation updates revision history; missing records alone are not cancellations.

## Web API

The four views are `/events`, `/ask`, `/availability` and `/plan`. Start with a GET view to receive the session cookie and CSRF meta token. Send that token as `X-CSRF-Token` with POST/DELETE requests. Private references are resolved inside the session's profile; API inputs do not accept an arbitrary user ID as authorization.

| Endpoint | Input / purpose |
| --- | --- |
| `POST /api/search` (also `/ask`) | `Search`; document excerpts and optional answer generation. |
| `POST /api/events`, `POST /api/recommend` | `EventQuery`; discovery or availability-aware recommendations. |
| `GET/POST /api/calendars` | List owned availability or upload multipart `.ics` data. |
| `DELETE /api/calendars/<ref>` | Delete owned availability. |
| `GET/POST /api/plans` | List/revalidate owned plans or save an `ExportRequest`. |
| `GET/DELETE /api/plans/<ref>` | Revalidate or delete an owned plan. |
| `POST /api/plans/<ref>/export`, `POST /api/export` | Recheck revisions/conflicts, then return ICS. Direct export takes `ExportRequest`. |
| `GET/POST/DELETE /api/planning-context` | Read, save or clear approved context. POST takes `SavePlanningContext`; DELETE takes `{"expected_revision":N}`. |
| `POST /api/pair` | Create a private one-use local pairing token. |
| `GET /health` | Local app status, not a claim about external sources/models. |

Contracts live in [`schemas.py`](../campus_assistant/schemas.py). Stale context or event selection returns HTTP 409. Reload, review, and confirm before retrying. MCP uses these shared services directly; the web does not call its own MCP server. See [MCP contracts and setup](MCP_SETUP.md).

## Checks and evaluation

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q -m 'not real_retrieval'
.\.venv\Scripts\python.exe -m eval.run
.\.venv\Scripts\python.exe -m eval.handoff_demo --approve-fixture
```

`--approve-fixture` means scripted approval of fictional selections, not student participation. The handoff demo uses independent SDK sessions/server subprocesses and a separate temporary database. Results go to `eval/results/handoff.json`; use `--output` for a separate report path.

If the Windows sandbox denies the system temp directory, create `tmp` and add `--basetemp=tmp/pytest-local` to pytest. HTTP-loopback/MCP subprocess tests need local socket/process permissions; no external service is needed. Do not substitute direct function calls for protocol tests.

Optional real-model check, separate from the offline suite:

```powershell
$env:CAMPUS_REAL_RETRIEVAL='1'
.\.venv\Scripts\python.exe -m pytest tests/integration/test_real_retrieval.py -q
Remove-Item Env:CAMPUS_REAL_RETRIEVAL
```

See [evaluation methodology](EVALUATION.md), [recorded frontend/regression checks](../eval/results/overprint-verification.json), [handoff evidence](../eval/results/handoff-verification.json), and [offline evaluation](../eval/results/offline.json). The 40 lexical-fixture questions are agent-authored and human-reviewable, not independent human validation. Small local latency samples are not a stable p95 or production SLA. User impact is unmeasured; study recruitment is separate. [Windows/Linux CI](../.github/workflows/checks.yml) defines offline checks, and a recorded local pass does not prove hosted CI ran.

## Important boundaries

- Python applies the hard scheduling filters, then ranks explicit interest matches and time. It does not claim an optimal itinerary.
- Availability covers the imported horizon, at most 30 days. Unsupported recurrence is rejected explicitly. Deleting availability invalidates plans that used it.
- Source freshness describes retrieval success/time, not a guarantee that the organizer is current. Export blocks stale/failed sources and changed selections pending review.
- Web sessions and MCP profiles are local capabilities. This release is single-machine; public multi-user hosting requires a separate authentication/operations design.
- Optional real-model retrieval, a specific desktop MCP host, real university sources, local GGUF generation, and student impact each need separate validation. Historical October records are labeled separately from the current handoff.

[Architecture](ARCHITECTURE.md) explains these decisions. [Provenance](PROVENANCE.md) and [contributions](CONTRIBUTIONS.md) distinguish inherited work and new implementation without inventing licensing or collaborators.
