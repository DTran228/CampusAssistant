"""Separate, optional MPNet download/index/search check. Not a quality benchmark."""
import json
import sys
import time
from campus_assistant.config import Config, ROOT
from campus_assistant.db import Database
from campus_assistant.documents import build_index
from campus_assistant.retrieval import search_docs
from campus_assistant.schemas import Search
from campus_assistant.errors import DomainError
from .run import provenance


def run_smoke():
    result = {"provenance": provenance(), "backend": "all-mpnet-base-v2 + FAISS IndexFlatL2", "scope": "Small real-model smoke, not retrieval quality or real-campus validation"}
    started = time.perf_counter()
    try:
        db = Database(Config(data_dir=ROOT / "runtime/real-smoke", fixed_now="2026-10-26T16:00:00Z"))
        sources = json.loads((ROOT / "data/demo/documents.json").read_text())
        index = build_index(db, sources, "mpnet")
        result["model_load_and_index_ms"] = (time.perf_counter() - started) * 1000
        rows = []
        for query, source, page in [("When does the library open on weekdays?", "library", 1), ("How long can students use a group study room?", "library", 2), ("Where do I request a transcript?", "registrar", 2)]:
            tick = time.perf_counter()
            found = search_docs(db, Search(query=query))
            hit = any(e["source_id"] == source and e["page"] == page for e in found["excerpts"])
            rows.append({"query": query, "expected_source": source, "expected_page": page, "hit_at_3": hit, "latency_ms": (time.perf_counter() - tick) * 1000, "excerpts": found["excerpts"]})
        with db.connect() as conn:
            index_path = conn.execute("SELECT index_path FROM document_revisions WHERE id=?", (index["revision"],)).fetchone()[0]
        from pathlib import Path
        path = Path(index_path)
        original_bytes = path.read_bytes()
        corrupt_rejected = False
        try:
            path.write_bytes(b"corrupted-index-fixture")
            try:
                search_docs(db, Search(query="library hours"))
            except DomainError as exc:
                corrupt_rejected = exc.code == "unavailable_source"
        finally:
            path.write_bytes(original_bytes)
        result.update(status="passed" if all(r["hit_at_3"] for r in rows) and corrupt_rejected else "failed", index=index, queries=rows, corrupt_faiss_index_rejected=corrupt_rejected)
    except Exception as exc:
        result.update(status="unavailable", error_type=type(exc).__name__, error=str(exc)[:500])
    output = ROOT / "eval/results/real-retrieval-smoke.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output)}))
    return result


if __name__ == "__main__":
    sys.exit(0 if run_smoke()["status"] == "passed" else 2)
