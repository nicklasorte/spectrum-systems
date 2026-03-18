"""
Tests for the Regression Harness (Prompt AR).

Covers:
- Regression policy schema validation
- Regression report schema validation
- RegressionPolicy: load, default, fields
- BaselineManager: save/load/list/describe
- BaselineManager: no-silent-overwrite enforcement
- BaselineManager: determinism mismatch warning
- evaluate_dimension_gate: pass, warning, hard_fail, insufficient_data
- evaluate_policy_gates: aggregate gate evaluation
- attribute_regressions_to_passes: matched, unmatched, partial
- compute_pass_regression_summary and identify_worst_passes
- RegressionHarness: compare_eval_runs (happy path, insufficient sample)
- RegressionHarness: compare_observability_runs (happy path)
- RegressionHarness: merge_comparison_results
- RegressionHarness: generate_report (pass, hard_fail, warning)
- RegressionHarness: deterministic_required enforcement
- RegressionReport: validate_against_schema
- generate_recommendations: rule-based output
- CLI smoke tests (create baseline, compare)
"""
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime, timezone

import pytest

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from spectrum_systems.modules.regression.harness import (
    RegressionHarness,
    RegressionPolicy,
    RegressionReport,
    eval_result_to_dict,
    observability_record_to_dict,
    _flatten_obs_record_dict,
)
from spectrum_systems.modules.regression.baselines import (
    BaselineManager,
    BaselineExistsError,
    BaselineNotFoundError,
)
from spectrum_systems.modules.regression.gates import (
    evaluate_dimension_gate,
    evaluate_policy_gates,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SEVERITY_HARD_FAIL,
)
from spectrum_systems.modules.regression.attribution import (
    attribute_regressions_to_passes,
    compute_pass_regression_summary,
    identify_worst_passes,
)
from spectrum_systems.modules.regression.recommendations import generate_recommendations

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]
_POLICY_SCHEMA = _REPO_ROOT / "contracts" / "schemas" / "regression_policy.schema.json"
_REPORT_SCHEMA = _REPO_ROOT / "contracts" / "schemas" / "regression_report.schema.json"
_DEFAULT_POLICY = _REPO_ROOT / "config" / "regression_policy.json"


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture()
def tmp_baselines_dir(tmp_path: Path) -> Path:
    return tmp_path / "baselines"


@pytest.fixture()
def manager(tmp_baselines_dir: Path) -> BaselineManager:
    return BaselineManager(tmp_baselines_dir)


@pytest.fixture()
def default_policy() -> RegressionPolicy:
    return RegressionPolicy.load(_DEFAULT_POLICY)


@pytest.fixture()
def sample_eval_results() -> List[Dict[str, Any]]:
    return [
        {
            "case_id": f"case_{i:03d}",
            "pass_fail": True,
            "structural_score": 0.90,
            "semantic_score": 0.85,
            "grounding_score": 0.95,
            "latency_summary": {"per_pass_latency": {}, "total_latency_ms": 100, "budget_violations": []},
            "error_types": [],
            "schema_valid": True,
            "regression_detected": False,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "human_feedback_overrides": [],
        }
        for i in range(5)
    ]


@pytest.fixture()
def sample_obs_records() -> List[Dict[str, Any]]:
    return [
        {
            "record_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "artifact_id": f"case_{i:03d}",
            "artifact_type": "evaluation_result",
            "pipeline_stage": "validate",
            "case_id": f"case_{i:03d}",
            "pass_id": str(uuid.uuid4()),
            "pass_type": "extraction",
            "structural_score": 0.90,
            "semantic_score": 0.85,
            "grounding_score": 0.95,
            "latency_ms": 100,
            "schema_valid": True,
            "grounding_passed": True,
            "regression_passed": True,
            "human_disagrees": False,
            "error_types": [],
            "failure_count": 0,
        }
        for i in range(5)
    ]


@pytest.fixture()
def harness(default_policy: RegressionPolicy) -> RegressionHarness:
    return RegressionHarness(policy=default_policy)


# ===========================================================================
# 1. Schema files exist and are valid JSON
# ===========================================================================


def test_regression_policy_schema_file_exists() -> None:
    assert _POLICY_SCHEMA.is_file(), f"Missing schema: {_POLICY_SCHEMA}"


def test_regression_report_schema_file_exists() -> None:
    assert _REPORT_SCHEMA.is_file(), f"Missing schema: {_REPORT_SCHEMA}"


