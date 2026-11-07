"""Run with `python -m eval.run`; no keys, participants or large models needed."""
import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from campus_assistant.config import Config, ROOT
from campus_assistant.db import Database
from campus_assistant.cli import demo
from campus_assistant.documents import build_index
from campus_assistant.events import configure_source, import_records
from campus_assistant.calendars import upload_calendar, export_ics
from campus_assistant.planner import discover
from campus_assistant.retrieval import search_docs
from campus_assistant.schemas import Search, EventQuery

WORKLOAD = ROOT / "eval"


def load(name):
    return json.loads((WORKLOAD / name).read_text(encoding="utf-8"))


def provenance():
    source_files = sorted(p for directory in (ROOT / "campus_assistant", ROOT / "tests", ROOT / "data/demo", ROOT / "eval") for p in directory.rglob("*") if p.suffix in (".py", ".json", ".ics", ".sql") and "results" not in p.parts and "__pycache__" not in p.parts)
    digest = hashlib.sha256()
    for path in source_files:
        digest.update(str(path.relative_to(ROOT)).replace("\\", "/").encode())
        digest.update(path.read_bytes())
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True))
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = "unavailable", True
    return {"measured_at_utc": datetime.now(timezone.utc).isoformat(), "base_commit": commit,
            "working_tree_dirty": dirty, "implementation_dataset_sha256": digest.hexdigest(),
            "dataset_revision": hashlib.sha256((WORKLOAD / "planner_cases.json").read_bytes() + (WORKLOAD / "retrieval_questions.json").read_bytes() + (ROOT / "data/demo/documents.json").read_bytes()).hexdigest(),
            "python": platform.python_version(), "os": platform.platform(), "processor": platform.processor(),
            "configuration": {"clock": "2026-10-26T16:00:00Z", "generation": "disabled", "campus": "fictional"}}


def planner_case(db, case):
    event = {"source_event_id": case["id"], "title": "Career workshop", "description": "Fictional case", "source_url": "fixture://planner/" + case["id"], "timezone": "UTC", "start": "2026-10-27T18:00:00Z", "end": "2026-10-27T19:00:00Z", "cost": 0}
    event.update(case.get("event", {}))
    configure_source(db, "case", "Evaluation fixture", "fixture://cases")
    import_records(db, "case", [event])
    profile = db.create_profile()
    query = EventQuery(start=case.get("query_start", "2026-10-26T16:00:00Z"), end=case.get("query_end", "2026-10-29T16:00:00Z"), interests=["career"], max_cost=case.get("max_cost"), free_food=case.get("food", False), buffer_minutes=case.get("buffer", 0))
    busy_events = [{"id": f"busy-{i}", "revision": 1, "title": "PRIVATE", "description": "", "source_url": "fixture://class", "start": f"2026-10-27T{a}:00Z", "end": f"2026-10-27T{b}:00Z"} for i, (a, b) in enumerate(case.get("busy", []))]
    raw = export_ics(busy_events, db.config.now()).encode()
    query.calendar_ref = upload_calendar(db, profile, raw, query.start, query.end, "UTC")["calendar_ref"]
    result = discover(db, profile, query, True)
    actual = bool(result["events"])
    return {"id": case["id"], "expected_feasible": case["expected"], "recommended": actual, "correct": actual == case["expected"], "excluded_counts": result["excluded_counts"]}


def evaluate_planner(directory):
    rows = []
    for case in load("planner_cases.json"):
        config = Config(data_dir=directory / case["id"], fixed_now="2026-10-26T16:00:00Z")
        rows.append(planner_case(Database(config), case))
    return {"cases": len(rows), "known_feasible": sum(r["expected_feasible"] for r in rows), "incorrect_feasible_recommendations": sum(r["recommended"] and not r["expected_feasible"] for r in rows), "missed_valid_options": sum(r["expected_feasible"] and not r["recommended"] for r in rows), "rows": rows}


