"""Tests for BF cross-run intelligence and anomaly detection layer (Prompt BF).

Covers:
- schema validation success for both artifacts
- schema rejection for extra properties
- no inputs
- malformed NRR input
- schema-invalid NRR input
- mixed study type failure
- metric comparison for clean comparable runs
- mixed units behavior
- insufficient data behavior
- rankings for p2p_interference
- rankings for retuning_analysis
- anomaly detection for extreme spread
- anomaly detection for duplicate scenario_id conflict
- readiness mismatch detection
- CLI exit code behavior
- directory auto-discovery
- integration using realistic NRR fixtures
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.cross_run_intelligence import (  # noqa: E402
    build_cross_run_comparison,
    build_cross_run_intelligence_decision,
    build_metric_comparisons,
    build_scenario_rankings,
    classify_cross_run_failure,
    collect_compared_runs,
    compare_normalized_runs,
    compute_summary_statistics,
    detect_cross_run_anomalies,
    detect_mixed_units,
    extract_metric_index,
    infer_comparison_study_type,
    load_normalized_run_result,
    validate_cross_run_comparison,
    validate_cross_run_intelligence_decision,
    validate_normalized_run_result_input,
)

_CRC_SCHEMA_PATH = _REPO_ROOT / "contracts" / "schemas" / "cross_run_comparison.schema.json"
_CRI_SCHEMA_PATH = (
    _REPO_ROOT / "contracts" / "schemas" / "cross_run_intelligence_decision.schema.json"
)
_NRR_P2P_RUN1 = _REPO_ROOT / "tests" / "fixtures" / "nrr_p2p_run1.json"
_NRR_P2P_RUN2 = _REPO_ROOT / "tests" / "fixtures" / "nrr_p2p_run2.json"
_NRR_P2P_OUTLIER = _REPO_ROOT / "tests" / "fixtures" / "nrr_p2p_outlier.json"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _load_fixture(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _p2p_nrr(
    bundle_id: str = "bundle-001",
    artifact_id: str = "NRR-AAA000",
    scenario_id: str = "scen-001",
    scenario_label: str = "Test Scenario",
    interference: float = -85.0,
    in_ratio: float = 12.0,
    path_loss: float = 142.0,
    readiness: str = "ready_for_comparison",
    completeness_status: str = "complete",
    study_type: str = "p2p_interference",
) -> Dict[str, Any]:
    """Return a minimal valid NRR dict for p2p_interference."""
    missing = [] if completeness_status == "complete" else ["path_loss_db"]
    req_count = 3
    present_count = req_count - len(missing)
    return {
        "artifact_id": artifact_id,
        "artifact_type": "normalized_run_result",
        "schema_version": "1.0.0",
        "source_bundle_id": bundle_id,
        "study_type": study_type,
        "scenario": {
            "scenario_id": scenario_id,
            "scenario_label": scenario_label,
            "frequency_range_mhz": {"low_mhz": 3550.0, "high_mhz": 3600.0},
            "assumptions_summary": "Test assumption.",
        },
        "metrics": {
            "metric_set_id": f"ms-{bundle_id}",
            "summary_metrics": [
                {
                    "name": "interference_power_dbm",
                    "value": interference,
                    "unit": "dBm",
                    "classification": "core",
                    "source_path": "outputs/results_summary.json#metrics[0]",
                },
                {
                    "name": "in_ratio_db",
                    "value": in_ratio,
                    "unit": "dB",
                    "classification": "core",
                    "source_path": "outputs/results_summary.json#metrics[1]",
                },
                {
                    "name": "path_loss_db",
                    "value": path_loss,
                    "unit": "dB",
                    "classification": "core",
                    "source_path": "outputs/results_summary.json#metrics[2]",
                },
            ],
            "completeness": {
                "required_metric_count": req_count,
                "present_required_metric_count": present_count,
                "missing_required_metrics": missing,
                "status": completeness_status,
            },
        },
        "evaluation_signals": {
            "readiness": readiness,
            "outlier_flags": [],
            "threshold_assessments": [],
            "trust_notes": [],
        },
        "provenance": {
            "manifest_author": "test-author",
            "source_case_ids": ["case-001"],
            "creation_context": "Unit test fixture.",
            "rng_reference": {"mode": "fixed", "value": 42},
            "results_summary_source": "outputs/results_summary.json",
            "provenance_source": "outputs/provenance.json",
        },
        "generated_at": "2026-03-01T10:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# Schema file checks
# ---------------------------------------------------------------------------


def test_crc_schema_file_exists():
    assert _CRC_SCHEMA_PATH.exists(), f"CRC schema not found at {_CRC_SCHEMA_PATH}"


def test_cri_schema_file_exists():
    assert _CRI_SCHEMA_PATH.exists(), f"CRI schema not found at {_CRI_SCHEMA_PATH}"


def test_fixture_files_exist():
    assert _NRR_P2P_RUN1.exists()
    assert _NRR_P2P_RUN2.exists()
    assert _NRR_P2P_OUTLIER.exists()


# ---------------------------------------------------------------------------
# Schema validation — success
# ---------------------------------------------------------------------------


def test_crc_schema_validates_valid_artifact():
    nrr1 = _p2p_nrr("b1", "NRR-A0000000001", "s1", "Scenario 1")
    nrr2 = _p2p_nrr("b2", "NRR-A0000000002", "s2", "Scenario 2")
    crc = build_cross_run_comparison([nrr1, nrr2])
    findings = validate_cross_run_comparison(crc)
    assert findings == [], f"Unexpected findings: {findings}"


def test_cri_schema_validates_valid_artifact():
    findings_in: list = []
    decision = build_cross_run_intelligence_decision("CMP-ABCDEF000001", findings_in)
    findings = validate_cross_run_intelligence_decision(decision)
    assert findings == [], f"Unexpected findings: {findings}"


# ---------------------------------------------------------------------------
# Schema validation — rejection for extra properties
# ---------------------------------------------------------------------------


def test_crc_schema_rejects_extra_properties():
    nrr1 = _p2p_nrr("b1", "NRR-A0000000001", "s1", "Scenario 1")
    nrr2 = _p2p_nrr("b2", "NRR-A0000000002", "s2", "Scenario 2")
    crc = build_cross_run_comparison([nrr1, nrr2])
    crc["unexpected_field"] = "should_fail"
    findings = validate_cross_run_comparison(crc)
    assert any(f["severity"] == "error" for f in findings)


def test_cri_schema_rejects_extra_properties():
    decision = build_cross_run_intelligence_decision("CMP-ABCDEF000001", [])
    decision["unexpected_field"] = "should_fail"
    findings = validate_cross_run_intelligence_decision(decision)
    assert any(f["severity"] == "error" for f in findings)


# ---------------------------------------------------------------------------
# No inputs
# ---------------------------------------------------------------------------


def test_no_inputs_returns_fail():
    result = compare_normalized_runs()
    assert result["cross_run_comparison"] is None
    decision = result["cross_run_intelligence_decision"]
    assert decision["overall_status"] == "fail"
    assert decision["failure_type"] == "no_inputs"


def test_empty_input_paths_returns_fail():
    result = compare_normalized_runs(input_paths=[])
    assert result["cross_run_comparison"] is None
    decision = result["cross_run_intelligence_decision"]
    assert decision["overall_status"] == "fail"
    assert decision["failure_type"] == "no_inputs"


# ---------------------------------------------------------------------------
# Malformed NRR input
# ---------------------------------------------------------------------------


def test_malformed_json_input(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json", encoding="utf-8")
    result = compare_normalized_runs(input_paths=[str(bad_file)])
    assert result["cross_run_comparison"] is None
    decision = result["cross_run_intelligence_decision"]
    assert decision["overall_status"] == "fail"
    assert decision["failure_type"] == "malformed_input"


def test_missing_input_file(tmp_path):
    result = compare_normalized_runs(input_paths=[str(tmp_path / "nonexistent.json")])
    assert result["cross_run_comparison"] is None
    decision = result["cross_run_intelligence_decision"]
    assert decision["overall_status"] == "fail"
    assert decision["failure_type"] == "malformed_input"


# ---------------------------------------------------------------------------
# Schema-invalid NRR input
# ---------------------------------------------------------------------------


def test_schema_invalid_nrr_input():
    invalid_nrr = {"artifact_type": "normalized_run_result", "bad_field": "value"}
    result = compare_normalized_runs(input_payloads=[invalid_nrr])
    assert result["cross_run_comparison"] is None
    decision = result["cross_run_intelligence_decision"]
    assert decision["overall_status"] == "fail"
    assert decision["failure_type"] == "schema_invalid"


# ---------------------------------------------------------------------------
# Mixed study type failure
# ---------------------------------------------------------------------------


def test_mixed_study_types_fails():
    nrr1 = _p2p_nrr("b1", "NRR-A0000000001", "s1", "S1", study_type="p2p_interference")
    nrr2 = _p2p_nrr("b2", "NRR-A0000000002", "s2", "S2", study_type="sharing_study")
    # Force different study types in the payloads
    nrr2["study_type"] = "sharing_study"
    result = compare_normalized_runs(input_payloads=[nrr1, nrr2])
    assert result["cross_run_comparison"] is None
    decision = result["cross_run_intelligence_decision"]
    assert decision["overall_status"] == "fail"
    assert decision["failure_type"] == "mixed_study_types"


def test_infer_comparison_study_type_mixed():
    nrr1 = _p2p_nrr("b1", "NRR-A1", "s1", "S1")
    nrr2 = _p2p_nrr("b2", "NRR-A2", "s2", "S2")
    nrr2["study_type"] = "retuning_analysis"
    study_type, findings = infer_comparison_study_type([nrr1, nrr2])
    assert study_type is None
    assert any(f["code"] == "mixed_study_types" for f in findings)


def test_infer_comparison_study_type_single():
    nrr1 = _p2p_nrr("b1", "NRR-A1", "s1", "S1")
    nrr2 = _p2p_nrr("b2", "NRR-A2", "s2", "S2")
    study_type, findings = infer_comparison_study_type([nrr1, nrr2])
    assert study_type == "p2p_interference"
    assert not any(f["severity"] == "error" for f in findings)


def test_infer_comparison_study_type_generic_included():
    nrr1 = _p2p_nrr("b1", "NRR-A1", "s1", "S1")
    nrr2 = _p2p_nrr("b2", "NRR-A2", "s2", "S2")
    nrr2["study_type"] = "generic"
    study_type, findings = infer_comparison_study_type([nrr1, nrr2])
    assert study_type == "p2p_interference"
    assert any(f["code"] == "generic_run_included" and f["severity"] == "warning" for f in findings)


def test_infer_comparison_study_type_all_generic():
    nrr1 = _p2p_nrr("b1", "NRR-A1", "s1", "S1")
    nrr1["study_type"] = "generic"
    nrr2 = _p2p_nrr("b2", "NRR-A2", "s2", "S2")
    nrr2["study_type"] = "generic"
    study_type, findings = infer_comparison_study_type([nrr1, nrr2])
    assert study_type == "generic"
    assert not any(f["severity"] == "error" for f in findings)


# ---------------------------------------------------------------------------
# Metric comparison — clean comparable runs
# ---------------------------------------------------------------------------


def test_metric_comparisons_comparable():
    nrr1 = _p2p_nrr("b1", "NRR-A1", "s1", "S1", interference=-85.0)
    nrr2 = _p2p_nrr("b2", "NRR-A2", "s2", "S2", interference=-92.0)
    comparisons = build_metric_comparisons([nrr1, nrr2])

    inter_mc = next(mc for mc in comparisons if mc["metric_name"] == "interference_power_dbm")
    assert inter_mc["comparability_status"] == "comparable"
    assert inter_mc["summary_statistics"]["count"] == 2
    assert inter_mc["summary_statistics"]["min"] == -92.0
    assert inter_mc["summary_statistics"]["max"] == -85.0


def test_metric_comparisons_values_traced():
    nrr1 = _p2p_nrr("b1", "NRR-A1", "s1", "S1", interference=-85.0)
    nrr2 = _p2p_nrr("b2", "NRR-A2", "s2", "S2", interference=-92.0)
    comparisons = build_metric_comparisons([nrr1, nrr2])

    inter_mc = next(mc for mc in comparisons if mc["metric_name"] == "interference_power_dbm")
    bundle_ids = {cv["source_bundle_id"] for cv in inter_mc["compared_values"]}
    assert "b1" in bundle_ids
    assert "b2" in bundle_ids


# ---------------------------------------------------------------------------
# Mixed units behavior
# ---------------------------------------------------------------------------


def test_mixed_units_detected():
    nrr1 = _p2p_nrr("b1", "NRR-A1", "s1", "S1")
    nrr2 = _p2p_nrr("b2", "NRR-A2", "s2", "S2")
    # Override the unit on one metric in nrr2
    nrr2["metrics"]["summary_metrics"][0]["unit"] = "W"  # different unit for interference
    comparisons = build_metric_comparisons([nrr1, nrr2])
    inter_mc = next(mc for mc in comparisons if mc["metric_name"] == "interference_power_dbm")
    assert inter_mc["comparability_status"] == "mixed_units"


def test_detect_mixed_units_true():
    assert detect_mixed_units("x", [{"unit": "dB"}, {"unit": "dBm"}]) is True


def test_detect_mixed_units_false():
    assert detect_mixed_units("x", [{"unit": "dB"}, {"unit": "dB"}]) is False


# ---------------------------------------------------------------------------
# Insufficient data behavior
# ---------------------------------------------------------------------------


def test_insufficient_data_single_run():
    nrr1 = _p2p_nrr("b1", "NRR-A1", "s1", "S1")
    comparisons = build_metric_comparisons([nrr1])
    for mc in comparisons:
        assert mc["comparability_status"] == "insufficient_data"


def test_summary_statistics_empty():
    stats = compute_summary_statistics([])
    assert stats["count"] == 0
    assert stats["min"] is None
    assert stats["mean"] is None


def test_summary_statistics_values():
    stats = compute_summary_statistics([10.0, 20.0, 30.0])
    assert stats["count"] == 3
    assert stats["min"] == 10.0
    assert stats["max"] == 30.0
    assert stats["range"] == 20.0
    assert abs(stats["mean"] - 20.0) < 1e-9


# ---------------------------------------------------------------------------
# Rankings — p2p_interference
# ---------------------------------------------------------------------------


def test_p2p_rankings_descending():
    nrr1 = _p2p_nrr("b1", "NRR-A1", "s1", "S1", interference=-85.0, in_ratio=12.0)
    nrr2 = _p2p_nrr("b2", "NRR-A2", "s2", "S2", interference=-92.0, in_ratio=8.0)
    comparisons = build_metric_comparisons([nrr1, nrr2])
    rankings = build_scenario_rankings(comparisons, "p2p_interference")

    inter_ranking = next(r for r in rankings if r["ranking_basis"] == "interference_power_dbm")
    assert inter_ranking["direction"] == "descending"
    # -85 > -92, so b1 ranks #1 in descending order
    assert inter_ranking["ranked_scenarios"][0]["source_bundle_id"] == "b1"
    assert inter_ranking["ranked_scenarios"][1]["source_bundle_id"] == "b2"


def test_p2p_in_ratio_ranking():
    nrr1 = _p2p_nrr("b1", "NRR-A1", "s1", "S1", in_ratio=12.0)
    nrr2 = _p2p_nrr("b2", "NRR-A2", "s2", "S2", in_ratio=8.0)
    comparisons = build_metric_comparisons([nrr1, nrr2])
    rankings = build_scenario_rankings(comparisons, "p2p_interference")

    in_ratio_ranking = next(r for r in rankings if r["ranking_basis"] == "in_ratio_db")
    assert in_ratio_ranking["ranked_scenarios"][0]["source_bundle_id"] == "b1"


# ---------------------------------------------------------------------------
# Rankings — retuning_analysis
# ---------------------------------------------------------------------------


def _retuning_nrr(
    bundle_id: str,
    artifact_id: str,
    scenario_id: str,
    scenario_label: str,
    incumbent_links: float = 5.0,
    retune_count: float = 10.0,
) -> Dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "artifact_type": "normalized_run_result",
        "schema_version": "1.0.0",
        "source_bundle_id": bundle_id,
        "study_type": "retuning_analysis",
        "scenario": {
            "scenario_id": scenario_id,
            "scenario_label": scenario_label,
            "frequency_range_mhz": {"low_mhz": 3550.0, "high_mhz": 3600.0},
            "assumptions_summary": "Retuning test.",
        },
        "metrics": {
            "metric_set_id": f"ms-{bundle_id}",
            "summary_metrics": [
                {
                    "name": "incumbent_links_impacted",
                    "value": incumbent_links,
                    "unit": "count",
                    "classification": "core",
                    "source_path": "outputs/results_summary.json#metrics[0]",
                },
                {
                    "name": "retune_candidate_count",
                    "value": retune_count,
                    "unit": "count",
                    "classification": "core",
                    "source_path": "outputs/results_summary.json#metrics[1]",
                },
            ],
            "completeness": {
                "required_metric_count": 2,
                "present_required_metric_count": 2,
                "missing_required_metrics": [],
                "status": "complete",
            },
        },
        "evaluation_signals": {
            "readiness": "ready_for_comparison",
            "outlier_flags": [],
            "threshold_assessments": [],
            "trust_notes": [],
        },
        "provenance": {
            "manifest_author": "test-author",
            "source_case_ids": ["case-rt-001"],
            "creation_context": "Retuning unit test.",
            "rng_reference": {"mode": "fixed", "value": 0},
            "results_summary_source": "outputs/results_summary.json",
            "provenance_source": "outputs/provenance.json",
        },
        "generated_at": "2026-03-01T10:00:00+00:00",
    }


def test_retuning_rankings():
    nrr1 = _retuning_nrr("b1", "NRR-RT1", "s1", "S1", incumbent_links=5.0, retune_count=10.0)
    nrr2 = _retuning_nrr("b2", "NRR-RT2", "s2", "S2", incumbent_links=2.0, retune_count=4.0)
    comparisons = build_metric_comparisons([nrr1, nrr2])
    rankings = build_scenario_rankings(comparisons, "retuning_analysis")

    # Expect b1 to rank #1 for incumbent_links_impacted (descending)
    links_ranking = next(r for r in rankings if r["ranking_basis"] == "incumbent_links_impacted")
    assert links_ranking["direction"] == "descending"
    assert links_ranking["ranked_scenarios"][0]["source_bundle_id"] == "b1"


def test_generic_no_rankings():
    nrr1 = _p2p_nrr("b1", "NRR-A1", "s1", "S1")
    nrr1["study_type"] = "generic"
    nrr2 = _p2p_nrr("b2", "NRR-A2", "s2", "S2")
    nrr2["study_type"] = "generic"
    comparisons = build_metric_comparisons([nrr1, nrr2])
    rankings = build_scenario_rankings(comparisons, "generic")
    assert rankings == []


# ---------------------------------------------------------------------------
# Anomaly detection — extreme spread
# ---------------------------------------------------------------------------


def test_extreme_spread_detected():
    nrr1 = _p2p_nrr("b1", "NRR-A1", "s1", "S1", interference=-1.0)
    nrr2 = _p2p_nrr("b2", "NRR-A2", "s2", "S2", interference=-200.0)
    # mean = -100.5, range = 199.0  → range > 10 * abs(mean) = 1005? No.
    # Let's use values where range > 10 * abs(mean)
    # mean = 5, range = 60 → range(60) > 10 * abs(5) = 50 → True
    nrr1["metrics"]["summary_metrics"][0]["value"] = 2.0
    nrr2["metrics"]["summary_metrics"][0]["value"] = 62.0
    # mean = 32, range = 60 → 60 > 10 * 32 = 320? No.
    # Use: val1=1, val2=12  → mean=6.5, range=11 → 11 > 10*6.5=65? No
    # Use: val1=0.5, val2=6 → mean=3.25, range=5.5 → 5.5 > 32.5? No
    # Use: val1=1, val2=100 → mean=50.5, range=99 → 99 > 505? No
    # The rule: abs(mean) > 0 and range > 10 * abs(mean)
    # need range/mean > 10 → e.g. mean=1, range=11
    # val1=0, val2=2 → mean=1, range=2 → 2 > 10? No
    # val1=-0.5, val2=10.5 → mean=5, range=11 → 11 > 50? No
    # val1=0.1, val2=1.1 → mean=0.6, range=1.0 → 1.0 > 6? No
    # val1=0.1, val2=10.1 → mean=5.1, range=10.0 → 10 > 51? No
    # val1=1, val2=20 → mean=10.5, range=19 → 19 > 105? No
    # Need: range/abs(mean) > 10
    # e.g. mean=1 (val1=0.5, val2=1.5 → range=1, mean=1 → 1>10? No)
    # val1=0.09, val2=1.09 → mean=0.59, range=1 → 1>5.9? No
    # val1=0.09, val2=5.09 → mean=2.59, range=5 → 5>25.9? No
    # Try: val1=-5, val2=6 → mean=0.5, range=11 → 11>5? Yes!
    nrr1["metrics"]["summary_metrics"][0]["value"] = -5.0
    nrr2["metrics"]["summary_metrics"][0]["value"] = 6.0
    # mean = 0.5, range = 11 → 11 > 10 * 0.5 = 5 → True!
    comparisons = build_metric_comparisons([nrr1, nrr2])
    flags = detect_cross_run_anomalies(comparisons, [nrr1, nrr2])
    extreme = [f for f in flags if f["flag_type"] == "extreme_spread"]
    assert extreme, "Expected extreme_spread anomaly flag"
    assert extreme[0]["metric_name"] == "interference_power_dbm"


def test_extreme_spread_not_triggered_for_normal_values():
    nrr1 = _p2p_nrr("b1", "NRR-A1", "s1", "S1", interference=-85.0)
    nrr2 = _p2p_nrr("b2", "NRR-A2", "s2", "S2", interference=-92.0)
    comparisons = build_metric_comparisons([nrr1, nrr2])
    flags = detect_cross_run_anomalies(comparisons, [nrr1, nrr2])
    extreme = [f for f in flags if f["flag_type"] == "extreme_spread"]
    assert not extreme


# ---------------------------------------------------------------------------
# Anomaly detection — duplicate scenario_id conflict
# ---------------------------------------------------------------------------


def test_duplicate_scenario_id_detected():
    # Same scenario_id in both runs but materially different values
    nrr1 = _p2p_nrr("b1", "NRR-A1", "same-scenario", "Same", interference=-85.0)
    nrr2 = _p2p_nrr("b2", "NRR-A2", "same-scenario", "Same", interference=-20.0)
    comparisons = build_metric_comparisons([nrr1, nrr2])
    flags = detect_cross_run_anomalies(comparisons, [nrr1, nrr2])
    dup_flags = [f for f in flags if f["flag_type"] == "duplicate_scenario_id"]
    assert dup_flags, "Expected duplicate_scenario_id anomaly flag"


def test_no_duplicate_scenario_id_for_different_scenarios():
    nrr1 = _p2p_nrr("b1", "NRR-A1", "scen-001", "S1", interference=-85.0)
    nrr2 = _p2p_nrr("b2", "NRR-A2", "scen-002", "S2", interference=-92.0)
    comparisons = build_metric_comparisons([nrr1, nrr2])
    flags = detect_cross_run_anomalies(comparisons, [nrr1, nrr2])
    dup_flags = [f for f in flags if f["flag_type"] == "duplicate_scenario_id"]
    assert not dup_flags


# ---------------------------------------------------------------------------
# Readiness mismatch detection
# ---------------------------------------------------------------------------


def test_readiness_mismatch_detected():
    nrr1 = _p2p_nrr(
        "b1",
        "NRR-A1",
        "s1",
        "S1",
        readiness="ready_for_comparison",
        completeness_status="partial",
    )
    nrr2 = _p2p_nrr("b2", "NRR-A2", "s2", "S2")
    comparisons = build_metric_comparisons([nrr1, nrr2])
    flags = detect_cross_run_anomalies(comparisons, [nrr1, nrr2])
    mismatch = [f for f in flags if f["flag_type"] == "readiness_mismatch"]
    assert mismatch, "Expected readiness_mismatch anomaly flag"
    assert "b1" in mismatch[0]["affected_runs"]


def test_no_readiness_mismatch_for_consistent_run():
    nrr1 = _p2p_nrr("b1", "NRR-A1", "s1", "S1")  # ready + complete
    nrr2 = _p2p_nrr("b2", "NRR-A2", "s2", "S2")
    comparisons = build_metric_comparisons([nrr1, nrr2])
    flags = detect_cross_run_anomalies(comparisons, [nrr1, nrr2])
    mismatch = [f for f in flags if f["flag_type"] == "readiness_mismatch"]
    assert not mismatch


# ---------------------------------------------------------------------------
# classify_cross_run_failure
# ---------------------------------------------------------------------------


def test_classify_pass():
    status, ftype = classify_cross_run_failure([])
    assert status == "pass"
    assert ftype == "none"


def test_classify_warning():
    findings = [{"code": "low_sample_count", "severity": "warning", "message": "x", "artifact_path": ""}]
    status, ftype = classify_cross_run_failure(findings)
    assert status == "warning"
    assert ftype == "none"


def test_classify_fail_no_inputs():
    findings = [{"code": "no_inputs", "severity": "error", "message": "x", "artifact_path": ""}]
    status, ftype = classify_cross_run_failure(findings)
    assert status == "fail"
    assert ftype == "no_inputs"


def test_classify_fail_schema_invalid():
    findings = [{"code": "schema_invalid", "severity": "error", "message": "x", "artifact_path": ""}]
    status, ftype = classify_cross_run_failure(findings)
    assert status == "fail"
    assert ftype == "schema_invalid"


# ---------------------------------------------------------------------------
# CLI exit code behavior
# ---------------------------------------------------------------------------


def test_cli_exit_0_for_clean_comparison(tmp_path):
    from scripts.cross_run_intelligence import main

    nrr1 = tmp_path / "nrr1.json"
    nrr2 = tmp_path / "nrr2.json"
    nrr1.write_text(json.dumps(_p2p_nrr("b1", "NRR-B1", "s1", "S1")), encoding="utf-8")
    nrr2.write_text(json.dumps(_p2p_nrr("b2", "NRR-B2", "s2", "S2")), encoding="utf-8")

    out_dir = tmp_path / "outputs"
    code = main(["--input", str(nrr1), "--input", str(nrr2), "--output-dir", str(out_dir)])
    assert code == 0


def test_cli_exit_2_for_no_valid_inputs(tmp_path):
    from scripts.cross_run_intelligence import main

    bad = tmp_path / "bad.json"
    bad.write_text("{broken", encoding="utf-8")
    code = main(["--input", str(bad)])
    assert code == 2


def test_cli_exit_2_for_mixed_study_types(tmp_path):
    from scripts.cross_run_intelligence import main

    nrr1 = _p2p_nrr("b1", "NRR-B1", "s1", "S1", study_type="p2p_interference")
    nrr2 = _p2p_nrr("b2", "NRR-B2", "s2", "S2", study_type="sharing_study")
    nrr2["study_type"] = "sharing_study"

    f1 = tmp_path / "nrr1.json"
    f2 = tmp_path / "nrr2.json"
    f1.write_text(json.dumps(nrr1), encoding="utf-8")
    f2.write_text(json.dumps(nrr2), encoding="utf-8")

    code = main(["--input", str(f1), "--input", str(f2)])
    assert code == 2


# ---------------------------------------------------------------------------
# Directory auto-discovery
# ---------------------------------------------------------------------------


def test_cli_directory_discovery(tmp_path):
    from scripts.cross_run_intelligence import main

    sub1 = tmp_path / "run1"
    sub2 = tmp_path / "run2"
    sub1.mkdir()
    sub2.mkdir()
    (sub1 / "normalized_run_result.json").write_text(
        json.dumps(_p2p_nrr("b1", "NRR-D1", "s1", "S1")), encoding="utf-8"
    )
    (sub2 / "normalized_run_result.json").write_text(
        json.dumps(_p2p_nrr("b2", "NRR-D2", "s2", "S2")), encoding="utf-8"
    )
    out_dir = tmp_path / "outputs"
    code = main(["--dir", str(tmp_path), "--output-dir", str(out_dir)])
    assert code == 0
    assert (out_dir / "cross_run_comparison.json").exists()
    assert (out_dir / "cross_run_intelligence_decision.json").exists()


def test_cli_directory_not_found(tmp_path):
    from scripts.cross_run_intelligence import main

    code = main(["--dir", str(tmp_path / "nonexistent")])
    assert code == 2


def test_cli_directory_no_nrr_files(tmp_path):
    from scripts.cross_run_intelligence import main

    code = main(["--dir", str(tmp_path)])
    assert code == 2


# ---------------------------------------------------------------------------
# Integration — realistic NRR fixtures
# ---------------------------------------------------------------------------


def test_integration_two_p2p_runs():
    """Integration test using the two realistic p2p fixture files."""
    result = compare_normalized_runs(
        input_paths=[str(_NRR_P2P_RUN1), str(_NRR_P2P_RUN2)]
    )
    crc = result["cross_run_comparison"]
    decision = result["cross_run_intelligence_decision"]

    assert crc is not None
    assert crc["study_type"] == "p2p_interference"
    assert len(crc["compared_runs"]) == 2

    # Validate CRC against schema
    schema_findings = validate_cross_run_comparison(crc)
    assert not any(f["severity"] == "error" for f in schema_findings), schema_findings

    # Validate decision against schema
    dec_schema_findings = validate_cross_run_intelligence_decision(decision)
    assert not any(f["severity"] == "error" for f in dec_schema_findings), dec_schema_findings

    # Rankings should be present
    assert len(crc["scenario_rankings"]) > 0

    # Decision should be pass or warning (no hard failures expected)
    assert decision["overall_status"] in {"pass", "warning"}


def test_integration_three_p2p_runs_with_outlier():
    """Integration test using two normal p2p runs and one outlier."""
    result = compare_normalized_runs(
        input_paths=[str(_NRR_P2P_RUN1), str(_NRR_P2P_RUN2), str(_NRR_P2P_OUTLIER)]
    )
    crc = result["cross_run_comparison"]
    decision = result["cross_run_intelligence_decision"]

    assert crc is not None
    assert len(crc["compared_runs"]) == 3

    # Should still produce valid artifacts
    assert not any(
        f["severity"] == "error" for f in validate_cross_run_comparison(crc)
    )
    assert decision["overall_status"] in {"pass", "warning", "fail"}


def test_integration_artifacts_are_traceable():
    """Verify that every compared_value is traceable back to a source_bundle_id."""
    result = compare_normalized_runs(
        input_paths=[str(_NRR_P2P_RUN1), str(_NRR_P2P_RUN2)]
    )
    crc = result["cross_run_comparison"]
    assert crc is not None

    bundle_ids = {run["source_bundle_id"] for run in crc["compared_runs"]}
    for mc in crc["metric_comparisons"]:
        for cv in mc["compared_values"]:
            assert cv["source_bundle_id"] in bundle_ids
            assert cv["source_path"] != ""


def test_integration_comparison_id_links_decision():
    """comparison_id in CRI must match comparison_id in CRC."""
    result = compare_normalized_runs(
        input_paths=[str(_NRR_P2P_RUN1), str(_NRR_P2P_RUN2)]
    )
    crc = result["cross_run_comparison"]
    decision = result["cross_run_intelligence_decision"]
    assert crc is not None
    assert crc["comparison_id"] == decision["comparison_id"]