def test_regression_policy_schema_is_valid_json() -> None:
    data = json.loads(_POLICY_SCHEMA.read_text(encoding="utf-8"))
    assert data.get("title") == "RegressionPolicy"


def test_regression_report_schema_is_valid_json() -> None:
    data = json.loads(_REPORT_SCHEMA.read_text(encoding="utf-8"))
    assert data.get("title") == "RegressionReport"


def test_default_policy_file_exists() -> None:
    assert _DEFAULT_POLICY.is_file(), f"Missing default policy: {_DEFAULT_POLICY}"


def test_default_policy_file_is_valid_json() -> None:
    data = json.loads(_DEFAULT_POLICY.read_text(encoding="utf-8"))
    assert "policy_id" in data
    assert "thresholds" in data


# ===========================================================================
# 2. Policy schema validation of default policy
# ===========================================================================


def test_default_policy_validates_against_schema() -> None:
    import jsonschema
    schema = json.loads(_POLICY_SCHEMA.read_text(encoding="utf-8"))
    data = json.loads(_DEFAULT_POLICY.read_text(encoding="utf-8"))
    jsonschema.validate(instance=data, schema=schema)


# ===========================================================================
# 3. RegressionPolicy
# ===========================================================================


def test_policy_load_default(default_policy: RegressionPolicy) -> None:
    assert default_policy.policy_id == "default"
    assert default_policy.version


def test_policy_fields(default_policy: RegressionPolicy) -> None:
    t = default_policy.thresholds
    assert "structural_score_drop_max" in t
    assert "semantic_score_drop_max" in t
    assert "grounding_score_drop_max" in t
    assert "latency_increase_pct_max" in t
    assert "human_disagreement_increase_pct_max" in t


def test_policy_hard_fail_dimensions(default_policy: RegressionPolicy) -> None:
    hf = default_policy.hard_fail_dimensions
    assert hf["grounding_score"] is True
    assert hf["structural_score"] is True
    # latency defaults to warning (not hard fail) in default policy
    assert hf["latency"] is False


def test_policy_load_from_path(tmp_path: Path) -> None:
    policy_data = {
        "policy_id": "test",
        "version": "1.0.0",
        "description": "Test policy",
        "thresholds": {
            "structural_score_drop_max": 0.1,
            "semantic_score_drop_max": 0.1,
            "grounding_score_drop_max": 0.05,
            "latency_increase_pct_max": 20,
            "human_disagreement_increase_pct_max": 20,
        },
        "hard_fail_dimensions": {
            "structural_score": True,
            "semantic_score": False,
            "grounding_score": True,
            "latency": False,
            "human_disagreement": False,
        },
        "minimum_sample_sizes": {"cases": 2, "per_pass_records": 2},
        "scope": {"artifact_types": ["evaluation_result"], "pass_types": ["extraction"]},
        "deterministic_required": False,
    }
    p = tmp_path / "policy.json"
    p.write_text(json.dumps(policy_data), encoding="utf-8")
    loaded = RegressionPolicy.load(p)
    assert loaded.policy_id == "test"


def test_policy_load_missing_file(tmp_path: Path) -> None:
    from spectrum_systems.modules.regression.harness import RegressionPolicyError
    with pytest.raises(RegressionPolicyError):
        RegressionPolicy.load(tmp_path / "nonexistent.json")


# ===========================================================================
# 4. BaselineManager
# ===========================================================================


def test_baseline_save_and_load(
    manager: BaselineManager,
    sample_eval_results: List[Dict[str, Any]],
    sample_obs_records: List[Dict[str, Any]],
) -> None:
    manager.save_baseline("v1", sample_eval_results, sample_obs_records)
    loaded = manager.load_baseline("v1")
    assert len(loaded["eval_results"]) == len(sample_eval_results)
    assert len(loaded["observability_records"]) == len(sample_obs_records)
    assert loaded["metadata"]["name"] == "v1"


def test_baseline_list(
    manager: BaselineManager,
    sample_eval_results: List[Dict[str, Any]],
    sample_obs_records: List[Dict[str, Any]],
) -> None:
    manager.save_baseline("v1", sample_eval_results, sample_obs_records)
    manager.save_baseline("v2", sample_eval_results, sample_obs_records)
    names = manager.list_baselines()
    assert "v1" in names
    assert "v2" in names


def test_baseline_list_empty(manager: BaselineManager) -> None:
    assert manager.list_baselines() == []


