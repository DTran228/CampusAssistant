import json
import pytest
from campus_assistant.config import ROOT
from campus_assistant.documents import build_index
from campus_assistant.schemas import Search
from campus_assistant import answers


@pytest.mark.parametrize("output,expected", [("Unsupported citation [E999]", "unavailable"), ("Library hours are shown in [E1].", "unverified_generated_answer")])
def test_optional_generation_citation_resolution(db, monkeypatch, output, expected):
    build_index(db, json.loads((ROOT / "data/demo/documents.json").read_text()))
    monkeypatch.setenv("CAMPUS_LLM_PATH", "fixture.gguf")
    monkeypatch.setattr(answers, "local_model", lambda: lambda *a, **k: {"choices": [{"text": output}]})
    result = answers.answer(db, Search(query="library hours"))
    assert result["generation"] == expected
    assert result["excerpts"]


def test_eligibility_query_does_not_generate_a_decision(db, monkeypatch):
    build_index(db, json.loads((ROOT / "data/demo/documents.json").read_text()))
    monkeypatch.setenv("CAMPUS_LLM_PATH", "fixture.gguf")
    def should_not_load():
        raise AssertionError("Eligibility decision must not invoke generation")
    monkeypatch.setattr(answers, "local_model", should_not_load)
    result = answers.answer(db, Search(query="scholarship eligibility"))
    assert result["generation"] == "disabled"
    assert "does not determine" in result["answer"]
