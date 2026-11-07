"""Trusted local ingestion. No pickle is read, including inherited FAISS metadata."""
import hashlib
import json
import secrets
from pathlib import Path
from .errors import DomainError


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pdf_source(path, title, url, category="general"):
    from pypdf import PdfReader
    path = Path(path)
    if path.stat().st_size > 20 * 1024 * 1024:
        raise DomainError("invalid_input", "PDF limit is 20 MiB")
    reader = PdfReader(path)
    if reader.is_encrypted or len(reader.pages) > 500:
        raise DomainError("invalid_input", "Encrypted PDFs or more than 500 pages are unsupported")
    return {"id": digest(url), "title": title, "url": url, "category": category,
            "pages": [page.extract_text() or "" for page in reader.pages]}


def build_index(db, sources, backend="demo"):
    if backend not in ("demo", "mpnet"):
        raise DomainError("invalid_input", "Use demo or mpnet backend")
    revision = secrets.token_hex(12)
    chunks = []
    for source in sources:
        if not source.get("pages"):
            raise DomainError("invalid_input", "Document must have pages")
        for page, text in enumerate(source["pages"], 1):
            for offset in range(0, len(text), 350):
                passage = text[offset:offset + 500].strip()
                if not passage:
                    continue
                content_hash = digest(passage)
                chunks.append({"id": digest(f"{source['id']}:{page}:{offset}:{content_hash}"),
                               "source_id": source["id"], "title": source["title"],
                               "url": source["url"], "category": source["category"],
                               "page": page, "text": passage, "content_hash": content_hash})
    if not chunks:
        raise DomainError("invalid_input", "No extractable text; scanned PDFs require external OCR")
    directory = db.config.data_dir / "indexes"
    directory.mkdir(exist_ok=True)
    metadata_path = directory / f"{revision}.json"
    index_path = None
    if backend == "mpnet":
        from .retrieval import embedding_model
        import faiss
        vectors = embedding_model().encode([c["text"] for c in chunks], normalize_embeddings=True)
        index = faiss.IndexFlatL2(vectors.shape[1])
        index.add(vectors)
        index_path = directory / f"{revision}.faiss"
        faiss.write_index(index, str(index_path))
    metadata_path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    # Files are immutable per revision. SQLite activates both only after construction succeeds.
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for source in sources:
            conn.execute("INSERT INTO document_sources VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,url=excluded.url,category=excluded.category",
                         (source["id"], source["title"], source["url"], source["category"]))
        conn.execute("INSERT INTO document_revisions VALUES (?,?,?,?,?)",
                     (revision, backend, str(metadata_path), str(index_path) if index_path else None, db.config.now().isoformat()))
        conn.executemany("INSERT INTO document_chunks VALUES (?,?,?,?,?,?)",
                         [(c["id"], revision, c["source_id"], c["page"], c["text"], c["content_hash"]) for c in chunks])
        conn.execute("INSERT INTO active_index VALUES (1,?) ON CONFLICT(singleton) DO UPDATE SET revision_id=excluded.revision_id", (revision,))
    return {"status": "ok", "revision": revision, "backend": backend, "chunks": len(chunks)}