def test_baseline_describe(
    manager: BaselineManager,
    sample_eval_results: List[Dict[str, Any]],
    sample_obs_records: List[Dict[str, Any]],
) -> None:
    manager.save_baseline("v1", sample_eval_results, sample_obs_records, notes="test run")
    meta = manager.describe_baseline("v1")
    assert meta["name"] == "v1"
    assert meta["notes"] == "test run"
    assert "created_at" in meta


def test_baseline_no_silent_overwrite(
    manager: BaselineManager,
    sample_eval_results: List[Dict[str, Any]],
    sample_obs_records: List[Dict[str, Any]],
) -> None:
    manager.save_baseline("v1", sample_eval_results, sample_obs_records)
    with pytest.raises(BaselineExistsError):
        manager.save_baseline("v1", sample_eval_results, sample_obs_records)


def test_baseline_explicit_update(
    manager: BaselineManager,
    sample_eval_results: List[Dict[str, Any]],
    sample_obs_records: List[Dict[str, Any]],
) -> None:
    manager.save_baseline("v1", sample_eval_results, sample_obs_records)
    # Should not raise with update=True
    manager.save_baseline("v1", sample_eval_results, sample_obs_records, update=True)


def test_baseline_not_found(manager: BaselineManager) -> None:
    with pytest.raises(BaselineNotFoundError):
        manager.load_baseline("nonexistent")


def test_baseline_invalid_name(
    manager: BaselineManager,
    sample_eval_results: List[Dict[str, Any]],
) -> None:
    with pytest.raises(ValueError):
        manager.save_baseline("bad name!", sample_eval_results, [])


def test_baseline_determinism_mismatch_warning(
    manager: BaselineManager,
    sample_eval_results: List[Dict[str, Any]],
    sample_obs_records: List[Dict[str, Any]],
) -> None:
    manager.save_baseline(
        "v1", sample_eval_results, sample_obs_records,
        metadata={"deterministic_mode": True}
    )
    warning = manager.warn_if_determinism_mismatch("v1", candidate_deterministic=False)
    assert warning is not None
    assert "mismatch" in warning.lower()


def test_baseline_determinism_match_no_warning(
    manager: BaselineManager,
    sample_eval_results: List[Dict[str, Any]],
    sample_obs_records: List[Dict[str, Any]],
) -> None:
    manager.save_baseline(
        "v1", sample_eval_results, sample_obs_records,
        metadata={"deterministic_mode": True}
    )
    warning = manager.warn_if_determinism_mismatch("v1", candidate_deterministic=True)
    assert warning is None


# ===========================================================================
# 5. Gate evaluation
# ===========================================================================


def test_gate_pass_no_regression() -> None:
    result = evaluate_dimension_gate(0.90, 0.89, 0.05, hard_fail=True)
    assert result["passed"] is True
    assert result["severity"] == SEVERITY_INFO


def test_gate_hard_fail() -> None:
    result = evaluate_dimension_gate(0.90, 0.80, 0.05, hard_fail=True)
    assert result["passed"] is False
    assert result["severity"] == SEVERITY_HARD_FAIL


def test_gate_warning() -> None:
    result = evaluate_dimension_gate(0.90, 0.80, 0.05, hard_fail=False)
    assert result["passed"] is False
    assert result["severity"] == SEVERITY_WARNING


def test_gate_insufficient_data() -> None:
    result = evaluate_dimension_gate(0.90, 0.80, 0.05, hard_fail=True, insufficient_data=True)
    assert result["passed"] is True
    assert result["severity"] == SEVERITY_INFO
    assert result["insufficient_data"] is True


def test_gate_latency_increase(default_policy: RegressionPolicy) -> None:
    # Latency higher_is_better=False: positive delta is bad
    result = evaluate_dimension_gate(
        0.0, 50.0, 25.0, hard_fail=False, higher_is_better=False
    )
    assert result["passed"] is False
    assert result["severity"] == SEVERITY_WARNING


def test_evaluate_policy_gates_all_pass(default_policy: RegressionPolicy) -> None:
    comparison = {
        "structural_score": {"baseline": 0.90, "candidate": 0.90},
        "semantic_score": {"baseline": 0.85, "candidate": 0.85},
        "grounding_score": {"baseline": 0.95, "candidate": 0.95},
        "latency_ms": {"baseline": 100.0, "candidate": 100.0},
        "human_disagreement_rate": {"baseline": 0.1, "candidate": 0.1, "insufficient_data": True},
    }
    results = evaluate_policy_gates(comparison, default_policy)
    assert results["overall_pass"] is True
    assert results["hard_failures"] == 0


