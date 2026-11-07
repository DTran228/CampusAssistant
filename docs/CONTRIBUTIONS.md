# Contributions and review record

The repository is being developed as a personal project. No human collaborator names, roles, interviews or reviews were supplied. Do not infer contributions from GitHub usernames or claim a co-development team. This implementation was produced with AI coding assistance in the existing owner workspace; it is not evidence that the owner independently authored every new line.

Inherited/new ownership boundaries are recorded in `PROVENANCE.md`. Actual human roles can be added when supplied, with consent and specific work/review evidence.

| Requirement / review observation | Resulting change | Evidence |
|---|---|---|
| Preserve inherited baseline and private changes | History retained; old entry names kept; `.env` untouched | Git diff, PROVENANCE.md |
| Deterministic schedule validation | Python hard filters and selection checks | planner.py; 36 fixture cases |
| Source changes before export | Stored revision and final transaction check | integration/test_planner.py |
| Private web / MCP boundary | Server sessions, CSRF, owned refs, explicit pairing | integration/test_web.py, test_mcp.py |
| Do not equate fixture retrieval with semantic quality | Separate demo and MPNet smoke/evaluation evidence | EVALUATION.md; eval/results/ |

These are implementation traceability notes, not claimed human review comments. Future collaborator review log template: date, actual name/role, requirement, substantive comment, response, resulting commit/test. Suggested UI/ingestion/organizer roles in the guideline are proposals only, not existing participants.
