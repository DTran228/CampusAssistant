# Sources and provenance

Inherited repository: [DTran228/CampusAssistant](https://github.com/DTran228/CampusAssistant), inspected base commit `32ddffe91443a8431181e80c53155a8ce9358b9d`. Git history and origin preserved. No license was present in the inspected checkout; this work does not invent an upstream license or third-party attribution. Review permissions before redistribution.

Inherited: Flask chat, all-mpnet-base-v2/FAISS retrieval idea, 500-character chunks/150 overlap, optional local Llama 2 direction, original entry point names. Earlier code loaded models and pickle at import, used global CORS, hard-coded localhost, and innerHTML. Those runtime paths were replaced. Legacy `vectordatabase/` artifacts remain for provenance and are never read by the new application. `datacollection.py` remains an inherited empty file; CLI event ingestion is implemented in the package.

New: shared services, safe JSON/SQLite index revisions, event/source adapters and revision history, privacy/session/pairing boundaries, calendar parser/constraints/plans/revalidation/export, four web views, real stdio MCP, automated and evaluation workloads, docs and CI.

`data/demo/*` is entirely fictional, authored for development. `demo.example` is a placeholder, not an official university. `fixture://` identifies local synthetic evidence. No actual campus identity, supplied PDF, local GGUF model, university feed, private student data or participant recruitment was supplied. Campus name is configurable; do not infer the owner attends SUNY Poly from the inherited UI.

`eval/retrieval_questions.json` contains agent-authored, human-reviewable question/evidence annotations, grouped by source into development/held-out sets. They are not independently validated research labels. Planner cases are intentionally specified ground-truth fixtures, not observations of real users.

`.env` was pre-existing and kept private, unread and unmodified. The existing untracked `.gitignore` rule `.env` was preserved and expanded. No paid resource, external publication, message to another person, or university-system access was performed.
