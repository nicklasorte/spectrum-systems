"""End-to-end integration: candidate -> validator -> safety -> evaluator -> store -> query -> frontier."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.hop import baseline_harness
from spectrum_systems.modules.hop.evaluator import EvalSet, evaluate_candidate
from spectrum_systems.modules.hop.experience_store import ExperienceStore, HopStoreError
from spectrum_systems.modules.hop.frontier import build_frontier_artifact
from spectrum_systems.modules.hop.safety_checks import scan_candidate
from spectrum_systems.modules.hop.schemas import validate_hop_artifact
from spectrum_systems.modules.hop.validator import validate_candidate
from tests.hop.conftest import make_baseline_candidate


def test_pipeline_end_to_end(store: ExperienceStore, eval_set: EvalSet, eval_cases) -> None:
    candidate = make_baseline_candidate()

    ok_validator, validator_failures = validate_candidate(candidate)
    assert ok_validator and validator_failures == []

    ok_safety, safety_failures = scan_candidate(candidate, eval_cases)
    assert ok_safety and safety_failures == []

    store.write_artifact(candidate)

    result = evaluate_candidate(
        candidate_payload=candidate,
        runner=baseline_harness.run,
        eval_set=eval_set,
        store=store,
    )
    assert result["run"]["status"] == "completed"

    # Confirm the score is queryable from the store.
    score_records = list(store.iter_index(artifact_type="hop_harness_score"))
    assert len(score_records) == 1
    score_payload = store.read_artifact("hop_harness_score", score_records[0]["artifact_id"])
    validate_hop_artifact(score_payload, "hop_harness_score")

    # And that the frontier artifact validates.
    frontier_payload = build_frontier_artifact(
        [score_payload], frontier_id="frontier_integration"
    )
    validate_hop_artifact(frontier_payload, "hop_harness_frontier")
    assert frontier_payload["considered_count"] == 1


def test_invalid_candidate_never_reaches_evaluator(store, eval_set, eval_cases) -> None:
    bad = {"artifact_type": "hop_harness_candidate", "candidate_id": "x"}
    ok, failures = validate_candidate(bad)
    assert not ok
    # Validator must produce a structured failure artifact; the store accepts it.
    store.write_artifact(failures[0])
    failure_records = list(store.list_failures(severity="reject"))
    assert any(
        rec["fields"]["failure_class"] == "schema_violation" for rec in failure_records
    )


def test_safety_check_block_prevents_eval(store, eval_set, eval_cases) -> None:
    leaky = make_baseline_candidate(
        code_source=(
            "def run(t):\n"
            "    if 'hop_case_golden_one_qa' in t.get('transcript_id', ''):\n"
            "        return {}\n"
            "    return {}\n"
        )
    )
    ok_safety, failures = scan_candidate(leaky, eval_cases)
    assert not ok_safety
    assert any(f["failure_class"] == "eval_dataset_leakage" for f in failures)
    # Persist the failure so downstream queries see it.
    for f in failures:
        store.write_artifact(f)
    blocked = list(store.list_failures())
    assert blocked


def test_replay_compatibility_same_candidate_twice(store: ExperienceStore, eval_set) -> None:
    """A candidate stored twice must remain idempotent; runs are independent."""
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    store.write_artifact(candidate)  # idempotent
    candidates = list(store.list_candidates())
    assert len(candidates) == 1

    r1 = evaluate_candidate(
        candidate_payload=candidate,
        runner=baseline_harness.run,
        eval_set=eval_set,
        store=store,
    )
    r2 = evaluate_candidate(
        candidate_payload=candidate,
        runner=baseline_harness.run,
        eval_set=eval_set,
        store=store,
    )
    # Distinct run artifacts.
    assert r1["run"]["artifact_id"] != r2["run"]["artifact_id"]
    runs = list(store.list_runs(candidate_id=candidate["candidate_id"]))
    assert len(runs) == 2