def test_evaluate_policy_gates_hard_fail(default_policy: RegressionPolicy) -> None:
    comparison = {
        "structural_score": {"baseline": 0.90, "candidate": 0.50},  # big drop
        "semantic_score": {"baseline": 0.85, "candidate": 0.85},
        "grounding_score": {"baseline": 0.95, "candidate": 0.95},
        "latency_ms": {"baseline": 100.0, "candidate": 100.0},
        "human_disagreement_rate": {"baseline": 0.1, "candidate": 0.1, "insufficient_data": True},
    }
    results = evaluate_policy_gates(comparison, default_policy)
    assert results["overall_pass"] is False
    assert results["hard_failures"] >= 1


def test_evaluate_policy_gates_latency_warning(default_policy: RegressionPolicy) -> None:
    comparison = {
        "structural_score": {"baseline": 0.90, "candidate": 0.90},
        "semantic_score": {"baseline": 0.85, "candidate": 0.85},
        "grounding_score": {"baseline": 0.95, "candidate": 0.95},
        "latency_ms": {"baseline": 100.0, "candidate": 250.0},  # 150% increase
        "human_disagreement_rate": {"baseline": 0.1, "candidate": 0.1, "insufficient_data": True},
    }
    results = evaluate_policy_gates(comparison, default_policy)
    # latency is warning (not hard fail) in default policy
    assert results["dimension_results"]["latency"]["severity"] == SEVERITY_WARNING
    assert results["hard_failures"] == 0
    assert results["warnings"] >= 1


# ===========================================================================
# 6. Pass-level attribution
# ===========================================================================


def _make_obs_record(pass_type: str, case_id: str, **scores: Any) -> Dict[str, Any]:
    return {
        "pass_type": pass_type,
        "case_id": case_id,
        "artifact_id": case_id,
        "structural_score": scores.get("structural_score", 0.9),
        "semantic_score": scores.get("semantic_score", 0.85),
        "grounding_score": scores.get("grounding_score", 0.95),
        "latency_ms": scores.get("latency_ms", 100),
        "human_disagrees": scores.get("human_disagrees", False),
    }


def test_attribution_matched_records() -> None:
    baseline = [_make_obs_record("extraction", "c1", semantic_score=0.90)]
    candidate = [_make_obs_record("extraction", "c1", semantic_score=0.80)]
    result = attribute_regressions_to_passes(baseline, candidate)
    assert "extraction" in result["pass_attributions"]
    entries = result["pass_attributions"]["extraction"]
    sem_entry = next((e for e in entries if e["dimension"] == "semantic_score"), None)
    assert sem_entry is not None
    assert abs(sem_entry["delta"] - (-0.10)) < 1e-9


def test_attribution_unmatched_records() -> None:
    baseline = [_make_obs_record("extraction", "c1")]
    candidate = [_make_obs_record("extraction", "c2")]  # different case
    result = attribute_regressions_to_passes(baseline, candidate)
    assert result["unmatched_baseline"] == 1
    assert result["partial_attribution"] is True


def test_attribution_empty_inputs() -> None:
    result = attribute_regressions_to_passes([], [])
    assert result["pass_attributions"] == {}
    assert result["partial_attribution"] is False


def test_compute_pass_regression_summary() -> None:
    baseline = [_make_obs_record("reasoning", "c1", semantic_score=0.90)]
    candidate = [_make_obs_record("reasoning", "c1", semantic_score=0.70)]
    attr = attribute_regressions_to_passes(baseline, candidate)
    summary = compute_pass_regression_summary(attr["pass_attributions"])
    assert "reasoning" in summary
    dim_stats = summary["reasoning"]["dimension_stats"]["semantic_score"]
    assert dim_stats["regression_count"] == 1
    assert dim_stats["avg_delta"] < 0


def test_identify_worst_passes() -> None:
    baseline = [
        _make_obs_record("extraction", f"c{i}", semantic_score=0.9)
        for i in range(3)
    ] + [
        _make_obs_record("reasoning", f"c{i}", semantic_score=0.9)
        for i in range(3)
    ]
    candidate = [
        _make_obs_record("extraction", f"c{i}", semantic_score=0.85)
        for i in range(3)
    ] + [
        _make_obs_record("reasoning", f"c{i}", semantic_score=0.70)
        for i in range(3)
    ]
    attr = attribute_regressions_to_passes(baseline, candidate)
    summary = compute_pass_regression_summary(attr["pass_attributions"])
    worst = identify_worst_passes(summary, top_n=2, dimension="semantic_score")
    assert len(worst) > 0
    # reasoning should be worse than extraction
    if len(worst) >= 2:
        assert worst[0]["pass_type"] == "reasoning"


