# Resume evidence: implementation before claims

| Possible claim | Evidence | Boundary |
|---|---|---|
| Built a local event discovery → availability → saved plan → calendar export workflow | web.py, templates, JS; test_web.py | HTTP workflow tested; actual university integration not supplied |
| Reused deterministic scheduling logic in web and MCP | planner.py; real SDK subprocess test_mcp.py | Local stdio; external desktop host pending |
| Resumed an explicitly reviewed event plan across independent assistants on the same local profile | planning_context.py, migration 002; test_mcp.py; eval/results/handoff.json | Real SDK subprocess clients, fictional workshop/calendar; no desktop-host or user-impact claim |
| Protected context ownership and stale edits; saved plan + context atomically | test_planning_context.py, test_web.py, test_mcp.py | Populated database migration, rollback, clear, CSRF and foreign-profile rejection; local OS capability boundary |
| Tracks changing/cancelled events and blocks stale/conflicting exports | events.py, planner.py; test_feed.py, test_planner.py | Explicit refresh, no realtime guarantee |
| Grounded document excerpts with page/source and trusted index revisions | documents.py, retrieval.py; test_documents.py | Inherited MPNet/FAISS baseline acknowledged; corpus fictional |
| Correct on a specified varied fixture workload | eval/results/offline.json planner rows | Finite synthetic cases; not real-world 100% reliability |
| Retrieval Recall@3 on source-grouped questions | eval/results/offline.json retrieval rows | Agent-authored labels, tiny lexical demo; no independent human validation |
| MPNet/FAISS actual execution | eval/results/real-retrieval-smoke.json | Read recorded status; a smoke is not a quality benchmark |
| Performance | eval/results/offline.json performance samples and provenance | Local tiny workload median, no stable p95/SLA/comparative speedup |
| Reduced student task time / improved outcomes | Future consented study records | **Unmeasured. No participant data. No achieved impact claim.** |
| Collaboration | docs/CONTRIBUTIONS.md, future actual reviews/commits | No collaborators supplied; do not claim a team |

Future two-bullet outline (rewrite with verified evidence only):

- Built CampusScout to help students discover source-linked events that fit their classes and export reviewed selections; [actual user-study result, if measured], with [actual collaborators/roles, only if supplied].
- Implemented deterministic recurrence/conflict checks, event revision revalidation and shared web/MCP services; [verified workload size and error counts] on synthetic acceptance cases, with [real retrieval/evaluation result and its scope].

Do not copy placeholders as achievements. The inherited project already used embeddings/FAISS/local Llama; new contributions must identify the planner, provenance, protocol integration and tests rather than presenting inherited technology as newly invented work.

## November 7 handoff evidence

Baseline: 69 offline tests passed, one optional real-model test deselected (`handoff-baseline.xml`). Initial sandbox attempts failed on Windows temporary-directory/socket permissions; the baseline passed with a workspace temporary directory and permitted loopback/subprocess execution. A later implementation run found the old migration-count test assumed one migration; it was updated to check the actual migration inventory and repeatability.

The current handoff report is `eval/results/handoff-verification.json`; protocol demonstration is `handoff.json`; automated cases are in `handoff-tests.xml`. `offline.json` was rerun for the finite 36-case planner workload and 40 lexical-fixture retrieval questions. Older October verification and real-retrieval files remain historical evidence, not a claim that those optional external checks ran again.

**Software evidence and human research are separate.** Scripted approvals verify tool/data behavior. They are not consented student participants. Participant count remains zero, user completion/time savings/satisfaction are unmeasured. A 30% planning-time reduction is only a study target until actual consented, counterbalanced task records support it. Compare successful verified conflict-free final selections with the same timing endpoint in both conditions, report failures/completion too, and follow `STUDY_PROTOCOL.md`. No three-person collaboration claim is supported without actual contribution records.