def evaluate_retrieval(db):
    rows = []
    corpus = {s["id"]: s for s in json.loads((ROOT / "data/demo/documents.json").read_text())}
    for question in load("retrieval_questions.json"):
        for evidence in question["evidence"]:
            assert evidence["passage"] in corpus[question["source"]]["pages"][evidence["page"] - 1]
        result = search_docs(db, Search(query=question["query"], limit=3))
        expected = {(question["source"], e["page"]) for e in question["evidence"]}
        received = {(c["source_id"], c["page"]) for c in result["excerpts"]}
        rows.append({"id": question["id"], "split": question["split"], "kind": question["kind"], "recall_at_3": len(expected & received) / len(expected) if expected else None, "abstained": not result["excerpts"], "returned_evidence": [{"source": c["source_id"], "page": c["page"], "text": c["text"]} for c in result["excerpts"]]})
    metrics = {}
    for split in ("development", "held_out"):
        answerable = [r for r in rows if r["split"] == split and r["kind"] == "answerable"]
        unknown = [r for r in rows if r["split"] == split and r["kind"] == "unanswerable"]
        metrics[split] = {"answerable_count": len(answerable), "recall_at_3": statistics.mean(r["recall_at_3"] for r in answerable), "unanswerable_count": len(unknown), "unanswerable_abstention_rate": statistics.mean(r["abstained"] for r in unknown)}
    return {"backend": "demo_lexical", "questions": len(rows), "k": 3, "metrics": metrics, "rows": rows,
            "ground_truth_status": "Agent-authored, human-reviewable fixture annotations. No independent human validation; source-grouped split fixed before evaluation.",
            "answer_support": "Not measured. Generation disabled; excerpts are not policy conclusions. Ambiguous questions are recorded separately, without claiming resolution."}


def benchmark(db, samples=50):
    query = EventQuery(start="2026-10-26T16:00:00Z", end="2026-11-02T16:00:00Z", interests=["career"], max_cost=0)
    profile = db.create_profile()
    raw = (ROOT / "data/demo/classes.ics").read_bytes()
    query.calendar_ref = upload_calendar(db, profile, raw, query.start, query.end, "America/New_York")["calendar_ref"]
    search = Search(query="group study room", limit=3)
    durations = {"retrieval_ms": [], "planning_ms": [], "total_ms": []}
    first = {}
    for iteration in range(samples + 1):
        a = time.perf_counter()
        search_docs(db, search)
        b = time.perf_counter()
        discover(db, profile, query, True)
        c = time.perf_counter()
        values = {"retrieval_ms": (b - a) * 1000, "planning_ms": (c - b) * 1000, "total_ms": (c - a) * 1000}
        if iteration == 0:
            first = values
        else:
            for key, value in values.items():
                durations[key].append(value)
    return {"corpus": "8 fictional document pages/chunks, 6 events, recurring class fixture", "sample_count": samples,
            "state": "First call and subsequent warm calls; OS cache uncontrolled. This process already ingested/evaluated the corpus; not a cold-process measurement.",
            "first_call_ms": first, "warm_median_ms": {k: statistics.median(v) for k, v in durations.items()}, "raw_samples_ms": durations,
            "generation_ms": None, "generation_status": "disabled, not measured", "percentiles": "No p95 claim for this small workload."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=WORKLOAD / "results/offline.json")
    args = parser.parse_args()
    (ROOT / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="evaluation-", dir=ROOT / "tmp") as temp:
        directory = Path(temp)
        planner = evaluate_planner(directory / "planner")
        db = Database(Config(data_dir=directory / "retrieval", fixed_now="2026-10-26T16:00:00Z"))
        demo(db)
        result = {"provenance": provenance(), "planner": planner, "retrieval": evaluate_retrieval(db), "performance": benchmark(db), "user_impact": {"status": "unmeasured", "participants": 0, "time_savings": None}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "planner_cases": planner["cases"], "incorrect_feasible": planner["incorrect_feasible_recommendations"], "missed_valid": planner["missed_valid_options"], "retrieval": result["retrieval"]["metrics"], "warm_median_ms": result["performance"]["warm_median_ms"]}, indent=2))
    if planner["incorrect_feasible_recommendations"] or planner["missed_valid_options"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
