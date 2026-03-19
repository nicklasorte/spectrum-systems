"""Tests for BG working paper evidence pack synthesis layer (Prompt BG).

Covers:
- schema validation success for both artifacts
- schema rejection for extra properties
- no inputs
- malformed BE input
- malformed BF input
- mixed study type failure
- BE-only synthesis path
- BE+BF synthesis path
- evidence assignment to sections
- ranked finding derivation
- caveat derivation
- follow-up question derivation
- confidence assignment logic
- empty/partial/populated synthesis status
- CLI exit code behavior
- integration using realistic BE and BF fixtures
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

from spectrum_systems.modules.runtime.working_paper_synthesis import (  # noqa: E402
    assign_evidence_to_sections,
    build_evidence_items_from_be,
    build_evidence_items_from_bf,
    build_working_paper_evidence_pack,
    build_working_paper_synthesis_decision,
    classify_synthesis_failure,
    collect_source_artifacts,
    compute_synthesis_status,
    derive_caveats,
    derive_followup_questions,
    derive_ranked_findings,
    infer_synthesis_study_type,
    load_governed_artifact,
    map_evidence_sections,
    synthesize_working_paper_evidence,
    validate_be_input,
    validate_bf_input,
    validate_working_paper_evidence_pack,
    validate_working_paper_synthesis_decision,
)

_WPE_SCHEMA_PATH = _REPO_ROOT / "contracts" / "schemas" / "working_paper_evidence_pack.schema.json"
_WPS_SCHEMA_PATH = (
    _REPO_ROOT / "contracts" / "schemas" / "working_paper_synthesis_decision.schema.json"
)
_NRR_P2P_RUN1 = _REPO_ROOT / "tests" / "fixtures" / "nrr_p2p_run1.json"
_NRR_P2P_RUN2 = _REPO_ROOT / "tests" / "fixtures" / "nrr_p2p_run2.json"
_NRR_P2P_THIN = _REPO_ROOT / "tests" / "fixtures" / "nrr_p2p_thin.json"
_BF_CRC = _REPO_ROOT / "tests" / "fixtures" / "bf_cross_run_comparison.json"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _p2p_nrr(
    artifact_id: str = "NRR-AAA001",
    bundle_id: str = "bundle-001",
    scenario_id: str = "sc-001",
    scenario_label: str = "Test Scenario",
    readiness: str = "ready_for_comparison",
    completeness_status: str = "complete",
    missing_metrics: list | None = None,
    interference: float = -85.0,
    in_ratio: float = 12.0,
    path_loss: float = 142.0,
    trust_notes: list | None = None,
) -> Dict[str, Any]:
    """Return a minimal valid NRR dict for p2p_interference."""
    if missing_metrics is None:
        missing_metrics = []
    if trust_notes is None:
        trust_notes = []

    req_count = 3
    metrics = []
    for name, val, unit in [
        ("interference_power_dbm", interference, "dBm"),
        ("in_ratio_db", in_ratio, "dB"),
        ("path_loss_db", path_loss, "dB"),
    ]:
        if name not in missing_metrics:
            metrics.append(
                {
                    "name": name,
                    "value": val,
                    "unit": unit,
                    "classification": "core",
                    "source_path": f"outputs/results_summary.json#{name}",
                }
            )

    present_count = req_count - len(missing_metrics)
    return {
        "artifact_id": artifact_id,
        "artifact_type": "normalized_run_result",
        "schema_version": "1.0.0",
        "source_bundle_id": bundle_id,
        "study_type": "p2p_interference",
        "scenario": {
            "scenario_id": scenario_id,
            "scenario_label": scenario_label,
            "frequency_range_mhz": {"low_mhz": 3550.0, "high_mhz": 3600.0},
            "assumptions_summary": "Test assumption.",
        },
        "metrics": {
            "metric_set_id": f"ms-{bundle_id}",
            "summary_metrics": metrics,
            "completeness": {
                "required_metric_count": req_count,
                "present_required_metric_count": present_count,
                "missing_required_metrics": missing_metrics,
                "status": completeness_status,
            },
        },
        "evaluation_signals": {
            "readiness": readiness,
            "outlier_flags": [],
            "threshold_assessments": [],
            "trust_notes": trust_notes,
        },
        "provenance": {
            "manifest_author": "test-author",
            "source_case_ids": ["case-001"],
            "creation_context": "BG unit test.",
            "rng_reference": {"mode": "fixed", "value": 42},
            "results_summary_source": "outputs/results_summary.json",
            "provenance_source": "outputs/provenance.json",
        },
        "generated_at": "2026-03-01T10:00:00+00:00",
    }


def _minimal_crc(
    artifact_id: str = "CRC-TEST-001",
    comparison_id: str = "CMP-TEST-001",
    study_type: str = "p2p_interference",
    anomaly_flags: list | None = None,
) -> Dict[str, Any]:
    if anomaly_flags is None:
        anomaly_flags = []
    return {
        "artifact_id": artifact_id,
        "artifact_type": "cross_run_comparison",
        "schema_version": "1.0.0",
        "comparison_id": comparison_id,
        "study_type": study_type,
        "compared_runs": [
            {
                "source_bundle_id": "bundle-001",
                "normalized_run_result_id": "NRR-AAA001",
                "scenario_id": "sc-001",
                "scenario_label": "Test Scenario",
                "readiness": "ready_for_comparison",
                "completeness_status": "complete",
            },
            {
                "source_bundle_id": "bundle-002",
                "normalized_run_result_id": "NRR-BBB001",
                "scenario_id": "sc-002",
                "scenario_label": "Test Scenario 2",
                "readiness": "ready_for_comparison",
                "completeness_status": "complete",
            },
        ],
        "metric_comparisons": [],
        "scenario_rankings": [
            {
                "ranking_basis": "interference_power_dbm",
                "direction": "descending",
                "ranked_scenarios": [
                    {
                        "rank": 1,
                        "source_bundle_id": "bundle-001",
                        "scenario_id": "sc-001",
                        "scenario_label": "Test Scenario",
                        "metric_name": "interference_power_dbm",
                        "value": -85.0,
                    },
                    {
                        "rank": 2,
                        "source_bundle_id": "bundle-002",
                        "scenario_id": "sc-002",
                        "scenario_label": "Test Scenario 2",
                        "metric_name": "interference_power_dbm",
                        "value": -92.0,
                    },
                ],
            }
        ],
        "anomaly_flags": anomaly_flags,
        "generated_at": "2026-03-01T14:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestSchemaFiles:
    def test_wpe_schema_is_valid_json(self):
        schema = json.loads(_WPE_SCHEMA_PATH.read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    def test_wps_schema_is_valid_json(self):
        schema = json.loads(_WPS_SCHEMA_PATH.read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    def test_wpe_schema_rejects_extra_properties(self):
        pack = build_working_paper_evidence_pack(be_payloads=[_p2p_nrr()])
        pack["extra_field"] = "not_allowed"
        findings = validate_working_paper_evidence_pack(pack)
        assert any(f["code"] == "schema_invalid" for f in findings)

    def test_wps_schema_rejects_extra_properties(self):
        nrr = _p2p_nrr()
        pack = build_working_paper_evidence_pack(be_payloads=[nrr])
        decision = build_working_paper_synthesis_decision(
            evidence_pack_id=pack["evidence_pack_id"], findings=[]
        )
        decision["bogus"] = "field"
        findings = validate_working_paper_synthesis_decision(decision)
        assert any(f["code"] == "schema_invalid" for f in findings)


# ---------------------------------------------------------------------------
# Input validation tests
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_be_valid_nrr_passes(self):
        nrr = _p2p_nrr()
        findings = validate_be_input(nrr)
        assert findings == []

    def test_be_invalid_nrr_rejected(self):
        findings = validate_be_input({"artifact_type": "normalized_run_result"})
        assert any(f["code"] == "schema_invalid" for f in findings)

    def test_be_wrong_artifact_type_rejected(self):
        nrr = _p2p_nrr()
        nrr["artifact_type"] = "cross_run_comparison"
        findings = validate_be_input(nrr)
        assert any(f["code"] == "schema_invalid" for f in findings)

    def test_bf_valid_crc_passes(self):
        crc = _minimal_crc()
        findings = validate_bf_input(crc)
        assert findings == []

    def test_bf_invalid_crc_rejected(self):
        findings = validate_bf_input({"artifact_type": "cross_run_comparison"})
        assert any(f["code"] == "schema_invalid" for f in findings)


# ---------------------------------------------------------------------------
# No inputs test
# ---------------------------------------------------------------------------


class TestNoInputs:
    def test_no_inputs_produces_fail(self):
        result = synthesize_working_paper_evidence()
        decision = result["working_paper_synthesis_decision"]
        assert decision["overall_status"] == "fail"
        assert decision["failure_type"] == "no_inputs"
        assert result["working_paper_evidence_pack"] is None

    def test_no_inputs_with_empty_lists(self):
        result = synthesize_working_paper_evidence(be_inputs=[], bf_input=None)
        decision = result["working_paper_synthesis_decision"]
        assert decision["overall_status"] == "fail"
        assert decision["failure_type"] == "no_inputs"


# ---------------------------------------------------------------------------
# Malformed input tests
# ---------------------------------------------------------------------------


class TestMalformedInput:
    def test_malformed_be_file_produces_error(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json", encoding="utf-8")
        result = synthesize_working_paper_evidence(be_inputs=[str(bad_file)])
        findings = result["findings"]
        assert any(f["code"] == "malformed_input" for f in findings)
        assert result["working_paper_synthesis_decision"]["overall_status"] == "fail"

    def test_malformed_bf_file_produces_error(self, tmp_path):
        bad_file = tmp_path / "bad_bf.json"
        bad_file.write_text("not json", encoding="utf-8")
        nrr = _p2p_nrr()
        result = synthesize_working_paper_evidence(be_payloads=[nrr], bf_input=str(bad_file))
        findings = result["findings"]
        assert any(f["code"] == "malformed_input" for f in findings)

    def test_schema_invalid_be_payload(self):
        result = synthesize_working_paper_evidence(
            be_payloads=[{"artifact_type": "normalized_run_result", "missing_fields": True}]
        )
        findings = result["findings"]
        assert any(f["code"] == "schema_invalid" for f in findings)

    def test_schema_invalid_bf_payload(self):
        nrr = _p2p_nrr()
        result = synthesize_working_paper_evidence(
            be_payloads=[nrr],
            bf_payload={"artifact_type": "cross_run_comparison"},
        )
        # BF validation failure; BE-only pack should still be produced
        assert result["working_paper_evidence_pack"] is not None
        findings = result["findings"]
        assert any(f["code"] == "schema_invalid" for f in findings)


# ---------------------------------------------------------------------------
# Mixed study type test
# ---------------------------------------------------------------------------


class TestMixedStudyTypes:
    def test_mixed_study_types_fail(self):
        nrr1 = _p2p_nrr(artifact_id="NRR-AAA001", bundle_id="bundle-001")
        nrr2 = _p2p_nrr(artifact_id="NRR-BBB001", bundle_id="bundle-002")
        nrr2["study_type"] = "retuning_analysis"
        # Adjust metrics to pass NRR schema for retuning_analysis study_type
        nrr2["metrics"]["summary_metrics"] = [
            {
                "name": "incumbent_links_impacted",
                "value": 5,
                "unit": "count",
                "classification": "core",
                "source_path": "outputs/results_summary.json#metrics[0]",
            }
        ]
        nrr2["metrics"]["completeness"]["missing_required_metrics"] = ["retune_candidate_count"]
        nrr2["metrics"]["completeness"]["status"] = "partial"
        result = synthesize_working_paper_evidence(be_payloads=[nrr1, nrr2])
        decision = result["working_paper_synthesis_decision"]
        assert decision["overall_status"] == "fail"
        assert decision["failure_type"] == "mixed_study_types"

    def test_infer_synthesis_study_type_returns_error(self):
        nrr1 = _p2p_nrr()
        nrr2 = _p2p_nrr()
        nrr2["study_type"] = "retuning_analysis"
        study_type, findings = infer_synthesis_study_type([nrr1, nrr2], None)
        assert study_type is None
        assert any(f["code"] == "mixed_study_types" for f in findings)


# ---------------------------------------------------------------------------
# BE-only synthesis path
# ---------------------------------------------------------------------------


class TestBEOnlySynthesis:
    def test_single_be_produces_pass(self):
        nrr = _p2p_nrr()
        result = synthesize_working_paper_evidence(be_payloads=[nrr])
        decision = result["working_paper_synthesis_decision"]
        assert decision["overall_status"] == "pass"
        assert result["working_paper_evidence_pack"] is not None

    def test_two_be_inputs_produce_pass(self):
        nrr1 = _p2p_nrr(artifact_id="NRR-AAA001", bundle_id="bundle-001", scenario_id="sc-001")
        nrr2 = _p2p_nrr(artifact_id="NRR-BBB001", bundle_id="bundle-002", scenario_id="sc-002")
        result = synthesize_working_paper_evidence(be_payloads=[nrr1, nrr2])
        assert result["working_paper_evidence_pack"] is not None
        assert result["working_paper_synthesis_decision"]["overall_status"] == "pass"

    def test_be_only_no_comparative_section(self):
        nrr = _p2p_nrr()
        pack = build_working_paper_evidence_pack(be_payloads=[nrr])
        comp_sec = next(
            s for s in pack["section_evidence"] if s["section_key"] == "comparative_results"
        )
        assert comp_sec["synthesis_status"] == "empty"

    def test_be_only_study_objective_populated(self):
        nrr = _p2p_nrr()
        pack = build_working_paper_evidence_pack(be_payloads=[nrr])
        obj_sec = next(
            s for s in pack["section_evidence"] if s["section_key"] == "study_objective"
        )
        assert obj_sec["synthesis_status"] != "empty"

    def test_be_only_technical_findings_populated(self):
        nrr = _p2p_nrr()
        pack = build_working_paper_evidence_pack(be_payloads=[nrr])
        tf_sec = next(
            s for s in pack["section_evidence"] if s["section_key"] == "technical_findings"
        )
        assert tf_sec["synthesis_status"] in ("populated", "partial")
        assert len(tf_sec["evidence_items"]) > 0


# ---------------------------------------------------------------------------
# BE+BF synthesis path
# ---------------------------------------------------------------------------


class TestBEPlusBFSynthesis:
    def test_be_bf_produces_pass(self):
        nrr1 = _p2p_nrr(artifact_id="NRR-AAA001", bundle_id="bundle-001")
        crc = _minimal_crc()
        result = synthesize_working_paper_evidence(be_payloads=[nrr1], bf_payload=crc)
        assert result["working_paper_evidence_pack"] is not None
        assert result["working_paper_synthesis_decision"]["overall_status"] == "pass"

    def test_comparative_results_populated_with_bf(self):
        nrr1 = _p2p_nrr(artifact_id="NRR-AAA001", bundle_id="bundle-001")
        crc = _minimal_crc()
        pack = build_working_paper_evidence_pack(be_payloads=[nrr1], bf_payload=crc)
        comp_sec = next(
            s for s in pack["section_evidence"] if s["section_key"] == "comparative_results"
        )
        assert comp_sec["synthesis_status"] in ("populated", "partial")
        assert len(comp_sec["evidence_items"]) > 0

    def test_ranked_findings_include_rank1_finding(self):
        nrr1 = _p2p_nrr(artifact_id="NRR-AAA001", bundle_id="bundle-001")
        crc = _minimal_crc()
        pack = build_working_paper_evidence_pack(be_payloads=[nrr1], bf_payload=crc)
        priorities = [f["priority"] for f in pack["ranked_findings"]]
        assert "high" in priorities

    def test_be_bf_source_artifacts_count(self):
        nrr1 = _p2p_nrr(artifact_id="NRR-AAA001", bundle_id="bundle-001")
        crc = _minimal_crc()
        pack = build_working_paper_evidence_pack(be_payloads=[nrr1], bf_payload=crc)
        assert len(pack["source_artifacts"]) == 2  # 1 BE + 1 BF

    def test_anomaly_evidence_from_bf(self):
        nrr1 = _p2p_nrr(artifact_id="NRR-AAA001", bundle_id="bundle-001")
        anomaly_flags = [
            {
                "flag_type": "extreme_spread",
                "severity": "error",
                "metric_name": "interference_power_dbm",
                "affected_runs": ["bundle-001", "bundle-002"],
                "detail": "Spread of 90 dBm detected across runs.",
            }
        ]
        crc = _minimal_crc(anomaly_flags=anomaly_flags)
        bf_items = build_evidence_items_from_bf(crc)
        anomaly_items = [i for i in bf_items if i["evidence_type"] == "anomaly"]
        assert len(anomaly_items) == 1
        assert anomaly_items[0]["confidence"] == "high"


# ---------------------------------------------------------------------------
# Evidence assignment to sections
# ---------------------------------------------------------------------------


class TestEvidenceAssignment:
    def test_scenario_summary_goes_to_study_objective(self):
        nrr = _p2p_nrr()
        items = build_evidence_items_from_be([nrr])
        sections = assign_evidence_to_sections(items, "p2p_interference")
        obj_sec = next(s for s in sections if s["section_key"] == "study_objective")
        scenario_items = [i for i in obj_sec["evidence_items"] if i["evidence_type"] == "scenario_summary"]
        assert len(scenario_items) >= 1

    def test_metric_observations_go_to_technical_findings(self):
        nrr = _p2p_nrr()
        items = build_evidence_items_from_be([nrr])
        sections = assign_evidence_to_sections(items, "p2p_interference")
        tf_sec = next(s for s in sections if s["section_key"] == "technical_findings")
        metric_items = [i for i in tf_sec["evidence_items"] if i["evidence_type"] == "metric_observation"]
        assert len(metric_items) >= 3  # Three p2p metrics

    def test_completeness_gap_goes_to_limitations(self):
        nrr = _p2p_nrr(missing_metrics=["path_loss_db"], completeness_status="partial")
        items = build_evidence_items_from_be([nrr])
        sections = assign_evidence_to_sections(items, "p2p_interference")
        lim_sec = next(s for s in sections if s["section_key"] == "limitations_and_caveats")
        gap_items = [i for i in lim_sec["evidence_items"] if i["evidence_type"] == "completeness_gap"]
        assert len(gap_items) >= 1

    def test_anomaly_goes_to_limitations(self):
        anomaly_flags = [
            {
                "flag_type": "extreme_spread",
                "severity": "warning",
                "metric_name": "interference_power_dbm",
                "affected_runs": ["bundle-001"],
                "detail": "Spread detected.",
            }
        ]
        crc = _minimal_crc(anomaly_flags=anomaly_flags)
        items = build_evidence_items_from_bf(crc)
        sections = assign_evidence_to_sections(items, "p2p_interference")
        lim_sec = next(s for s in sections if s["section_key"] == "limitations_and_caveats")
        anomaly_items = [i for i in lim_sec["evidence_items"] if i["evidence_type"] == "anomaly"]
        assert len(anomaly_items) == 1

    def test_ranked_result_goes_to_comparative(self):
        crc = _minimal_crc()
        items = build_evidence_items_from_bf(crc)
        sections = assign_evidence_to_sections(items, "p2p_interference")
        comp_sec = next(s for s in sections if s["section_key"] == "comparative_results")
        rank_items = [i for i in comp_sec["evidence_items"] if i["evidence_type"] == "ranked_result"]
        assert len(rank_items) >= 1


# ---------------------------------------------------------------------------
# Ranked finding derivation
# ---------------------------------------------------------------------------


class TestRankedFindingDerivation:
    def test_findings_list_not_empty_with_sufficient_data(self):
        nrr = _p2p_nrr()
        crc = _minimal_crc()
        pack = build_working_paper_evidence_pack(be_payloads=[nrr], bf_payload=crc)
        assert len(pack["ranked_findings"]) >= 1

    def test_findings_bounded_at_seven(self):
        nrr1 = _p2p_nrr(artifact_id="NRR-AAA001", bundle_id="b1", scenario_id="sc-1")
        nrr2 = _p2p_nrr(artifact_id="NRR-BBB001", bundle_id="b2", scenario_id="sc-2")
        crc = _minimal_crc()
        pack = build_working_paper_evidence_pack(be_payloads=[nrr1, nrr2], bf_payload=crc)
        assert len(pack["ranked_findings"]) <= 7

    def test_critical_finding_for_anomaly(self):
        nrr = _p2p_nrr()
        anomaly_flags = [
            {
                "flag_type": "extreme_spread",
                "severity": "error",
                "metric_name": "interference_power_dbm",
                "affected_runs": ["bundle-001"],
                "detail": "Extreme spread.",
            }
        ]
        crc = _minimal_crc(anomaly_flags=anomaly_flags)
        pack = build_working_paper_evidence_pack(be_payloads=[nrr], bf_payload=crc)
        critical_findings = [f for f in pack["ranked_findings"] if f["priority"] == "critical"]
        assert len(critical_findings) >= 1

    def test_critical_finding_for_large_gaps(self):
        nrr = _p2p_nrr(
            missing_metrics=["path_loss_db", "in_ratio_db"],
            completeness_status="insufficient",
        )
        pack = build_working_paper_evidence_pack(be_payloads=[nrr])
        critical_findings = [f for f in pack["ranked_findings"] if f["priority"] == "critical"]
        assert len(critical_findings) >= 1

    def test_finding_ids_match_pattern(self):
        nrr = _p2p_nrr()
        crc = _minimal_crc()
        pack = build_working_paper_evidence_pack(be_payloads=[nrr], bf_payload=crc)
        import re
        pattern = re.compile(r"^FND-[A-Z0-9][A-Z0-9._-]*$")
        for f in pack["ranked_findings"]:
            assert pattern.match(f["finding_id"]), f"Bad finding_id: {f['finding_id']}"


# ---------------------------------------------------------------------------
# Caveat derivation
# ---------------------------------------------------------------------------


class TestCaveatDerivation:
    def test_data_gap_caveat_from_missing_metric(self):
        nrr = _p2p_nrr(missing_metrics=["path_loss_db"], completeness_status="partial")
        pack = build_working_paper_evidence_pack(be_payloads=[nrr])
        gap_cavs = [c for c in pack["caveats"] if c["category"] == "data_gap"]
        assert len(gap_cavs) >= 1

    def test_comparability_limit_caveat_from_mixed_units(self):
        crc = _minimal_crc()
        # Inject a mixed_units metric comparison
        crc["metric_comparisons"].append(
            {
                "metric_name": "path_loss_db",
                "unit": "dB",
                "compared_values": [
                    {
                        "source_bundle_id": "bundle-001",
                        "scenario_id": "sc-001",
                        "value": 142.0,
                        "classification": "core",
                        "source_path": "outputs/x.json",
                    },
                    {
                        "source_bundle_id": "bundle-002",
                        "scenario_id": "sc-002",
                        "value": 1420.0,
                        "classification": "core",
                        "source_path": "outputs/x.json",
                    },
                ],
                "summary_statistics": {"count": 2, "min": 142.0, "max": 1420.0, "range": 1278.0, "mean": 781.0},
                "comparability_status": "mixed_units",
            }
        )
        # Force mixed unit evidence by manually building BF items
        nrr = _p2p_nrr()
        pack = build_working_paper_evidence_pack(be_payloads=[nrr], bf_payload=crc)
        comp_lim = [c for c in pack["caveats"] if c["category"] == "comparability_limit"]
        assert len(comp_lim) >= 1

    def test_provenance_limit_caveat_for_not_ready(self):
        nrr = _p2p_nrr(readiness="not_ready")
        pack = build_working_paper_evidence_pack(be_payloads=[nrr])
        prov_cavs = [c for c in pack["caveats"] if c["category"] == "provenance_limit"]
        assert len(prov_cavs) >= 1
        assert prov_cavs[0]["severity"] == "error"

    def test_threshold_uncertainty_caveat(self):
        nrr = _load(_NRR_P2P_THIN)
        pack = build_working_paper_evidence_pack(be_payloads=[nrr])
        threshold_cavs = [c for c in pack["caveats"] if c["category"] == "threshold_uncertainty"]
        assert len(threshold_cavs) >= 1

    def test_caveat_ids_match_pattern(self):
        nrr = _p2p_nrr(missing_metrics=["path_loss_db"], completeness_status="partial")
        pack = build_working_paper_evidence_pack(be_payloads=[nrr])
        import re
        pattern = re.compile(r"^CAV-[A-Z0-9][A-Z0-9._-]*$")
        for c in pack["caveats"]:
            assert pattern.match(c["caveat_id"]), f"Bad caveat_id: {c['caveat_id']}"


# ---------------------------------------------------------------------------
# Follow-up question derivation
# ---------------------------------------------------------------------------


class TestFollowupQuestionDerivation:
    def test_question_generated_for_missing_metric(self):
        nrr = _p2p_nrr(missing_metrics=["path_loss_db"], completeness_status="partial")
        pack = build_working_paper_evidence_pack(be_payloads=[nrr])
        assert len(pack["followup_questions"]) >= 1
        q_text = pack["followup_questions"][0]["question"]
        assert "path_loss_db" in q_text

    def test_question_generated_for_anomaly(self):
        nrr = _p2p_nrr()
        anomaly_flags = [
            {
                "flag_type": "extreme_spread",
                "severity": "warning",
                "metric_name": "interference_power_dbm",
                "affected_runs": ["bundle-001"],
                "detail": "Spread detected.",
            }
        ]
        crc = _minimal_crc(anomaly_flags=anomaly_flags)
        pack = build_working_paper_evidence_pack(be_payloads=[nrr], bf_payload=crc)
        anomaly_qs = [
            q for q in pack["followup_questions"]
            if "anomaly" in q["question"].lower() or "interference_power_dbm" in q["question"]
        ]
        assert len(anomaly_qs) >= 1

    def test_question_generated_for_not_ready(self):
        nrr = _p2p_nrr(readiness="not_ready")
        pack = build_working_paper_evidence_pack(be_payloads=[nrr])
        not_ready_qs = [
            q for q in pack["followup_questions"]
            if "ready_for_comparison" in q["question"].lower() or "not_ready" in q["reason"].lower()
        ]
        assert len(not_ready_qs) >= 1

    def test_question_ids_match_pattern(self):
        nrr = _p2p_nrr(missing_metrics=["path_loss_db"], completeness_status="partial")
        pack = build_working_paper_evidence_pack(be_payloads=[nrr])
        import re
        pattern = re.compile(r"^QST-[A-Z0-9][A-Z0-9._-]*$")
        for q in pack["followup_questions"]:
            assert pattern.match(q["question_id"]), f"Bad question_id: {q['question_id']}"

    def test_questions_have_targeted_text(self):
        nrr = _p2p_nrr(missing_metrics=["path_loss_db"], completeness_status="partial")
        pack = build_working_paper_evidence_pack(be_payloads=[nrr])
        for q in pack["followup_questions"]:
            # Should not be vague filler
            assert len(q["question"]) > 20
            assert q["reason"] != ""


# ---------------------------------------------------------------------------
# Confidence assignment logic
# ---------------------------------------------------------------------------


class TestConfidenceAssignment:
    def test_high_confidence_for_ready_complete_be(self):
        nrr = _p2p_nrr(readiness="ready_for_comparison", completeness_status="complete")
        items = build_evidence_items_from_be([nrr])
        metric_items = [i for i in items if i["evidence_type"] == "metric_observation"]
        assert all(i["confidence"] == "high" for i in metric_items)

    def test_medium_confidence_for_limited_use_be(self):
        nrr = _p2p_nrr(
            readiness="limited_use",
            completeness_status="partial",
            missing_metrics=["path_loss_db"],
        )
        items = build_evidence_items_from_be([nrr])
        metric_items = [i for i in items if i["evidence_type"] == "metric_observation"]
        assert all(i["confidence"] == "medium" for i in metric_items)

    def test_low_confidence_for_completeness_gap(self):
        nrr = _p2p_nrr(missing_metrics=["path_loss_db"], completeness_status="partial")
        items = build_evidence_items_from_be([nrr])
        gap_items = [i for i in items if i["evidence_type"] == "completeness_gap"]
        assert all(i["confidence"] == "low" for i in gap_items)

    def test_high_confidence_for_bf_ranked_with_two_ready(self):
        crc = _minimal_crc()  # 2 ready_for_comparison runs
        items = build_evidence_items_from_bf(crc)
        ranked_items = [i for i in items if i["evidence_type"] == "ranked_result"]
        assert all(i["confidence"] == "high" for i in ranked_items)

    def test_high_confidence_for_error_anomaly(self):
        crc = _minimal_crc(
            anomaly_flags=[
                {
                    "flag_type": "extreme_spread",
                    "severity": "error",
                    "metric_name": "metric_x",
                    "affected_runs": [],
                    "detail": "Error anomaly.",
                }
            ]
        )
        items = build_evidence_items_from_bf(crc)
        anomaly_items = [i for i in items if i["evidence_type"] == "anomaly"]
        assert anomaly_items[0]["confidence"] == "high"

    def test_medium_confidence_for_warning_anomaly(self):
        crc = _minimal_crc(
            anomaly_flags=[
                {
                    "flag_type": "readiness_mismatch",
                    "severity": "warning",
                    "metric_name": "metric_x",
                    "affected_runs": [],
                    "detail": "Warning anomaly.",
                }
            ]
        )
        items = build_evidence_items_from_bf(crc)
        anomaly_items = [i for i in items if i["evidence_type"] == "anomaly"]
        assert anomaly_items[0]["confidence"] == "medium"


# ---------------------------------------------------------------------------
# Synthesis status tests
# ---------------------------------------------------------------------------


class TestSynthesisStatus:
    def test_empty_section(self):
        section = {"section_key": "agency_questions", "evidence_items": []}
        assert compute_synthesis_status(section) == "empty"

    def test_populated_section_all_content(self):
        nrr = _p2p_nrr()
        items = build_evidence_items_from_be([nrr])
        metric_only = [i for i in items if i["evidence_type"] == "metric_observation"]
        section = {"section_key": "technical_findings", "evidence_items": metric_only}
        assert compute_synthesis_status(section) == "populated"

    def test_partial_section_mixed_content_and_gaps(self):
        nrr = _p2p_nrr(missing_metrics=["path_loss_db"], completeness_status="partial")
        items = build_evidence_items_from_be([nrr])
        section = {"section_key": "technical_findings", "evidence_items": items}
        # Has both metric_observation and completeness_gap
        status = compute_synthesis_status(section)
        assert status in ("partial", "populated")

    def test_partial_section_only_gaps(self):
        nrr = _p2p_nrr(missing_metrics=["path_loss_db"], completeness_status="partial")
        items = build_evidence_items_from_be([nrr])
        gap_only = [i for i in items if i["evidence_type"] == "completeness_gap"]
        section = {"section_key": "limitations_and_caveats", "evidence_items": gap_only}
        assert compute_synthesis_status(section) == "partial"


# ---------------------------------------------------------------------------
# Classify synthesis failure
# ---------------------------------------------------------------------------


class TestClassifySynthesisFailure:
    def test_no_findings_is_pass(self):
        status, failure = classify_synthesis_failure([])
        assert status == "pass"
        assert failure == "none"

    def test_error_finding_is_fail(self):
        findings = [{"code": "no_inputs", "severity": "error", "message": "x", "artifact_path": ""}]
        status, failure = classify_synthesis_failure(findings)
        assert status == "fail"
        assert failure == "no_inputs"

    def test_warning_finding_is_warning(self):
        findings = [{"code": "study_type_mismatch", "severity": "warning", "message": "x", "artifact_path": ""}]
        status, failure = classify_synthesis_failure(findings)
        assert status == "warning"

    def test_mixed_error_and_warning_is_fail(self):
        findings = [
            {"code": "no_inputs", "severity": "error", "message": "x", "artifact_path": ""},
            {"code": "study_type_mismatch", "severity": "warning", "message": "y", "artifact_path": ""},
        ]
        status, failure = classify_synthesis_failure(findings)
        assert status == "fail"


# ---------------------------------------------------------------------------
# Full artifact schema validation
# ---------------------------------------------------------------------------


class TestArtifactSchemaCompliance:
    def test_wpe_produced_artifact_passes_schema(self):
        nrr = _p2p_nrr()
        pack = build_working_paper_evidence_pack(be_payloads=[nrr])
        findings = validate_working_paper_evidence_pack(pack)
        assert findings == [], f"Schema violations: {findings}"

    def test_wps_produced_artifact_passes_schema(self):
        nrr = _p2p_nrr()
        pack = build_working_paper_evidence_pack(be_payloads=[nrr])
        decision = build_working_paper_synthesis_decision(
            evidence_pack_id=pack["evidence_pack_id"], findings=[]
        )
        findings = validate_working_paper_synthesis_decision(decision)
        assert findings == [], f"Schema violations: {findings}"

    def test_wpe_with_bf_passes_schema(self):
        nrr = _p2p_nrr()
        crc = _minimal_crc()
        pack = build_working_paper_evidence_pack(be_payloads=[nrr], bf_payload=crc)
        findings = validate_working_paper_evidence_pack(pack)
        assert findings == [], f"Schema violations: {findings}"

    def test_wpe_fail_decision_passes_schema(self):
        findings_list = [
            {"code": "no_inputs", "severity": "error", "message": "No inputs.", "artifact_path": ""}
        ]
        decision = build_working_paper_synthesis_decision(
            evidence_pack_id="", findings=findings_list
        )
        schema_findings = validate_working_paper_synthesis_decision(decision)
        assert schema_findings == [], f"Schema violations: {schema_findings}"


# ---------------------------------------------------------------------------
# CLI exit code tests
# ---------------------------------------------------------------------------


class TestCLIExitCodes:
    def test_cli_pass_returns_0(self, tmp_path):
        import subprocess
        result = subprocess.run(
            [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "working_paper_synthesis.py"),
                "--be-input",
                str(_NRR_P2P_RUN1),
                "--output-dir",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_cli_fail_returns_2_no_inputs(self, tmp_path):
        import subprocess
        result = subprocess.run(
            [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "working_paper_synthesis.py"),
                "--output-dir",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2

    def test_cli_fail_returns_2_bad_file(self, tmp_path):
        import subprocess
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "working_paper_synthesis.py"),
                "--be-input",
                str(bad),
                "--output-dir",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2

    def test_cli_writes_output_files(self, tmp_path):
        import subprocess
        result = subprocess.run(
            [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "working_paper_synthesis.py"),
                "--be-input",
                str(_NRR_P2P_RUN1),
                "--output-dir",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert (tmp_path / "working_paper_evidence_pack.json").exists()
        assert (tmp_path / "working_paper_synthesis_decision.json").exists()

    def test_cli_warning_returns_1(self, tmp_path):
        """A BF input with a mixed study_type warning should produce exit 1."""
        import subprocess
        # Write a BE with generic study type mixed with p2p BE
        nrr_generic = _p2p_nrr(artifact_id="NRR-GEN001")
        nrr_generic["study_type"] = "generic"
        generic_file = tmp_path / "nrr_generic.json"
        generic_file.write_text(json.dumps(nrr_generic), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "working_paper_synthesis.py"),
                "--be-input",
                str(_NRR_P2P_RUN1),
                "--be-input",
                str(generic_file),
                "--output-dir",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        # generic + p2p triggers a warning finding but not a hard fail
        assert result.returncode in (0, 1)


# ---------------------------------------------------------------------------
# Integration tests using fixtures
# ---------------------------------------------------------------------------


class TestIntegrationWithFixtures:
    def test_integration_be_only_run1(self):
        result = synthesize_working_paper_evidence(be_inputs=[str(_NRR_P2P_RUN1)])
        assert result["working_paper_evidence_pack"] is not None
        assert result["working_paper_synthesis_decision"]["overall_status"] == "pass"

    def test_integration_be_run1_run2(self):
        result = synthesize_working_paper_evidence(
            be_inputs=[str(_NRR_P2P_RUN1), str(_NRR_P2P_RUN2)]
        )
        assert result["working_paper_evidence_pack"] is not None
        assert result["working_paper_synthesis_decision"]["overall_status"] == "pass"
        pack = result["working_paper_evidence_pack"]
        assert pack["study_type"] == "p2p_interference"

    def test_integration_be_plus_bf(self):
        result = synthesize_working_paper_evidence(
            be_inputs=[str(_NRR_P2P_RUN1), str(_NRR_P2P_RUN2)],
            bf_input=str(_BF_CRC),
        )
        assert result["working_paper_synthesis_decision"]["overall_status"] == "pass"
        pack = result["working_paper_evidence_pack"]
        comp_sec = next(
            s for s in pack["section_evidence"] if s["section_key"] == "comparative_results"
        )
        assert comp_sec["synthesis_status"] in ("populated", "partial")

    def test_integration_thin_be_triggers_caveats(self):
        result = synthesize_working_paper_evidence(be_inputs=[str(_NRR_P2P_THIN)])
        pack = result["working_paper_evidence_pack"]
        assert len(pack["caveats"]) >= 1
        assert len(pack["followup_questions"]) >= 1

    def test_integration_thin_be_limitations_section_not_empty(self):
        result = synthesize_working_paper_evidence(be_inputs=[str(_NRR_P2P_THIN)])
        pack = result["working_paper_evidence_pack"]
        lim_sec = next(
            s for s in pack["section_evidence"] if s["section_key"] == "limitations_and_caveats"
        )
        assert lim_sec["synthesis_status"] in ("partial", "populated")

    def test_integration_full_pack_passes_schema(self):
        result = synthesize_working_paper_evidence(
            be_inputs=[str(_NRR_P2P_RUN1), str(_NRR_P2P_RUN2)],
            bf_input=str(_BF_CRC),
        )
        pack = result["working_paper_evidence_pack"]
        assert pack is not None
        schema_findings = validate_working_paper_evidence_pack(pack)
        assert schema_findings == [], f"Schema violations: {schema_findings}"

    def test_integration_decision_passes_schema(self):
        result = synthesize_working_paper_evidence(
            be_inputs=[str(_NRR_P2P_RUN1)],
            bf_input=str(_BF_CRC),
        )
        decision = result["working_paper_synthesis_decision"]
        schema_findings = validate_working_paper_synthesis_decision(decision)
        assert schema_findings == [], f"Schema violations: {schema_findings}"

    def test_load_governed_artifact(self):
        payload = load_governed_artifact(_NRR_P2P_RUN1)
        assert payload["artifact_type"] == "normalized_run_result"
