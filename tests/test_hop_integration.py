from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from spectrum_systems.modules.hop.evaluator import evaluate_candidate
from spectrum_systems.modules.hop.experience_store import ExperienceStore
from spectrum_systems.modules.hop.frontier import build_frontier
from spectrum_systems.modules.hop.safety_checks import run_safety_checks
from spectrum_systems.modules.hop.validator import validate_candidate


def _now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _candidate_artifact(candidate_file: Path) -> dict:
    return {
        "artifact_type": "harness_candidate",
        "artifact_id": "hop-candidate-1",
        "schema_ref": "hop/harness_candidate.schema.json@1.0.0",
        "trace": {"trace_id": "trace-hop-1", "timestamp": _now(), "steps": [{"name": "candidate", "status": "pass"}]},
        "content_hash": _hash({"candidate_id": "cand-1"}),
        "created_at": _now(),
        "candidate_id": "cand-1",
        "code_ref": str(candidate_file),
        "interface": {"entrypoint": "HarnessCandidate", "required_methods": ["run"]},
        "cost": 0.1,
        "latency_ms": 10.0,
    }


def test_integration_baseline_eval_store_query_frontier(tmp_path: Path) -> None:
    schema_root = Path(__file__).resolve().parents[1] / "contracts" / "schemas" / "hop"
    eval_path = Path(__file__).resolve().parents[1] / "contracts" / "evals" / "hop" / "eval_cases.v1.json"

    candidate_file = tmp_path / "candidate_ok.py"
    candidate_file.write_text(
        "class HarnessCandidate:\n"
        "    def run(self, transcript):\n"
        "        return {'artifact_type': 'faq_cluster_artifact', 'faq_items': [{'question': transcript, 'answer': transcript}], 'faq_count': 1}\n",
        encoding="utf-8",
    )
    candidate = _candidate_artifact(candidate_file)

    candidate_check = validate_candidate(candidate, schema_root=schema_root)
    assert candidate_check["status"] == "pass"

    safety = run_safety_checks(candidate_artifact=candidate, eval_set_path=eval_path, schema_root=schema_root)
    assert safety["status"] == "pass"

    eval_out = evaluate_candidate(candidate_artifact=candidate, eval_set_path=eval_path, trace_id="trace-hop-1", schema_root=schema_root)
    assert eval_out["eval_summary_artifact"]["run_count"] >= 20

    store = ExperienceStore(tmp_path / "store", schema_root=schema_root)
    for run_artifact in eval_out["eval_result_artifacts"]:
        store.append(run_artifact, "harness_run")
    store.append(eval_out["eval_summary_artifact"], "harness_score")

    scores = list(store.iter_records(schema="harness_score", min_score=0.0, max_score=1.0))
    assert len(scores) == 1

    frontier = build_frontier(
        [
            {
                "candidate_id": "cand-1",
                "score": eval_out["eval_summary_artifact"]["score"],
                "cost": eval_out["eval_summary_artifact"].get("cost", 0.1),
                "latency": eval_out["eval_summary_artifact"]["latency_ms"],
                "trace_completeness": 1.0,
                "eval_coverage": eval_out["eval_summary_artifact"]["coverage"],
            }
        ],
        trace_id="trace-hop-1",
        schema_root=schema_root,
    )
    store.append(frontier, "harness_frontier")
    assert len(list(store.iter_records(schema="harness_frontier"))) == 1


def test_failure_paths_missing_schema_invalid_harness_eval_tamper_trace_gap(tmp_path: Path) -> None:
    eval_path = Path(__file__).resolve().parents[1] / "contracts" / "evals" / "hop" / "eval_cases.v1.json"

    bad_candidate_file = tmp_path / "candidate_bad.py"
    bad_candidate_file.write_text("class NotHarness: pass\n", encoding="utf-8")
    candidate = _candidate_artifact(bad_candidate_file)

    with pytest.raises(Exception):
        validate_candidate(candidate, schema_root=tmp_path / "missing_schema_dir")

    # missing schema
    from spectrum_systems.modules.hop.validator import validate_artifact_shape

    with pytest.raises(Exception):
        validate_artifact_shape({}, "harness_score", schema_root=tmp_path / "missing_schema_dir")

    # eval tampering
    tampered_eval = tmp_path / "eval_tampered.json"
    tampered_eval.write_text('{"cases": []}', encoding="utf-8")
    with pytest.raises(Exception):
        evaluate_candidate(candidate_artifact=candidate, eval_set_path=tampered_eval, trace_id="trace-x", schema_root=tmp_path / "missing_schema_dir")

    # trace missing in store append
    schema_root = Path(__file__).resolve().parents[1] / "contracts" / "schemas" / "hop"
    store = ExperienceStore(tmp_path / "store", schema_root=schema_root)
    bad_trace_score = {
        "artifact_type": "harness_score",
        "artifact_id": "score-bad",
        "schema_ref": "hop/harness_score.schema.json@1.0.0",
        "content_hash": _hash({"x": 1}),
        "created_at": _now(),
        "candidate_id": "cand-x",
        "score": 0.1,
        "coverage": 0.1,
        "run_count": 1,
    }
    with pytest.raises(Exception):
        store.append(bad_trace_score, "harness_score")

    # safety block
    candidate_leak = tmp_path / "candidate_leak.py"
    candidate_leak.write_text("# golden-01 leak\nclass HarnessCandidate:\n    def run(self, transcript):\n        return {'artifact_type': 'faq_cluster_artifact', 'faq_items': []}\n", encoding="utf-8")
    leak_artifact = _candidate_artifact(candidate_leak)
    safety = run_safety_checks(candidate_artifact=leak_artifact, eval_set_path=eval_path, schema_root=schema_root)
    assert safety["status"] == "block"
