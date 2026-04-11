"""Tests for scripts/run_rq_master_36_01.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_rq_master_36_01.py"
TRACE_PATH = REPO_ROOT / "artifacts" / "rdx_runs" / "RQ-MASTER-36-01-artifact-trace.json"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "rq_master_36_01"
PUBLIC_ROOT = REPO_ROOT / "dashboard" / "public"

UMBRELLA_CHECKPOINTS = [f"umbrella-{idx}_checkpoint.json" for idx in range(1, 10)]
REQUIRED_PUBLIC = [
    "dashboard_freshness_status.json",
    "cycle_comparator_03_05.json",
    "next_action_recommendation_record.json",
    "next_action_outcome_record.json",
    "recommendation_accuracy_tracker.json",
    "confidence_calibration_artifact.json",
    "stuck_loop_detector.json",
    "error_budget_enforcement_outcome.json",
    "recurrence_prevention_status.json",
    "judgment_application_artifact.json",
    "readiness_to_expand_validator.json",
    "operator_trust_closeout_artifact.json",
    "operator_surface_snapshot_export.json",
    "deploy_ci_truth_gate.json",
]


def _run_script() -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT_PATH)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_script_emits_all_umbrella_checkpoints_and_trace() -> None:
    _run_script()

    assert TRACE_PATH.is_file()
    for checkpoint in UMBRELLA_CHECKPOINTS:
        assert (ARTIFACT_ROOT / checkpoint).is_file()


def test_delivery_contract_and_publication_gate_are_present() -> None:
    _run_script()

    checkpoint = _load_json(ARTIFACT_ROOT / "umbrella-1_checkpoint.json")
    assert checkpoint["checkpoint_status"] == "pass"
    assert "delivery_contract" in checkpoint
    assert "certification_readiness_impact" in checkpoint["delivery_contract"]

    trace = _load_json(TRACE_PATH)
    assert trace["execution_mode"] == "SERIAL WITH HARD CHECKPOINTS"
    assert trace["dashboard_publication"]["freshness_state"] == "explicit_artifact"


def test_required_public_operator_artifacts_are_published() -> None:
    _run_script()

    for filename in REQUIRED_PUBLIC:
        assert (PUBLIC_ROOT / filename).is_file()

    gate = _load_json(PUBLIC_ROOT / "deploy_ci_truth_gate.json")
    assert gate["result"] == "pass"
