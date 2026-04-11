"""Tests for scripts/run_certification_judgment_40_explicit.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_certification_judgment_40_explicit.py"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "certification_judgment_40_explicit"
TRACE_PATH = REPO_ROOT / "artifacts" / "rdx_runs" / "CERTIFICATION-JUDGMENT-40-EXPLICIT-artifact-trace.json"

EXPECTED_OWNER_BY_ARTIFACT = {
    "hard_gate_evidence_inventory_packet": "RIL",
    "certification_risk_admission_record": "AEX",
    "certification_requirement_scope_policy": "TPA",
    "certification_probe_execution_bundle": "PQX",
    "certification_probe_review_verdict": "RQX",
    "certification_evidence_enforcement_result": "SEL",
    "certification_readiness_decision": "CDE",
    "certification_operator_proof_bundle": "MAP",
    "judgment_extraction_interpretation_packet": "RIL",
    "judgment_candidate_register": "PRG",
    "judgment_policy_candidate_set": "PRG",
    "judgment_rationale_projection_bundle": "MAP",
    "judgment_reuse_scorecard": "PRG",
    "judgment_priority_batch_artifact": "RDX",
    "judgment_umbrella_sequencing_plan": "RDX",
    "judgment_sensitive_readiness_decision": "CDE",
    "evidence_debt_interpretation_packet": "RIL",
    "evidence_debt_register": "PRG",
    "evidence_debt_priority_stack": "PRG",
    "evidence_debt_escalation_result": "SEL",
    "observability_completeness_packet": "RIL",
    "observability_debt_register": "PRG",
    "observability_probe_execution_bundle": "PQX",
    "observability_completeness_guard_result": "SEL",
    "drift_pressure_interpretation_packet": "RIL",
    "drift_pressure_scoreboard": "PRG",
    "drift_freeze_candidate_guard_result": "SEL",
    "drift_hold_decision": "CDE",
    "certification_regression_replay_bundle": "PQX",
    "certification_regression_review_tightening_record": "RQX",
    "certification_regression_enforcement_result": "SEL",
    "regression_remediation_priority_recommendation": "PRG",
    "operator_closure_topology_bundle": "MAP",
    "stale_proof_interpretation_packet": "RIL",
    "stale_proof_operator_guard_result": "SEL",
    "operator_ambiguity_tracker": "PRG",
    "promotion_restraint_recommendation": "PRG",
    "promotion_closure_decision": "CDE",
    "promotion_proof_guard_result": "SEL",
    "certification_judgment_program_closeout": "PRG",
}


def _run_script() -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT_PATH)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_script_generates_required_artifacts_and_trace() -> None:
    _run_script()

    for artifact in EXPECTED_OWNER_BY_ARTIFACT:
        path = ARTIFACT_ROOT / f"{artifact}.json"
        assert path.is_file(), f"missing {artifact}"

    for name in ["delivery_report", "review_report", "checkpoint_summary", "registry_alignment_result"]:
        assert (ARTIFACT_ROOT / f"{name}.json").is_file()

    trace = _load_json(TRACE_PATH)
    assert trace["execution_mode"] == "STRICT SERIAL WITH HARD CHECKPOINTS"
    assert len(trace["step_sequence"]) == 40


def test_ownership_boundaries_map_exactly_one_owner_per_step() -> None:
    _run_script()

    for artifact, owner in EXPECTED_OWNER_BY_ARTIFACT.items():
        payload = _load_json(ARTIFACT_ROOT / f"{artifact}.json")
        assert payload["owner"] == owner
        assert payload["authority_boundaries_respected"] is True


def test_ten_checkpoints_include_required_global_validation_rules() -> None:
    _run_script()

    for checkpoint_idx in range(1, 11):
        checkpoint = _load_json(ARTIFACT_ROOT / f"checkpoint-{checkpoint_idx}.json")
        validation = checkpoint["validation"]
        assert checkpoint["checkpoint_status"] == "pass"
        assert checkpoint["stop_on_failure"] is True
        assert validation["tests"]["status"] == "pass"
        assert validation["schema_validation"]["status"] == "pass"
        assert validation["registry_alignment"]["status"] == "pass"
        assert validation["artifact_presence"]["status"] == "pass"
        assert validation["fail_closed_behavior"]["status"] == "pass"


def test_registry_alignment_contains_all_required_cross_checks() -> None:
    _run_script()

    registry = _load_json(ARTIFACT_ROOT / "registry_alignment_result.json")
    cross_checks = registry["cross_checks"]

    assert len(cross_checks) == 14
    assert all(value == "pass" for value in cross_checks.values())