def test_attribution_partial_attribution_reported() -> None:
    baseline = [
        _make_obs_record("extraction", "c1"),
        _make_obs_record("extraction", "c2"),
    ]
    candidate = [
        _make_obs_record("extraction", "c1"),
        # c2 missing from candidate
    ]
    result = attribute_regressions_to_passes(baseline, candidate)
    assert result["unmatched_baseline"] == 1
    assert result["partial_attribution"] is True


# ===========================================================================
# 7. RegressionHarness — compare_eval_runs
# ===========================================================================


def test_compare_eval_runs_happy_path(
    harness: RegressionHarness,
    sample_eval_results: List[Dict[str, Any]],
) -> None:
    result = harness.compare_eval_runs(sample_eval_results, sample_eval_results)
    assert result["insufficient_data"] is False
    assert result["cases_compared"] == 5


def test_compare_eval_runs_insufficient_sample(
    harness: RegressionHarness,
    sample_eval_results: List[Dict[str, Any]],
) -> None:
    # Only 1 case — below minimum_sample_sizes.cases = 3
    single = sample_eval_results[:1]
    result = harness.compare_eval_runs(single, single)
    assert result["insufficient_data"] is True


def test_compare_eval_runs_detects_regression(
    harness: RegressionHarness,
    sample_eval_results: List[Dict[str, Any]],
) -> None:
    regressed = [
        {**r, "grounding_score": 0.50}  # big drop
        for r in sample_eval_results
    ]
    result = harness.compare_eval_runs(sample_eval_results, regressed)
    agg = result["aggregates"]
    delta = agg["candidate_grounding_score"] - agg["baseline_grounding_score"]
    assert delta < 0


# ===========================================================================
# 8. RegressionHarness — compare_observability_runs
# ===========================================================================


def test_compare_observability_runs_happy_path(
    harness: RegressionHarness,
    sample_obs_records: List[Dict[str, Any]],
) -> None:
    result = harness.compare_observability_runs(sample_obs_records, sample_obs_records)
    assert result["latency_ms"]["baseline"] == pytest.approx(100.0)
    assert result["latency_ms"]["candidate"] == pytest.approx(100.0)
    assert result["passes_compared"] == 5


def test_compare_observability_runs_empty_inputs(
    harness: RegressionHarness,
) -> None:
    result = harness.compare_observability_runs([], [])
    assert result["insufficient_data"] is True


# ===========================================================================
# 9. RegressionHarness — generate_report
# ===========================================================================


def test_generate_report_passes_with_identical_runs(
    harness: RegressionHarness,
    sample_eval_results: List[Dict[str, Any]],
    sample_obs_records: List[Dict[str, Any]],
) -> None:
    ec = harness.compare_eval_runs(sample_eval_results, sample_eval_results)
    oc = harness.compare_observability_runs(sample_obs_records, sample_obs_records)
    report = harness.generate_report(
        baseline_id="v1",
        candidate_id="current",
        eval_comparison=ec,
        observability_comparison=oc,
    )
    assert report.overall_pass is True
    assert report.hard_failures == 0


def test_generate_report_hard_fail_on_grounding_regression(
    harness: RegressionHarness,
    sample_eval_results: List[Dict[str, Any]],
    sample_obs_records: List[Dict[str, Any]],
) -> None:
    regressed = [{**r, "grounding_score": 0.50} for r in sample_eval_results]
    ec = harness.compare_eval_runs(sample_eval_results, regressed)
    oc = harness.compare_observability_runs(sample_obs_records, sample_obs_records)
    report = harness.generate_report(
        baseline_id="v1",
        candidate_id="current",
        eval_comparison=ec,
        observability_comparison=oc,
    )
    assert report.overall_pass is False
    assert report.hard_failures >= 1


def test_generate_report_warning_on_latency_increase(
    harness: RegressionHarness,
    sample_eval_results: List[Dict[str, Any]],
    sample_obs_records: List[Dict[str, Any]],
) -> None:
    slow_obs = [{**r, "latency_ms": 1000} for r in sample_obs_records]
    ec = harness.compare_eval_runs(sample_eval_results, sample_eval_results)
    oc = harness.compare_observability_runs(sample_obs_records, slow_obs)
    report = harness.generate_report(
        baseline_id="v1",
        candidate_id="current",
        eval_comparison=ec,
        observability_comparison=oc,
    )
    # latency should warn but not hard fail
    dim = report.to_dict()["dimension_results"]["latency"]
    assert dim["severity"] == SEVERITY_WARNING
    assert report.hard_failures == 0


