"""Tests for scripts/run_repair_standardization_24_01.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_repair_standardization_24_01.py"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "repair_standardization_24_01"
TRACE_PATH = REPO_ROOT / "artifacts" / "rdx_runs" / "REPAIR-STANDARDIZATION-24-01-artifact-trace.json"


def _run_script() -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT_PATH)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_script_emits_all_umbrella_checkpoints_and_trace() -> None:
    _run_script()

    for index in range(1, 5):
        checkpoint = ARTIFACT_ROOT / f"umbrella-{index}_checkpoint.json"
        assert checkpoint.is_file()

    trace = _load_json(TRACE_PATH)
    assert trace["execution_mode"] == "SERIAL WITH HARD CHECKPOINTS"
    assert trace["umbrella_sequence"] == ["UMBRELLA-1", "UMBRELLA-2", "UMBRELLA-3", "UMBRELLA-4"]


def test_umbrella_1_repair_standardization_outputs() -> None:
    _run_script()

    fre_contract = _load_json(ARTIFACT_ROOT / "umbrella_1" / "repair_class_contract_pack.json")
    assert fre_contract["owner"] == "FRE"

    tpa_policy = _load_json(ARTIFACT_ROOT / "umbrella_1" / "repair_class_scope_policy.json")
    assert tpa_policy["owner"] == "TPA"
    assert tpa_policy["policy_scope_only"] is True

    pqx_exec = _load_json(ARTIFACT_ROOT / "umbrella_1" / "parameterized_repair_execution_record.json")
    assert pqx_exec["owner"] == "PQX"
    assert pqx_exec["lineage"] == ["AEX", "TLC", "TPA", "PQX"]


def test_umbrella_2_replay_confidence_and_closure_tightening_outputs() -> None:
    _run_script()

    confidence_record = _load_json(ARTIFACT_ROOT / "umbrella_2" / "repair_replay_confidence_record.json")
    assert confidence_record["owner"] == "PRG"
    assert confidence_record["authoritative"] is False

    sel_gate = _load_json(ARTIFACT_ROOT / "umbrella_2" / "weak_repair_replay_enforcement_result.json")
    assert sel_gate["owner"] == "SEL"
    assert sel_gate["fail_closed"] is True

    cde_decision = _load_json(ARTIFACT_ROOT / "umbrella_2" / "repair_confidence_closure_decision.json")
    assert cde_decision["owner"] == "CDE"


def test_umbrella_3_debt_liquidation_outputs() -> None:
    _run_script()

    debt_plan = _load_json(ARTIFACT_ROOT / "umbrella_3" / "repair_debt_liquidation_plan.json")
    assert debt_plan["owner"] == "PRG"
    assert debt_plan["authoritative"] is False

    debt_batch = _load_json(ARTIFACT_ROOT / "umbrella_3" / "repair_debt_batch_artifact.json")
    assert debt_batch["owner"] == "RDX"
    assert debt_batch["sequencing_only"] is True

    escalation = _load_json(ARTIFACT_ROOT / "umbrella_3" / "repair_debt_escalation_result.json")
    assert escalation["owner"] == "SEL"


def test_umbrella_4_closure_proof_and_promotion_restraint_outputs() -> None:
    _run_script()

    projection = _load_json(ARTIFACT_ROOT / "umbrella_4" / "closure_proof_projection_bundle.json")
    assert projection["owner"] == "MAP"
    assert projection["projection_only"] is True
    assert projection["semantics_invented"] is False

    recommendation = _load_json(ARTIFACT_ROOT / "umbrella_4" / "promotion_restraint_recommendation.json")
    assert recommendation["owner"] == "PRG"
    assert recommendation["authoritative"] is False

    promotion_decision = _load_json(ARTIFACT_ROOT / "umbrella_4" / "repair_aware_promotion_readiness_decision.json")
    assert promotion_decision["owner"] == "CDE"


def test_required_reporting_cross_checks_and_closeout_are_non_empty() -> None:
    _run_script()

    required_paths = [
        ARTIFACT_ROOT / "umbrella_1" / "canonical_delivery_report_artifact.json",
        ARTIFACT_ROOT / "umbrella_1" / "canonical_review_report_artifact.json",
        ARTIFACT_ROOT / "checkpoint_summary.json",
        ARTIFACT_ROOT / "registry_alignment_result.json",
        ARTIFACT_ROOT / "closeout_artifact.json",
    ]

    for path in required_paths:
        assert path.is_file()
        assert path.stat().st_size > 2

    alignment = _load_json(ARTIFACT_ROOT / "registry_alignment_result.json")
    assert len(alignment["cross_checks"]) == 14
    assert all(status == "pass" for status in alignment["cross_checks"].values())

    closeout = _load_json(ARTIFACT_ROOT / "closeout_artifact.json")
    assert all(closeout["final_success_conditions"].values())
