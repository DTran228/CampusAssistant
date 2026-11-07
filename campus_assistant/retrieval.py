import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from .documents import digest
from .errors import DomainError
from .schemas import Search

STOP = set("a an the is are do does can i my for to in on at of and what when where how with from this it who".split())


def tokens(text):
    return set(re.findall(r"[a-z0-9]+", text.lower())) - STOP


@lru_cache(maxsize=1)
def embedding_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise DomainError("unavailable_source", "Install the tested retrieval extra before building an MPNet index") from exc
    return SentenceTransformer("sentence-transformers/all-mpnet-base-v2")


def search_docs(db, request: Search):
    with db.connect() as conn:
        revision = conn.execute("SELECT r.* FROM document_revisions r JOIN active_index a ON r.id=a.revision_id").fetchone()
        if not revision:
            raise DomainError("unavailable_source", "No trusted index. Run the index command first.")
        canonical = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM document_chunks WHERE revision_id=?", (revision["id"],))}
    try:
        chunks = json.loads(Path(revision["metadata_path"]).read_text(encoding="utf-8"))
        if len(chunks) != len(canonical) or len({c["id"] for c in chunks}) != len(chunks) or any(c["id"] not in canonical or any(c[k] != canonical[c["id"]][k] for k in ("source_id", "page", "text", "content_hash")) or digest(c["text"]) != c["content_hash"] or c["page"] < 1 for c in chunks):
            raise ValueError("Invalid metadata")
        query_tokens = tokens(request.query)
        if revision["backend"] == "mpnet":
            import faiss
            index = faiss.read_index(revision["index_path"])
            if index.ntotal != len(chunks):
                raise ValueError("Index metadata mismatch")
            vector = embedding_model().encode([request.query], normalize_embeddings=True)
            distances, indices = index.search(vector, len(chunks))
            scored = [(1 - float(distance) / 2, chunks[int(i)]) for distance, i in zip(distances[0], indices[0]) if i >= 0]
            scored = [(score, chunk) for score, chunk in scored if score >= 0.30]
        else:
            scored = [(len(query_tokens & tokens(c["text"])) / max(1, len(query_tokens)), c) for c in chunks]
            scored = [(score, chunk) for score, chunk in scored if score >= 0.25]
        scored = [(score, c) for score, c in scored if not request.category or c["category"] == request.category]
        scored.sort(key=lambda item: (-item[0], item[1]["id"]))
        excerpts = [dict(c, evidence_id=f"E{n}", score=round(score, 4)) for n, (score, c) in enumerate(scored[:request.limit], 1)]
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, ImportError) as exc:
        raise DomainError("unavailable_source", "Index missing or corrupt. Rebuild trusted sources.") from exc
    return {"status": "ok" if excerpts else "insufficient_evidence", "excerpts": excerpts,
            "index_revision": revision["id"], "backend": revision["backend"],
            "indexed_at": revision["created_at"], "freshness": "stale" if (db.config.now() - datetime.fromisoformat(revision["created_at"])).total_seconds() > db.config.stale_hours * 3600 else "fresh",
            "notice": "Fictional lexical demo; not a semantic embedding benchmark." if revision["backend"] == "demo" else "MPNet + FAISS; relevance thresholds require campus-specific evaluation."}
