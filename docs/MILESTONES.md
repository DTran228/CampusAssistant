# Milestone and handoff record

Implementation on October 26, 2026 (America/New_York). Dates in raw results use UTC. The guideline was treated as the requested project specification; suggested collaborators/impact targets were not treated as facts or authorization for external services.

| Gate | Implemented | Checks executed at gate | What to understand / remaining boundary |
|---|---|---|---|
| M0 | Dependency/config, SQLite migration, fixtures, import-safe compatibility entry points, private-data ignores | Migration/profile test, `/health` through Flask client; default install and pip check | No source PDF/GGUF supplied; `.env` and Git history preserved. No model needed to start |
| M1 | Page-aware ingestion, stable chunk/hash, immutable index revisions, JSON metadata, excerpts/UI, optional generation fallback | Initial M0/M1: 3 passed. Later actual PDF extraction test and real MPNet/FAISS smoke: 3 expected source/page hits | Default lexical demo is not semantic quality evidence. Citation resolution is not factual support. Real university documents/LLM absent |
| M2 | JSON/CSV and HTTP ICS adapter, identity/upsert, revisions/cancel/freshness, outage preservation | 7 passed including actual localhost HTTP server, idempotency, cancel, failed source preservation | Feed configuration is admin CLI. Refresh is explicit; absence is not cancellation. No real university feed supplied |
| M3 | Bounded recurring availability, DST/EXDATE/overrides, deterministic ranking, owned plans, revalidation/alternatives, atomic checked export, four web views | Core M2/M3: 19 passed; final suite extends edge cases. Browser: actual fixture upload → schedule filter → save → ICS download → source move → disabled export | Python owns hard constraints. Multiple ranked options may conflict; save/export checks selections. No calendar write/registration |
| M4 | Five official-SDK stdio tools, typed schemas/results/errors, explicit profile/pairing, shared business functions | M0–M4 combined: 22 passed including real SDK subprocess initialize/list/call/shutdown and another profile denied | External desktop MCP host smoke still pending. MCP does not provide Llama 2 tool orchestration automatically |
| M5 | 36 planner cases, 40 source-grouped retrieval questions, raw results/benchmarks, study templates, evidence/provenance docs, Windows/Linux CI definition, screenshots | Expanded offline suite and pip check; eval.run with finite synthetic workload; separate model smoke; browser evidence below | Hosted CI, real campus validation, LLM support evaluation and actual user impact remain separate/unmeasured |

Exact final test totals are in `eval/results/tests.xml` and `verification.json`; gate counts above record the incremental checks, not additive independent trials.

Final observed run: **70 passed, 0 skipped, 0 failures** in 52.96 seconds, including the cached MPNet/FAISS test. Three SWIG deprecation warnings originated in the optional FAISS dependency. JavaScript syntax, Python compileall, pip check and Git whitespace check passed. Planner evaluation: 36 cases, 14 known feasible, 0 incorrect feasible recommendations, 0 missed valid options. These are fixture outcomes, not student-impact claims.

## Browser evidence

The first sandbox server could not be reached from the in-app browser. Restarting the local-only server outside the network sandbox resolved it; no firewall or security settings were weakened.

Verified through browser controls against `http://127.0.0.1:5555`:

1. Uploaded the checked-in fictional `classes.ics`; UI showed **2 busy intervals**, raw file/titles discarded.
2. Selected availability and searched. UI showed two feasible options, interview lab first; Tuesday resume workshop excluded for schedule conflict.
3. Selected interview lab, saved, opened My plan: current selection valid.
4. Clicked Export plan, downloaded actual `campus-events.ics`; parsed that downloaded file with icalendar: one VEVENT titled Interview practice lab.
5. Ran `demo-change`; Recheck saved plans displayed changed start/end, schedule conflict, disabled export, and alternative Python study group.
6. Asked group study room question; UI displayed Fictional Library Guide, evidence E1, page 2, matching excerpt and index timestamp.
7. Applied a small viewport override for responsive QA. Actual CSS viewport/content width were both 375px (no horizontal overflow); override reset afterward.

Screenshots (actual browser, fictional data): `screenshots/events.jpg`, `plan.jpg`, `plan-changed.jpg`, `documents.jpg`, `mobile-events.jpg`. Browser checks are an observed smoke, not a full automated accessibility audit. Keyboard labels/focus/skip link are implemented; screen-reader/device coverage remains limited.

## Remaining external validation

- Actual campus name and trusted public sources; source update/cancellation conventions in a real university feed.
- Real institutional PDFs, relevance thresholds on a non-fixture corpus, independently reviewed retrieval labels.
- Supplied GGUF/local generation, factual claim support and conflict resolution by responsible offices.
- A specific external desktop MCP host/client configuration, beyond official SDK subprocess tests.
- Hosted GitHub Actions and non-Windows platform runs (workflow provided, not dispatched).
- Consented student study; participants = 0, actual task-time savings and impact unmeasured.

Deferred by scope: public multi-tenant hosting, real account/OAuth, live student systems, automatic calendar writes/registration, routing, push notifications, automatic background refresh, HTML scraping without an actual source. Unsupported recurrence forms are explicit errors, not hidden partial support.
