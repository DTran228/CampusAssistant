import json
import pytest
from campus_assistant.config import ROOT
from campus_assistant.documents import build_index
from campus_assistant.retrieval import search_docs
from campus_assistant.schemas import Search
from campus_assistant.errors import DomainError


def test_missing_and_corrupt_index(db):
    with pytest.raises(DomainError, match="No trusted index"):
        search_docs(db, Search(query="library hours"))
    build_index(db, json.loads((ROOT / "data/demo/documents.json").read_text()))
    result = search_docs(db, Search(query="library hours"))
    assert result["excerpts"][0]["page"] == 1
    assert result["excerpts"][0]["url"] == "fixture://library-guide"
    for path in (db.config.data_dir / "indexes").glob("*.json"):
        path.write_text("broken")
    with pytest.raises(DomainError, match="corrupt"):
        search_docs(db, Search(query="library hours"))


def test_refresh_stable_chunks_out_of_domain_and_failure_atomicity(db):
    sources = json.loads((ROOT / "data/demo/documents.json").read_text())
    a = build_index(db, sources)
    one = search_docs(db, Search(query="group study room"))
    b = build_index(db, sources)
    two = search_docs(db, Search(query="group study room"))
    assert a["revision"] != b["revision"]
    assert one["excerpts"][0]["id"] == two["excerpts"][0]["id"]
    assert two["excerpts"][0]["page"] == 2
    assert not search_docs(db, Search(query="quantum volcano penguin"))["excerpts"]
    with pytest.raises(DomainError):
        build_index(db, [])
    assert search_docs(db, Search(query="room"))["index_revision"] == b["revision"]
