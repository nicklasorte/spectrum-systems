"""Tests for scripts/run_shift_left_memory_24_01.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_shift_left_memory_24_01.py"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "shift_left_memory_24_01"
TRACE_PATH = REPO_ROOT / "artifacts" / "rdx_runs" / "SHIFT-LEFT-MEMORY-24-01-artifact-trace.json"


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


def test_umbrella_1_shift_left_hardening_outputs() -> None:
    _run_script()

    packet = _load_json(ARTIFACT_ROOT / "umbrella_1" / "first_pass_failure_signature_packet.json")
    assert packet["owner"] == "RIL"
    assert packet["interpretation_boundary"] == "interpretation_only"

    enrichment = _load_json(ARTIFACT_ROOT / "umbrella_1" / "admission_risk_enrichment_record.json")
    assert enrichment["owner"] == "AEX"
    assert enrichment["authority_boundary"] == "admission_enrichment_only"

    enforcement = _load_json(ARTIFACT_ROOT / "umbrella_1" / "shift_left_hardening_enforcement_result.json")
    assert enforcement["owner"] == "SEL"


def test_umbrella_2_memory_activation_outputs() -> None:
    _run_script()

    retrieval = _load_json(ARTIFACT_ROOT / "umbrella_2" / "repair_memory_retrieval_score_record.json")
    assert retrieval["owner"] == "PRG"
    assert retrieval["authoritative"] is False

    plan = _load_json(ARTIFACT_ROOT / "umbrella_2" / "memory_backed_repair_plan.json")
    assert plan["owner"] == "FRE"
    assert plan["memory_assisted"] is True

    batch = _load_json(ARTIFACT_ROOT / "umbrella_2" / "memory_priority_batch_artifact.json")
    assert batch["owner"] == "RDX"


def test_umbrella_3_first_pass_quality_outputs() -> None:
    _run_script()

    validation = _load_json(ARTIFACT_ROOT / "umbrella_3" / "pre_execution_validation_bundle_record.json")
    assert validation["owner"] == "PQX"

    review = _load_json(ARTIFACT_ROOT / "umbrella_3" / "failed_first_pass_review_compression_record.json")
    assert review["owner"] == "RQX"

    trend = _load_json(ARTIFACT_ROOT / "umbrella_3" / "first_pass_quality_trend_artifact.json")
    assert trend["owner"] == "PRG"
    assert trend["trend"] in {"improving", "flat", "regressing"}


def test_umbrella_4_repair_pressure_closure_and_projection_outputs() -> None:
    _run_script()

    decision = _load_json(ARTIFACT_ROOT / "umbrella_4" / "repair_pressure_closure_decision.json")
    assert decision["owner"] == "CDE"

    projection = _load_json(ARTIFACT_ROOT / "umbrella_4" / "repair_pressure_projection_bundle.json")
    assert projection["owner"] == "MAP"
    assert projection["projection_only"] is True
    assert projection["semantics_invented"] is False

    recommendation = _load_json(ARTIFACT_ROOT / "umbrella_4" / "hardening_focus_recommendation.json")
    assert recommendation["owner"] == "PRG"
    assert recommendation["authoritative"] is False


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
    assert len(alignment["cross_checks"]) == 16
    assert all(status == "pass" for status in alignment["cross_checks"].values())

    closeout = _load_json(ARTIFACT_ROOT / "closeout_artifact.json")
    assert all(closeout["final_success_conditions"].values())
