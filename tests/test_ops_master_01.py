"""Tests for scripts/run_ops_master_01.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_ops_master_01.py"
TRACE_PATH = REPO_ROOT / "artifacts" / "rdx_runs" / "OPS-MASTER-01-artifact-trace.json"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "ops_master_01"

REQUIRED_ARTIFACT_TYPES = {
    "current_run_state_record",
    "current_bottleneck_record",
    "deferred_item_register",
    "hard_gate_status_record",
    "aex_evidence_completeness_enforcement",
    "tpa_lineage_completeness_enforcement",
    "pre_pqx_contract_readiness_artifact",
    "failure_shift_classifier",
    "first_pass_quality_artifact",
    "repair_loop_reduction_tracker",
    "repeated_failure_memory_registry",
    "fix_outcome_registry",
    "deferred_return_tracker",
    "drift_trend_continuity_artifact",
    "adoption_outcome_history",
    "policy_change_outcome_tracker",
    "canonical_roadmap_state_artifact",
    "hard_gate_tracker_artifact",
    "maturity_phase_tracker",
    "bottleneck_tracker",
    "roadmap_delta_artifact",
    "constitutional_drift_checker_result",
    "roadmap_alignment_validator_result",
    "serial_bundle_validator_result",
}


def _run_script() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_script_emits_required_artifacts_and_trace() -> None:
    _run_script()
    assert TRACE_PATH.is_file()

    for artifact_type in REQUIRED_ARTIFACT_TYPES:
        path = ARTIFACT_ROOT / f"{artifact_type}.json"
        assert path.is_file(), f"missing artifact: {artifact_type}"


def test_trace_records_serial_umbrella_sequence_and_fail_closed_status() -> None:
    _run_script()
    trace = _load_json(TRACE_PATH)

    assert trace["umbrella_sequence"] == [
        "VISIBILITY_LAYER",
        "SHIFT_LEFT_HARDENING_LAYER",
        "OPERATIONAL_MEMORY_LAYER",
        "ROADMAP_STATE_LAYER",
        "CONSTITUTION_PROTECTION_LAYER",
    ]
    assert trace["fail_open_detected"] is False
    assert trace["fail_closed_checks"] == {
        "missing_artifacts": "pass",
        "invalid_schema": "pass",
        "broken_lineage": "pass",
        "authority_misuse": "pass",
    }