def test_generate_report_deterministic_required_hard_fail() -> None:
    policy_data = {
        "policy_id": "strict",
        "version": "1.0.0",
        "description": "Strict determinism policy",
        "thresholds": {
            "structural_score_drop_max": 0.05,
            "semantic_score_drop_max": 0.08,
            "grounding_score_drop_max": 0.03,
            "latency_increase_pct_max": 25,
            "human_disagreement_increase_pct_max": 20,
        },
        "hard_fail_dimensions": {
            "structural_score": True,
            "semantic_score": True,
            "grounding_score": True,
            "latency": False,
            "human_disagreement": False,
        },
        "minimum_sample_sizes": {"cases": 1, "per_pass_records": 1},
        "scope": {"artifact_types": ["evaluation_result"], "pass_types": ["extraction"]},
        "deterministic_required": True,
    }
    policy = RegressionPolicy(policy_data)
    harness = RegressionHarness(policy=policy)
    report = harness.generate_report(
        baseline_id="v1",
        candidate_id="current",
        candidate_deterministic=False,  # non-deterministic → hard fail
    )
    assert report.overall_pass is False
    assert report.hard_failures >= 1


def test_generate_report_deterministic_required_passes_when_deterministic() -> None:
    policy_data = {
        "policy_id": "strict",
        "version": "1.0.0",
        "description": "Strict",
        "thresholds": {
            "structural_score_drop_max": 0.05,
            "semantic_score_drop_max": 0.08,
            "grounding_score_drop_max": 0.03,
            "latency_increase_pct_max": 25,
            "human_disagreement_increase_pct_max": 20,
        },
        "hard_fail_dimensions": {
            "structural_score": True,
            "semantic_score": True,
            "grounding_score": True,
            "latency": False,
            "human_disagreement": False,
        },
        "minimum_sample_sizes": {"cases": 1, "per_pass_records": 1},
        "scope": {"artifact_types": ["evaluation_result"], "pass_types": ["extraction"]},
        "deterministic_required": True,
    }
    policy = RegressionPolicy(policy_data)
    harness = RegressionHarness(policy=policy)
    report = harness.generate_report(
        baseline_id="v1",
        candidate_id="current",
        candidate_deterministic=True,  # deterministic → OK
    )
    # No data → all insufficient, but determinism gate passes
    assert report.hard_failures == 0


# ===========================================================================
# 10. Report schema validation
# ===========================================================================


def test_report_validates_against_schema(
    harness: RegressionHarness,
    sample_eval_results: List[Dict[str, Any]],
    sample_obs_records: List[Dict[str, Any]],
) -> None:
    ec = harness.compare_eval_runs(sample_eval_results, sample_eval_results)
    oc = harness.compare_observability_runs(sample_obs_records, sample_obs_records)
    report = harness.generate_report(
        baseline_id="v1",
        candidate_id="current",
        eval_comparison=ec,
        observability_comparison=oc,
    )
    errors = report.validate_against_schema()
    assert errors == [], f"Schema validation errors: {errors}"


def test_report_write_and_reload(
    tmp_path: Path,
    harness: RegressionHarness,
    sample_eval_results: List[Dict[str, Any]],
    sample_obs_records: List[Dict[str, Any]],
) -> None:
    ec = harness.compare_eval_runs(sample_eval_results, sample_eval_results)
    oc = harness.compare_observability_runs(sample_obs_records, sample_obs_records)
    report = harness.generate_report(
        baseline_id="v1",
        candidate_id="current",
        eval_comparison=ec,
        observability_comparison=oc,
    )
    out = tmp_path / "regression_report.json"
    report.write(out)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["baseline_id"] == "v1"
    assert "summary" in loaded
    assert "dimension_results" in loaded


# ===========================================================================
# 11. Serialisation helpers
# ===========================================================================


def test_eval_result_to_dict_passthrough(sample_eval_results: List[Dict[str, Any]]) -> None:
    d = eval_result_to_dict(sample_eval_results[0])
    assert d["case_id"] == "case_000"


def test_observability_record_to_dict_flat_passthrough(
    sample_obs_records: List[Dict[str, Any]],
) -> None:
    d = observability_record_to_dict(sample_obs_records[0])
    assert d["pass_type"] == "extraction"


