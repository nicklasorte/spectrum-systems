"""Tests for scripts/run_rq_next_24_01.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_rq_next_24_01.py"
TRACE_PATH = REPO_ROOT / "artifacts" / "rdx_runs" / "RQ-NEXT-24-01-artifact-trace.json"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "rq_next_24_01"
PUBLIC_ROOT = REPO_ROOT / "dashboard" / "public"

UMBRELLA_CHECKPOINTS = [f"umbrella-{idx}_checkpoint.json" for idx in range(1, 5)]


def _run_script() -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT_PATH)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_emits_umbrella_checkpoints_and_trace() -> None:
    _run_script()

    assert TRACE_PATH.is_file()
    for checkpoint in UMBRELLA_CHECKPOINTS:
        assert (ARTIFACT_ROOT / checkpoint).is_file()

    trace = _load_json(TRACE_PATH)
    assert trace["execution_mode"] == "SERIAL WITH HARD CHECKPOINTS"
    assert trace["umbrella_sequence"] == ["UMBRELLA-1", "UMBRELLA-2", "UMBRELLA-3", "UMBRELLA-4"]


def test_umbrella_one_recommendation_accuracy_artifacts() -> None:
    _run_script()

    taxonomy = _load_json(ARTIFACT_ROOT / "umbrella_1" / "nx_01_recommendation_failure_taxonomy.json")
    assert taxonomy["artifact_type"] == "recommendation_failure_taxonomy"
    assert taxonomy["classes"]

    registry = _load_json(ARTIFACT_ROOT / "umbrella_1" / "nx_02_recommendation_error_pattern_registry.json")
    assert "artifact_basis_missing" in registry["recurring_classes"]

    calibration = _load_json(ARTIFACT_ROOT / "umbrella_1" / "nx_03_confidence_recalibration_policy.json")
    assert calibration["policy_decision"] == "tighten"

    rollback = _load_json(ARTIFACT_ROOT / "umbrella_1" / "nx_04_recommendation_rollback_heuristic.json")
    assert rollback["rollback_state"] == "engaged"


def test_umbrella_two_operator_runtime_discipline_artifacts() -> None:
    _run_script()

    admissibility = _load_json(ARTIFACT_ROOT / "umbrella_2" / "nx_08_operator_action_admissibility_check.json")
    assert admissibility["admissibility"] == "admit"

    divergence = _load_json(ARTIFACT_ROOT / "umbrella_2" / "nx_10_operator_divergence_tracker.json")
    assert 0 <= divergence["divergence_rate"] <= 1

    closure = _load_json(ARTIFACT_ROOT / "umbrella_2" / "nx_12_action_result_closure_artifact.json")
    assert closure["closure_status"] == "auditable_closed_loop"


def test_umbrella_three_and_four_replay_and_governance_outputs() -> None:
    _run_script()

    simulation = _load_json(ARTIFACT_ROOT / "umbrella_3" / "nx_18_simulation_outcome_summary.json")
    assert simulation["replay_pressure_verdict"] == "pass_with_constraints"

    canary = _load_json(ARTIFACT_ROOT / "umbrella_4" / "nx_23_controlled_expansion_canary_gate.json")
    assert canary["gate_state"] == "allow_bounded_canary"
    assert canary["automatic_rollback_on_regression"] is True

    closeout = _load_json(ARTIFACT_ROOT / "umbrella_4" / "nx_24_next_cycle_governance_closeout.json")
    assert closeout["final_recommendation"] in {"tune", "validate", "canary", "hold"}


def test_publication_surfaces_match_generated_truth() -> None:
    _run_script()

    published_taxonomy = PUBLIC_ROOT / "rq_next_24_01__umbrella_1__nx_01_recommendation_failure_taxonomy.json"
    assert published_taxonomy.is_file()

    published_closeout = _load_json(PUBLIC_ROOT / "rq_next_24_01__umbrella_4__nx_24_next_cycle_governance_closeout.json")
    assert published_closeout["artifact_type"] == "next_cycle_governance_closeout"

    trace = _load_json(TRACE_PATH)
    assert trace["dashboard_publication"]["status"] == "pass"
    assert trace["final_success_conditions"]["canary_expansion_bounded_and_conservative"] is True
