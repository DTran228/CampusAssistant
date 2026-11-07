import json
import pytest
from campus_assistant.config import ROOT
from eval.run import planner_case

CASES = json.loads((ROOT / "eval/planner_cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_known_planner_outcomes(db, case):
    result = planner_case(db, case)
    assert result["correct"], result


def test_question_annotations_match_pages():
    questions = json.loads((ROOT / "eval/retrieval_questions.json").read_text())
    corpus = {s["id"]: s for s in json.loads((ROOT / "data/demo/documents.json").read_text())}
    assert len(questions) == 40 and len({q["id"] for q in questions}) == 40
    sources = {}
    for question in questions:
        sources.setdefault(question["split"], set()).add(question["source"])
        for passage in question["evidence"]:
            assert passage["passage"] in corpus[question["source"]]["pages"][passage["page"] - 1]
    assert sources["development"].isdisjoint(sources["held_out"])