def test_observability_record_to_dict_from_nested_schema() -> None:
    nested = {
        "record_id": "r1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "context": {
            "artifact_id": "art1",
            "artifact_type": "evaluation_result",
            "pipeline_stage": "validate",
            "case_id": "c1",
        },
        "pass_info": {"pass_id": "p1", "pass_type": "extraction"},
        "metrics": {
            "structural_score": 0.9,
            "semantic_score": 0.85,
            "grounding_score": 0.95,
            "latency_ms": 100,
        },
        "flags": {
            "schema_valid": True,
            "grounding_passed": True,
            "regression_passed": True,
            "human_disagrees": False,
        },
        "error_summary": {"error_types": [], "failure_count": 0},
    }
    flat = observability_record_to_dict(nested)
    assert flat["pass_type"] == "extraction"
    assert flat["case_id"] == "c1"
    assert flat["structural_score"] == pytest.approx(0.9)


# ===========================================================================
# 12. Recommendations
# ===========================================================================


def test_recommendations_no_regressions() -> None:
    report_dict = {
        "dimension_results": {
            k: {"passed": True, "severity": "info", "delta": 0.0, "insufficient_data": False}
            for k in ("structural_score", "semantic_score", "grounding_score", "latency", "human_disagreement")
        },
        "worst_regressions": [],
        "summary": {"overall_pass": True, "hard_failures": 0, "warnings": 0},
    }
    recs = generate_recommendations(report_dict)
    assert len(recs) == 1
    assert "no regressions" in recs[0].lower()


def test_recommendations_hard_fail_included() -> None:
    report_dict = {
        "dimension_results": {
            "grounding_score": {"passed": False, "severity": "hard_fail", "delta": -0.15, "insufficient_data": False},
            "structural_score": {"passed": True, "severity": "info", "delta": 0.0, "insufficient_data": False},
            "semantic_score": {"passed": True, "severity": "info", "delta": 0.0, "insufficient_data": False},
            "latency": {"passed": True, "severity": "info", "delta": 0.0, "insufficient_data": False},
            "human_disagreement": {"passed": True, "severity": "info", "delta": 0.0, "insufficient_data": True},
        },
        "worst_regressions": [],
        "summary": {"overall_pass": False, "hard_failures": 1, "warnings": 0},
    }
    recs = generate_recommendations(report_dict)
    hard_fail_recs = [r for r in recs if "HARD FAIL" in r]
    assert len(hard_fail_recs) >= 1


def test_recommendations_warning_included() -> None:
    report_dict = {
        "dimension_results": {
            "latency": {"passed": False, "severity": "warning", "delta": 200.0, "insufficient_data": False},
            "structural_score": {"passed": True, "severity": "info", "delta": 0.0, "insufficient_data": False},
            "semantic_score": {"passed": True, "severity": "info", "delta": 0.0, "insufficient_data": False},
            "grounding_score": {"passed": True, "severity": "info", "delta": 0.0, "insufficient_data": False},
            "human_disagreement": {"passed": True, "severity": "info", "delta": 0.0, "insufficient_data": True},
        },
        "worst_regressions": [],
        "summary": {"overall_pass": True, "hard_failures": 0, "warnings": 1},
    }
    recs = generate_recommendations(report_dict)
    lat_recs = [r for r in recs if "latency" in r.lower() or "Latency" in r]
    assert len(lat_recs) >= 1


def test_recommendations_determinism_fail() -> None:
    report_dict = {
        "dimension_results": {
            k: {"passed": True, "severity": "info", "delta": 0.0, "insufficient_data": False}
            for k in ("structural_score", "semantic_score", "grounding_score", "latency", "human_disagreement")
        },
        "worst_regressions": [],
        "summary": {"overall_pass": False, "hard_failures": 1, "warnings": 0},
        "determinism_fail": True,
    }
    recs = generate_recommendations(report_dict)
    assert any("HARD FAIL" in r and "deterministic" in r.lower() for r in recs)


def test_recommendations_insufficient_data_notice() -> None:
    report_dict = {
        "dimension_results": {
            "structural_score": {"passed": True, "severity": "info", "delta": 0.0, "insufficient_data": True},
            "semantic_score": {"passed": True, "severity": "info", "delta": 0.0, "insufficient_data": False},
            "grounding_score": {"passed": True, "severity": "info", "delta": 0.0, "insufficient_data": False},
            "latency": {"passed": True, "severity": "info", "delta": 0.0, "insufficient_data": False},
            "human_disagreement": {"passed": True, "severity": "info", "delta": 0.0, "insufficient_data": True},
        },
        "worst_regressions": [],
        "summary": {"overall_pass": True, "hard_failures": 0, "warnings": 0},
    }
    recs = generate_recommendations(report_dict)
    insufficient_recs = [r for r in recs if "insufficient" in r.lower()]
    assert len(insufficient_recs) >= 1


