"""Tests for scripts/run_rh_kernel_24_01.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_rh_kernel_24_01.py"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "rh_kernel_24_01"
TRACE_PATH = REPO_ROOT / "artifacts" / "rdx_runs" / "RH-KERNEL-24-01-artifact-trace.json"
PUBLIC_ROOT = REPO_ROOT / "dashboard" / "public"


def _run_script() -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT_PATH)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_script_emits_checkpoints_and_trace() -> None:
    _run_script()

    for index in range(1, 5):
        checkpoint = ARTIFACT_ROOT / f"umbrella-{index}_checkpoint.json"
        assert checkpoint.is_file()

    trace = _load_json(TRACE_PATH)
    assert trace["execution_mode"] == "SERIAL WITH HARD CHECKPOINTS"
    assert trace["umbrella_sequence"] == ["UMBRELLA-1", "UMBRELLA-2", "UMBRELLA-3", "UMBRELLA-4"]


def test_umbrella_one_reporting_artifacts_and_enforcement() -> None:
    _run_script()

    delivery = _load_json(ARTIFACT_ROOT / "umbrella_1" / "delivery_report.json")
    assert delivery["artifact_type"] == "delivery_report"
    assert delivery["canonical_json_authority"] is True

    review = _load_json(ARTIFACT_ROOT / "umbrella_1" / "review_report.json")
    assert review["artifact_type"] == "review_report"

    enforcement = _load_json(ARTIFACT_ROOT / "umbrella_1" / "rh_06_report_enforcement_result.json")
    assert enforcement["enforcement_decision"] == "pass"


def test_umbrella_two_readiness_and_truth_integrity_artifacts() -> None:
    _run_script()

    evidence = _load_json(ARTIFACT_ROOT / "umbrella_2" / "rh_07_evidence_depth_assessment.json")
    assert evidence["expansion_claim_depth"]["status"] == "fail"

    false_readiness = _load_json(ARTIFACT_ROOT / "umbrella_2" / "rh_09_false_readiness_detection_record.json")
    assert false_readiness["detector_result"] == "pass"

    truth_probe = _load_json(ARTIFACT_ROOT / "umbrella_2" / "rh_10_production_dashboard_truth_probe.json")
    assert truth_probe["divergence_count"] == 0


def test_umbrella_three_learning_quality_outputs() -> None:
    _run_script()

    experiment = _load_json(ARTIFACT_ROOT / "umbrella_3" / "rh_13_experiment_record.json")
    assert experiment["artifact_type"] == "experiment_record"

    realism = _load_json(ARTIFACT_ROOT / "umbrella_3" / "rh_16_execution_realism_assessment.json")
    assert realism["green_low_value_detection"] == "pass"

    stability = _load_json(ARTIFACT_ROOT / "umbrella_3" / "rh_18_stability_index_artifact.json")
    assert 0 <= stability["cross_cycle_stability_index"] <= 1


def test_umbrella_four_governance_debt_and_system_map_projection() -> None:
    _run_script()

    debt = _load_json(ARTIFACT_ROOT / "umbrella_4" / "rh_19_governance_debt_register.json")
    assert debt["debt_items"]

    explainability = _load_json(ARTIFACT_ROOT / "umbrella_4" / "rh_22_explainability_bundle.json")
    assert explainability["projection_source"] == "interpreted artifacts only"

    map_projection = _load_json(ARTIFACT_ROOT / "umbrella_4" / "rh_24_system_map_projection_bundle.json")
    assert map_projection["projection_constraints"]["semantic_invention"] is False


def test_required_reporting_and_registry_alignment_non_empty_and_published() -> None:
    _run_script()

    required_paths = [
        ARTIFACT_ROOT / "umbrella_1" / "delivery_report.json",
        ARTIFACT_ROOT / "umbrella_1" / "review_report.json",
        ARTIFACT_ROOT / "checkpoint_summary.json",
        ARTIFACT_ROOT / "closeout_artifact.json",
        ARTIFACT_ROOT / "registry_alignment_result.json",
    ]
    for path in required_paths:
        assert path.is_file()
        assert path.stat().st_size > 2

    alignment = _load_json(ARTIFACT_ROOT / "registry_alignment_result.json")
    assert all(status == "pass" for status in alignment["cross_checks"].values())

    published = PUBLIC_ROOT / "rh_kernel_24_01__umbrella_1__delivery_report.json"
    assert published.is_file()

    closeout = _load_json(ARTIFACT_ROOT / "closeout_artifact.json")
    assert closeout["final_success_conditions"]["canonical_reports_exist_and_strong"] is True
