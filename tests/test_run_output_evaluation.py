"""Tests for BE run output normalization + evaluation layer (Prompt BE).

Covers:
- schema validation success for both artifacts
- schema rejection for extra properties
- missing results_summary_json file
- missing provenance_json file
- malformed JSON input
- p2p_interference normalization from flat scalar fields
- normalization from metrics list form
- normalization from nested results form
- completeness for full / partial / insufficient cases
- threshold pass / fail / unknown cases
- outlier flag detection for NaN / inf / extreme values
- generic study type behavior
- decision classification mapping
- CLI exit code behavior
- integration using a realistic fixture bundle
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.run_output_evaluation import (  # noqa: E402
    build_normalized_run_result,
    build_run_output_evaluation_decision,
    build_threshold_assessments,
    classify_evaluation_failure,
    compute_completeness,
    compute_readiness,
    detect_outlier_flags,
    evaluate_run_outputs,
    extract_provenance,
    extract_results_summary,
    get_required_metrics_for_study_type,
    infer_study_type,
    load_json_file,
    normalize_summary_metrics,
    resolve_manifest_output_paths,
    validate_normalized_run_result,
    validate_run_output_evaluation_decision,
)

_NRR_SCHEMA_PATH = _REPO_ROOT / "contracts" / "schemas" / "normalized_run_result.schema.json"
_ROE_SCHEMA_PATH = (
    _REPO_ROOT / "contracts" / "schemas" / "run_output_evaluation_decision.schema.json"
)
_FIXTURE_BUNDLE = _REPO_ROOT / "tests" / "fixtures" / "be_bundle"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_manifest() -> Dict[str, Any]:
    return {
        "bundle_version": "1.0.0",
        "run_id": "run-test-be-001",
        "matlab_release": "R2024b",
        "runtime_version_required": "R2024b",
        "platform": "linux-x86_64",
        "worker_entrypoint": "bin/run.sh",
        "component_cache": {"mcr_cache_root": "/tmp", "mcr_cache_size": "2GB"},
        "startup_options": {"logfile": "logs/worker.log"},
        "inputs": [{"path": "inputs/cases.json", "type": "case_definition", "required": True}],
        "expected_outputs": [
            {
                "path": "outputs/results_summary.json",
                "type": "results_summary_json",
                "required": True,
                "paper_relevant": True,
            },
            {
                "path": "outputs/provenance.json",
                "type": "provenance_json",
                "required": True,
                "paper_relevant": False,
            },
            {
                "path": "logs/worker.log",
                "type": "log_file",
                "required": True,
                "paper_relevant": False,
            },
        ],
        "provenance": {
            "source_artifact_ids": ["artifact-001"],
            "source_case_ids": ["case-001"],
            "rng_seed": 42,
            "manifest_author": "test-agent",
            "creation_context": "Unit test run.",
        },
        "execution_policy": {
            "idempotency_mode": "safe_rerun",
            "retry_allowed": False,
            "max_retries": 0,
            "stale_claim_timeout_hours": 1.0,
        },
        "study_type": "p2p_interference",
        "created_at": "2024-01-01T00:00:00Z",
    }


def _p2p_results_summary() -> Dict[str, Any]:
    return {
        "study_type": "p2p_interference",
        "metrics": [
            {"name": "interference_power_dbm", "value": -85.3, "unit": "dBm"},
            {"name": "in_ratio_db", "value": 12.7, "unit": "dB"},
            {"name": "path_loss_db", "value": 142.5, "unit": "dB"},
        ],
    }


def _provenance_json() -> Dict[str, Any]:
    return {"run_id": "run-test-be-001", "rng_seed": 42, "generated_by": "test"}


# ---------------------------------------------------------------------------
# Schema file checks
# ---------------------------------------------------------------------------


def test_nrr_schema_file_exists():
    assert _NRR_SCHEMA_PATH.exists(), f"Schema not found: {_NRR_SCHEMA_PATH}"


def test_roe_schema_file_exists():
    assert _ROE_SCHEMA_PATH.exists(), f"Schema not found: {_ROE_SCHEMA_PATH}"


def test_nrr_schema_is_valid_json():
    schema = json.loads(_NRR_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema.get("$schema") is not None
    assert schema.get("type") == "object"


def test_roe_schema_is_valid_json():
    schema = json.loads(_ROE_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema.get("$schema") is not None
    assert schema.get("type") == "object"


# ---------------------------------------------------------------------------
# load_json_file
# ---------------------------------------------------------------------------


def test_load_json_file_returns_parsed_content(tmp_path):
    f = tmp_path / "test.json"
    f.write_text('{"key": "value"}', encoding="utf-8")
    result = load_json_file(f)
    assert result == {"key": "value"}


def test_load_json_file_raises_oserror_for_missing(tmp_path):
    with pytest.raises(OSError):
        load_json_file(tmp_path / "nonexistent.json")


def test_load_json_file_raises_json_decode_error_for_bad_json(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_json_file(f)


# ---------------------------------------------------------------------------
# resolve_manifest_output_paths
# ---------------------------------------------------------------------------


def test_resolve_paths_returns_none_when_no_bundle_root():
    manifest = _valid_manifest()
    result = resolve_manifest_output_paths(manifest, bundle_root=None)
    assert result["results_summary_path"] is None
    assert result["provenance_path"] is None


def test_resolve_paths_returns_absolute_paths_with_bundle_root(tmp_path):
    manifest = _valid_manifest()
    result = resolve_manifest_output_paths(manifest, bundle_root=tmp_path)
    assert result["results_summary_path"] == tmp_path / "outputs/results_summary.json"
    assert result["provenance_path"] == tmp_path / "outputs/provenance.json"


# ---------------------------------------------------------------------------
# infer_study_type
# ---------------------------------------------------------------------------


def test_infer_study_type_from_manifest():
    manifest = _valid_manifest()
    manifest["study_type"] = "adjacency_analysis"
    assert infer_study_type(manifest, {}) == "adjacency_analysis"


def test_infer_study_type_from_results_summary():
    manifest = _valid_manifest()
    del manifest["study_type"]
    rs = {"study_type": "retuning_analysis"}
    assert infer_study_type(manifest, rs) == "retuning_analysis"


def test_infer_study_type_fallback_to_generic():
    manifest = _valid_manifest()
    del manifest["study_type"]
    assert infer_study_type(manifest, {}) == "generic"


def test_infer_study_type_unknown_value_falls_back():
    manifest = _valid_manifest()
    manifest["study_type"] = "not_a_valid_type"
    assert infer_study_type(manifest, {}) == "generic"


# ---------------------------------------------------------------------------
# get_required_metrics_for_study_type
# ---------------------------------------------------------------------------


def test_required_metrics_p2p_interference():
    metrics = get_required_metrics_for_study_type("p2p_interference")
    assert "interference_power_dbm" in metrics
    assert "in_ratio_db" in metrics
    assert "path_loss_db" in metrics


def test_required_metrics_generic_is_empty():
    assert get_required_metrics_for_study_type("generic") == []


def test_required_metrics_adjacency_analysis():
    metrics = get_required_metrics_for_study_type("adjacency_analysis")
    assert "frequency_separation_mhz" in metrics
    assert "interference_power_dbm" in metrics


# ---------------------------------------------------------------------------
# normalize_summary_metrics — different input shapes
# ---------------------------------------------------------------------------


def test_normalize_from_metrics_list():
    rs = {
        "metrics": [
            {"name": "interference_power_dbm", "value": -85.3, "unit": "dBm"},
            {"name": "in_ratio_db", "value": 12.7, "unit": "dB"},
            {"name": "path_loss_db", "value": 142.5, "unit": "dB"},
        ]
    }
    result = normalize_summary_metrics("p2p_interference", rs)
    names = [m["name"] for m in result]
    assert "interference_power_dbm" in names
    assert "in_ratio_db" in names
    assert "path_loss_db" in names


def test_normalize_from_summary_metrics_list():
    rs = {
        "summary_metrics": [
            {"name": "interference_power_dbm", "value": -90.0, "unit": "dBm"},
        ]
    }
    result = normalize_summary_metrics("p2p_interference", rs)
    assert any(m["name"] == "interference_power_dbm" for m in result)


def test_normalize_from_flat_scalars():
    rs = {
        "interference_power_dbm": -85.3,
        "in_ratio_db": 12.7,
        "path_loss_db": 142.5,
    }
    result = normalize_summary_metrics("p2p_interference", rs)
    names = [m["name"] for m in result]
    assert "interference_power_dbm" in names


def test_normalize_from_nested_results():
    rs = {
        "results": {
            "metrics": [
                {"name": "interference_power_dbm", "value": -85.3, "unit": "dBm"},
                {"name": "in_ratio_db", "value": 12.7, "unit": "dB"},
            ]
        }
    }
    result = normalize_summary_metrics("p2p_interference", rs)
    assert any(m["name"] == "interference_power_dbm" for m in result)


def test_normalize_classification_core_for_required():
    rs = {"metrics": [{"name": "interference_power_dbm", "value": -85.3, "unit": "dBm"}]}
    result = normalize_summary_metrics("p2p_interference", rs)
    for m in result:
        if m["name"] == "interference_power_dbm":
            assert m["classification"] == "core"


def test_normalize_classification_supporting_for_non_required():
    rs = {"metrics": [{"name": "some_extra_metric", "value": 10.0, "unit": ""}]}
    result = normalize_summary_metrics("p2p_interference", rs)
    for m in result:
        if m["name"] == "some_extra_metric":
            assert m["classification"] == "supporting"


def test_normalize_source_path_present():
    rs = {"metrics": [{"name": "interference_power_dbm", "value": -85.3, "unit": "dBm"}]}
    result = normalize_summary_metrics("p2p_interference", rs)
    for m in result:
        assert "source_path" in m
        assert m["source_path"] != ""


# ---------------------------------------------------------------------------
# compute_completeness
# ---------------------------------------------------------------------------


def test_completeness_complete():
    required = get_required_metrics_for_study_type("p2p_interference")
    rs = {
        "metrics": [
            {"name": "interference_power_dbm", "value": -85.0, "unit": "dBm"},
            {"name": "in_ratio_db", "value": 12.0, "unit": "dB"},
            {"name": "path_loss_db", "value": 140.0, "unit": "dB"},
        ]
    }
    metrics = normalize_summary_metrics("p2p_interference", rs)
    result = compute_completeness(required, metrics)
    assert result["status"] == "complete"
    assert result["missing_required_metrics"] == []
    assert result["present_required_metric_count"] == 3


def test_completeness_partial():
    required = get_required_metrics_for_study_type("p2p_interference")
    rs = {"metrics": [{"name": "interference_power_dbm", "value": -85.0, "unit": "dBm"}]}
    metrics = normalize_summary_metrics("p2p_interference", rs)
    result = compute_completeness(required, metrics)
    assert result["status"] == "partial"
    assert "in_ratio_db" in result["missing_required_metrics"]
    assert "path_loss_db" in result["missing_required_metrics"]


def test_completeness_insufficient():
    required = get_required_metrics_for_study_type("p2p_interference")
    metrics = normalize_summary_metrics("p2p_interference", {})
    result = compute_completeness(required, metrics)
    assert result["status"] == "insufficient"
    assert result["present_required_metric_count"] == 0
    assert len(result["missing_required_metrics"]) == 3


def test_completeness_generic_with_no_metrics_is_complete():
    result = compute_completeness([], [])
    assert result["status"] == "complete"


# ---------------------------------------------------------------------------
# build_threshold_assessments
# ---------------------------------------------------------------------------


def test_threshold_pass():
    metrics = [{"name": "path_loss_db", "value": 100.0, "unit": "dB", "classification": "core", "source_path": ""}]
    manifest = {
        "evaluation_thresholds": [
            {"metric_name": "path_loss_db", "threshold_name": "max_path_loss", "operator": "lte", "value": 150.0}
        ]
    }
    results = build_threshold_assessments("p2p_interference", metrics, manifest, {})
    assert len(results) == 1
    assert results[0]["status"] == "pass"


def test_threshold_fail():
    metrics = [{"name": "path_loss_db", "value": 200.0, "unit": "dB", "classification": "core", "source_path": ""}]
    manifest = {
        "evaluation_thresholds": [
            {"metric_name": "path_loss_db", "threshold_name": "max_path_loss", "operator": "lte", "value": 150.0}
        ]
    }
    results = build_threshold_assessments("p2p_interference", metrics, manifest, {})
    assert results[0]["status"] == "fail"


def test_threshold_unknown_when_metric_absent():
    metrics = []
    manifest = {
        "evaluation_thresholds": [
            {"metric_name": "path_loss_db", "threshold_name": "max_path_loss", "operator": "lte", "value": 150.0}
        ]
    }
    results = build_threshold_assessments("p2p_interference", metrics, manifest, {})
    assert results[0]["status"] == "unknown"


def test_threshold_unknown_when_malformed():
    metrics = []
    manifest = {
        "evaluation_thresholds": [
            {"metric_name": "path_loss_db", "threshold_name": "max_path_loss"}  # missing operator + value
        ]
    }
    results = build_threshold_assessments("p2p_interference", metrics, manifest, {})
    assert results[0]["status"] == "unknown"


def test_threshold_from_results_summary():
    metrics = [{"name": "interference_power_dbm", "value": -85.0, "unit": "dBm", "classification": "core", "source_path": ""}]
    rs = {
        "evaluation_thresholds": [
            {"metric_name": "interference_power_dbm", "threshold_name": "min_interference", "operator": "gt", "value": -100.0}
        ]
    }
    results = build_threshold_assessments("p2p_interference", metrics, {}, rs)
    assert results[0]["status"] == "pass"


def test_threshold_empty_when_none_defined():
    metrics = [{"name": "interference_power_dbm", "value": -85.0, "unit": "dBm", "classification": "core", "source_path": ""}]
    results = build_threshold_assessments("p2p_interference", metrics, {}, {})
    assert results == []


# ---------------------------------------------------------------------------
# detect_outlier_flags
# ---------------------------------------------------------------------------


def test_outlier_nan():
    metrics = [{"name": "metric_a", "value": float("nan"), "unit": "", "classification": "core", "source_path": ""}]
    flags = detect_outlier_flags(metrics)
    assert any(f["flag_type"] == "nan_value" for f in flags)


def test_outlier_inf():
    metrics = [{"name": "metric_b", "value": float("inf"), "unit": "", "classification": "core", "source_path": ""}]
    flags = detect_outlier_flags(metrics)
    assert any(f["flag_type"] == "infinite_value" for f in flags)


def test_outlier_extreme():
    metrics = [{"name": "metric_c", "value": 2e13, "unit": "", "classification": "core", "source_path": ""}]
    flags = detect_outlier_flags(metrics)
    assert any(f["flag_type"] == "extreme_magnitude" for f in flags)


def test_no_outlier_for_normal_value():
    metrics = [{"name": "metric_d", "value": -85.0, "unit": "dBm", "classification": "core", "source_path": ""}]
    flags = detect_outlier_flags(metrics)
    assert flags == []


def test_outlier_ignores_bool_values():
    metrics = [{"name": "flag_field", "value": True, "unit": "", "classification": "supporting", "source_path": ""}]
    flags = detect_outlier_flags(metrics)
    assert flags == []


# ---------------------------------------------------------------------------
# compute_readiness
# ---------------------------------------------------------------------------


def test_readiness_ready_for_comparison():
    completeness = {"status": "complete", "missing_required_metrics": []}
    assert compute_readiness(completeness, [], []) == "ready_for_comparison"


def test_readiness_not_ready_insufficient():
    completeness = {"status": "insufficient", "missing_required_metrics": ["m1"]}
    assert compute_readiness(completeness, [], []) == "not_ready"


def test_readiness_not_ready_error_finding():
    completeness = {"status": "complete", "missing_required_metrics": []}
    findings = [{"severity": "error", "code": "schema_invalid", "message": "bad", "artifact_path": ""}]
    assert compute_readiness(completeness, [], findings) == "not_ready"


def test_readiness_limited_use_partial():
    completeness = {"status": "partial", "missing_required_metrics": ["m1"]}
    assert compute_readiness(completeness, [], []) == "limited_use"


def test_readiness_limited_use_threshold_fail():
    completeness = {"status": "complete", "missing_required_metrics": []}
    assessments = [{"metric_name": "x", "threshold_name": "t1", "status": "fail", "detail": ""}]
    assert compute_readiness(completeness, assessments, []) == "limited_use"


# ---------------------------------------------------------------------------
# classify_evaluation_failure
# ---------------------------------------------------------------------------


def test_classify_pass_when_no_findings():
    status, ft = classify_evaluation_failure([])
    assert status == "pass"
    assert ft == "none"


def test_classify_fail_on_error_finding():
    findings = [{"code": "missing_output_file", "severity": "error", "message": "x", "artifact_path": ""}]
    status, ft = classify_evaluation_failure(findings)
    assert status == "fail"
    assert ft == "missing_output_file"


def test_classify_warning_on_warning_finding():
    findings = [{"code": "outlier_detected", "severity": "warning", "message": "x", "artifact_path": ""}]
    status, ft = classify_evaluation_failure(findings)
    assert status == "warning"


def test_classify_highest_priority_failure_type():
    findings = [
        {"code": "semantic_incomplete", "severity": "error", "message": "x", "artifact_path": ""},
        {"code": "missing_output_file", "severity": "error", "message": "y", "artifact_path": ""},
    ]
    status, ft = classify_evaluation_failure(findings)
    assert ft == "missing_output_file"


# ---------------------------------------------------------------------------
# validate_normalized_run_result
# ---------------------------------------------------------------------------


def test_nrr_schema_valid_artifact():
    manifest = _valid_manifest()
    nrr = build_normalized_run_result(manifest, _p2p_results_summary(), _provenance_json())
    findings = validate_normalized_run_result(nrr)
    assert findings == [], f"Schema errors: {findings}"


def test_nrr_schema_rejects_extra_property():
    manifest = _valid_manifest()
    nrr = build_normalized_run_result(manifest, _p2p_results_summary(), _provenance_json())
    nrr["extra_field"] = "forbidden"
    findings = validate_normalized_run_result(nrr)
    assert any(f["code"] == "schema_invalid" for f in findings)


def test_nrr_schema_rejects_wrong_artifact_type():
    manifest = _valid_manifest()
    nrr = build_normalized_run_result(manifest, _p2p_results_summary(), _provenance_json())
    nrr["artifact_type"] = "wrong_type"
    findings = validate_normalized_run_result(nrr)
    assert any(f["code"] == "schema_invalid" for f in findings)


# ---------------------------------------------------------------------------
# validate_run_output_evaluation_decision
# ---------------------------------------------------------------------------


def test_roe_schema_valid_artifact():
    decision = build_run_output_evaluation_decision("run-test-001", [])
    findings = validate_run_output_evaluation_decision(decision)
    assert findings == [], f"Schema errors: {findings}"


def test_roe_schema_rejects_extra_property():
    decision = build_run_output_evaluation_decision("run-test-001", [])
    decision["extra_field"] = "forbidden"
    findings = validate_run_output_evaluation_decision(decision)
    assert any(f["code"] == "schema_invalid" for f in findings)


# ---------------------------------------------------------------------------
# evaluate_run_outputs — error cases
# ---------------------------------------------------------------------------


def test_evaluate_missing_results_summary_file(tmp_path):
    manifest = _valid_manifest()
    manifest_path = tmp_path / "run_bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    # Do NOT create the results_summary file
    result = evaluate_run_outputs(manifest_path=manifest_path, bundle_root=tmp_path)
    decision = result["run_output_evaluation_decision"]
    assert decision["overall_status"] == "fail"
    assert any(f["code"] == "missing_output_file" for f in result["findings"])


def test_evaluate_missing_provenance_file(tmp_path):
    manifest = _valid_manifest()
    manifest_path = tmp_path / "run_bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    # Create results_summary but NOT provenance
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    (outputs_dir / "results_summary.json").write_text(
        json.dumps(_p2p_results_summary()), encoding="utf-8"
    )
    result = evaluate_run_outputs(manifest_path=manifest_path, bundle_root=tmp_path)
    decision = result["run_output_evaluation_decision"]
    assert decision["overall_status"] == "fail"
    assert any(f["code"] == "missing_output_file" for f in result["findings"])


def test_evaluate_malformed_results_summary_json(tmp_path):
    manifest = _valid_manifest()
    manifest_path = tmp_path / "run_bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    (outputs_dir / "results_summary.json").write_text("not valid json", encoding="utf-8")
    result = evaluate_run_outputs(manifest_path=manifest_path, bundle_root=tmp_path)
    decision = result["run_output_evaluation_decision"]
    assert decision["overall_status"] == "fail"
    assert any(f["code"] == "malformed_json" for f in result["findings"])


def test_evaluate_manifest_payload_without_path():
    manifest = _valid_manifest()
    # Remove the expected_outputs paths so no file loading happens
    manifest["expected_outputs"] = [
        o for o in manifest["expected_outputs"] if o["type"] == "log_file"
    ]
    result = evaluate_run_outputs(manifest_payload=manifest)
    # Should not crash; will produce a result
    assert "run_output_evaluation_decision" in result


# ---------------------------------------------------------------------------
# evaluate_run_outputs — p2p_interference success path
# ---------------------------------------------------------------------------


def test_evaluate_p2p_success_path(tmp_path):
    manifest = _valid_manifest()
    manifest_path = tmp_path / "run_bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    (outputs_dir / "results_summary.json").write_text(
        json.dumps(_p2p_results_summary()), encoding="utf-8"
    )
    (outputs_dir / "provenance.json").write_text(
        json.dumps(_provenance_json()), encoding="utf-8"
    )
    result = evaluate_run_outputs(manifest_path=manifest_path, bundle_root=tmp_path)
    assert result["normalized_run_result"] is not None
    nrr = result["normalized_run_result"]
    assert nrr["study_type"] == "p2p_interference"
    assert nrr["metrics"]["completeness"]["status"] == "complete"
    assert nrr["evaluation_signals"]["readiness"] == "ready_for_comparison"
    decision = result["run_output_evaluation_decision"]
    assert decision["overall_status"] == "pass"


# ---------------------------------------------------------------------------
# Generic study type
# ---------------------------------------------------------------------------


def test_generic_study_type_completeness_is_complete():
    manifest = _valid_manifest()
    del manifest["study_type"]
    nrr = build_normalized_run_result(manifest, {}, _provenance_json())
    assert nrr["study_type"] == "generic"
    assert nrr["metrics"]["completeness"]["status"] == "complete"


def test_generic_study_type_readiness_ready_when_no_metrics():
    manifest = _valid_manifest()
    del manifest["study_type"]
    nrr = build_normalized_run_result(manifest, {}, _provenance_json())
    assert nrr["evaluation_signals"]["readiness"] == "ready_for_comparison"


# ---------------------------------------------------------------------------
# build_normalized_run_result — structure checks
# ---------------------------------------------------------------------------


def test_nrr_artifact_id_format():
    manifest = _valid_manifest()
    nrr = build_normalized_run_result(manifest, _p2p_results_summary(), _provenance_json())
    assert nrr["artifact_id"].startswith("NRR-")


def test_nrr_artifact_type():
    manifest = _valid_manifest()
    nrr = build_normalized_run_result(manifest, _p2p_results_summary(), _provenance_json())
    assert nrr["artifact_type"] == "normalized_run_result"


def test_nrr_source_bundle_id():
    manifest = _valid_manifest()
    nrr = build_normalized_run_result(manifest, _p2p_results_summary(), _provenance_json())
    assert nrr["source_bundle_id"] == "run-test-be-001"


def test_nrr_provenance_fields():
    manifest = _valid_manifest()
    nrr = build_normalized_run_result(manifest, _p2p_results_summary(), _provenance_json())
    prov = nrr["provenance"]
    assert prov["manifest_author"] == "test-agent"
    assert "case-001" in prov["source_case_ids"]
    assert prov["rng_reference"]["mode"] == "seed"
    assert prov["rng_reference"]["value"] == 42


# ---------------------------------------------------------------------------
# build_run_output_evaluation_decision — structure
# ---------------------------------------------------------------------------


def test_roe_decision_id_format():
    decision = build_run_output_evaluation_decision("run-001", [])
    assert decision["decision_id"].startswith("ROE-")


def test_roe_artifact_type():
    decision = build_run_output_evaluation_decision("run-001", [])
    assert decision["artifact_type"] == "run_output_evaluation_decision"


# ---------------------------------------------------------------------------
# Integration — fixture bundle
# ---------------------------------------------------------------------------


def test_fixture_bundle_exists():
    assert (_FIXTURE_BUNDLE / "run_bundle_manifest.json").exists()
    assert (_FIXTURE_BUNDLE / "outputs" / "results_summary.json").exists()
    assert (_FIXTURE_BUNDLE / "outputs" / "provenance.json").exists()


def test_fixture_bundle_integration(tmp_path):
    # Copy fixture bundle to tmp_path so we can write outputs there
    import shutil
    bundle_copy = tmp_path / "be_bundle"
    shutil.copytree(str(_FIXTURE_BUNDLE), str(bundle_copy))
    result = evaluate_run_outputs(
        manifest_path=bundle_copy / "run_bundle_manifest.json",
        bundle_root=bundle_copy,
    )
    nrr = result["normalized_run_result"]
    assert nrr is not None
    assert nrr["study_type"] == "p2p_interference"
    assert nrr["metrics"]["completeness"]["status"] == "complete"
    decision = result["run_output_evaluation_decision"]
    assert decision["overall_status"] == "pass"
    schema_findings = validate_normalized_run_result(nrr)
    assert schema_findings == [], f"NRR schema errors: {schema_findings}"
    decision_findings = validate_run_output_evaluation_decision(decision)
    assert decision_findings == [], f"ROE schema errors: {decision_findings}"


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_cli_pass_exit_code(tmp_path):
    from scripts.run_output_evaluation import main

    manifest = _valid_manifest()
    manifest_path = tmp_path / "run_bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    (outputs_dir / "results_summary.json").write_text(
        json.dumps(_p2p_results_summary()), encoding="utf-8"
    )
    (outputs_dir / "provenance.json").write_text(
        json.dumps(_provenance_json()), encoding="utf-8"
    )
    exit_code = main(["--manifest", str(manifest_path)])
    assert exit_code == 0


def test_cli_fail_exit_code_missing_output(tmp_path):
    from scripts.run_output_evaluation import main

    manifest = _valid_manifest()
    manifest_path = tmp_path / "run_bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    exit_code = main(["--manifest", str(manifest_path)])
    assert exit_code == 2


def test_cli_bundle_root_pass(tmp_path):
    from scripts.run_output_evaluation import main

    manifest = _valid_manifest()
    manifest_path = tmp_path / "run_bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    (outputs_dir / "results_summary.json").write_text(
        json.dumps(_p2p_results_summary()), encoding="utf-8"
    )
    (outputs_dir / "provenance.json").write_text(
        json.dumps(_provenance_json()), encoding="utf-8"
    )
    exit_code = main(["--bundle-root", str(tmp_path)])
    assert exit_code == 0


def test_cli_bundle_root_missing_manifest(tmp_path):
    from scripts.run_output_evaluation import main

    exit_code = main(["--bundle-root", str(tmp_path)])
    assert exit_code == 2


def test_cli_writes_output_files(tmp_path, monkeypatch):
    import scripts.run_output_evaluation as roe_mod

    manifest = _valid_manifest()
    manifest_path = tmp_path / "run_bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    (outputs_dir / "results_summary.json").write_text(
        json.dumps(_p2p_results_summary()), encoding="utf-8"
    )
    (outputs_dir / "provenance.json").write_text(
        json.dumps(_provenance_json()), encoding="utf-8"
    )

    archive_dir = tmp_path / "archive"
    monkeypatch.setattr(roe_mod, "_ARCHIVE_DIR", archive_dir)

    roe_mod.main(["--manifest", str(manifest_path)])

    assert (outputs_dir / "normalized_run_result.json").exists()
    assert (outputs_dir / "run_output_evaluation_decision.json").exists()
    archived = list(archive_dir.glob("*.json"))
    assert len(archived) == 1