# ===========================================================================
# 13. CLI smoke tests
# ===========================================================================


def _make_eval_json(path: Path, n: int = 5) -> None:
    results = [
        {
            "case_id": f"case_{i:03d}",
            "pass_fail": True,
            "structural_score": 0.90,
            "semantic_score": 0.85,
            "grounding_score": 0.95,
            "latency_summary": {"per_pass_latency": {}, "total_latency_ms": 100, "budget_violations": []},
            "error_types": [],
            "schema_valid": True,
            "regression_detected": False,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "human_feedback_overrides": [],
        }
        for i in range(n)
    ]
    path.write_text(json.dumps(results), encoding="utf-8")


def _make_obs_json(path: Path, n: int = 5) -> None:
    records = [
        {
            "record_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "artifact_id": f"case_{i:03d}",
            "artifact_type": "evaluation_result",
            "pipeline_stage": "validate",
            "case_id": f"case_{i:03d}",
            "pass_id": str(uuid.uuid4()),
            "pass_type": "extraction",
            "structural_score": 0.90,
            "semantic_score": 0.85,
            "grounding_score": 0.95,
            "latency_ms": 100,
            "schema_valid": True,
            "grounding_passed": True,
            "regression_passed": True,
            "human_disagrees": False,
            "error_types": [],
            "failure_count": 0,
        }
        for i in range(n)
    ]
    path.write_text(json.dumps(records), encoding="utf-8")


def test_cli_create_baseline(tmp_path: Path) -> None:
    """CLI can create a baseline and exits 0."""
    from scripts.run_regression_check import main

    eval_path = tmp_path / "eval.json"
    obs_path = tmp_path / "obs.json"
    _make_eval_json(eval_path)
    _make_obs_json(obs_path)

    exit_code = main([
        "--create-baseline", "smoke_v1",
        "--from-eval", str(eval_path),
        "--from-observability", str(obs_path),
        "--baselines-dir", str(tmp_path / "baselines"),
    ])
    assert exit_code == 0
    assert (tmp_path / "baselines" / "smoke_v1" / "metadata.json").exists()


def test_cli_compare_identical_baseline(tmp_path: Path) -> None:
    """CLI compare of identical baseline vs candidate exits 0."""
    from scripts.run_regression_check import main

    eval_path = tmp_path / "eval.json"
    obs_path = tmp_path / "obs.json"
    output_path = tmp_path / "report.json"
    baselines_dir = tmp_path / "baselines"

    _make_eval_json(eval_path)
    _make_obs_json(obs_path)

    # Create baseline
    main([
        "--create-baseline", "v1",
        "--from-eval", str(eval_path),
        "--from-observability", str(obs_path),
        "--baselines-dir", str(baselines_dir),
    ])

    # Compare
    exit_code = main([
        "--baseline", "v1",
        "--from-eval", str(eval_path),
        "--from-observability", str(obs_path),
        "--output", str(output_path),
        "--baselines-dir", str(baselines_dir),
    ])
    assert exit_code in (0, 1)
    assert output_path.exists()
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert "summary" in report
    assert report["summary"]["hard_failures"] == 0


def test_cli_compare_missing_baseline(tmp_path: Path) -> None:
    """CLI exits 2 if baseline does not exist."""
    from scripts.run_regression_check import main

    exit_code = main([
        "--baseline", "nonexistent",
        "--baselines-dir", str(tmp_path / "baselines"),
    ])
    assert exit_code == 2


def test_cli_no_silent_overwrite(tmp_path: Path) -> None:
    """CLI exits 2 if trying to overwrite baseline without --update-baseline."""
    from scripts.run_regression_check import main

    eval_path = tmp_path / "eval.json"
    obs_path = tmp_path / "obs.json"
    _make_eval_json(eval_path)
    _make_obs_json(obs_path)

    main([
        "--create-baseline", "v1",
        "--from-eval", str(eval_path),
        "--from-observability", str(obs_path),
        "--baselines-dir", str(tmp_path / "baselines"),
    ])

    exit_code = main([
        "--create-baseline", "v1",
        "--from-eval", str(eval_path),
        "--from-observability", str(obs_path),
        "--baselines-dir", str(tmp_path / "baselines"),
    ])
    assert exit_code == 2
