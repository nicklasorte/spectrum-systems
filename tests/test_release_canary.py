from __future__ import annotations

from copy import deepcopy

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.release_canary import ReleaseInputVersions, build_release_record


def _eval_summary(eval_run_id: str, *, pass_rate: float, trace_suffix: str = "1") -> dict:
    return {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": f"00000000-0000-4000-8000-{int(trace_suffix):012d}",
        "eval_run_id": eval_run_id,
        "pass_rate": pass_rate,
        "failure_rate": round(1.0 - pass_rate, 6),
        "drift_rate": 0.0,
        "reproducibility_score": 1.0,
        "system_status": "healthy",
    }


def _eval_result(case_id: str, *, status: str = "pass", indeterminate: bool = False) -> dict:
    failure_modes: list[str] = []
    if status != "pass":
        failure_modes.append("expected_output_mismatch")
    if indeterminate:
        failure_modes.append("indeterminate_treated_as_failure")
    return {
        "artifact_type": "eval_result",
        "schema_version": "1.0.0",
        "eval_case_id": case_id,
        "trace_id": "11111111-1111-4111-8111-111111111111",
        "result_status": status,
        "score": 1.0 if status == "pass" else 0.0,
        "failure_modes": failure_modes,
        "provenance_refs": [f"trace://{case_id}"],
    }


def _coverage(run_id: str, *, score: float = 1.0, uncovered: list[str] | None = None) -> dict:
    return {
        "artifact_type": "eval_coverage_summary",
        "schema_version": "1.0.0",
        "coverage_run_id": run_id,
        "timestamp": "2026-03-24T00:00:00Z",
        "dataset_refs": [],
        "total_eval_cases": 2,
        "covered_slices": ["slice.alpha"],
        "uncovered_required_slices": uncovered or [],
        "slice_case_counts": {"slice.alpha": 2},
        "risk_weighted_coverage_score": score,
        "coverage_gaps": [],
    }


def _slice_summary(pass_rate: float = 1.0, *, total_cases: int = 2) -> dict:
    return {
        "artifact_type": "eval_slice_summary",
        "schema_version": "1.0.0",
        "coverage_run_id": "cov",
        "slice_id": "slice.alpha",
        "slice_name": "Alpha",
        "total_cases": total_cases,
        "pass_count": int(total_cases * pass_rate),
        "fail_count": total_cases - int(total_cases * pass_rate),
        "indeterminate_count": 0,
        "pass_rate": pass_rate,
        "failure_rate": round(1.0 - pass_rate, 6),
        "latest_eval_run_refs": ["trace://1"],
        "risk_class": "high",
        "priority": "p1",
        "status": "healthy",
    }


def _policy() -> dict:
    return {
        "minimum_eval_sample_size": 2,
        "max_pass_rate_delta_drop": 0.02,
        "max_coverage_score_delta_drop": 0.05,
        "required_slices_must_not_degrade": True,
        "allow_new_failures": False,
        "indeterminate_counts_as_regression": True,
        "control_thresholds": {
            "reliability_threshold": 0.85,
            "drift_threshold": 0.2,
            "trust_threshold": 0.8,
        },
        "blocking_system_responses": ["freeze", "block"],
        "rollback_system_responses": ["block"],
        "rollback_pass_rate_delta_drop_threshold": 0.1,
        "rollback_triggers": [
            "candidate_blocked_by_control",
            "required_slice_regression",
            "new_failures_introduced",
            "indeterminate_case_detected",
            "pass_rate_drop_exceeds_rollback_threshold",
        ],
    }


def _versions(tag: str) -> ReleaseInputVersions:
    return ReleaseInputVersions(
        prompt_version_id=f"prompt-{tag}",
        schema_version=f"schema-{tag}",
        policy_version_id=f"policy-{tag}",
        route_policy_version_id=f"route-{tag}",
    )


def _build(**overrides):
    payload = {
        "release_id": "release-test-001",
        "timestamp": "2026-03-24T00:00:00Z",
        "baseline_version": "baseline-v1",
        "candidate_version": "candidate-v1",
        "artifact_types": ["prompt", "schema", "policy", "routing"],
        "baseline_versions": _versions("base"),
        "candidate_versions": _versions("cand"),
        "baseline_eval_summary": _eval_summary("base-run", pass_rate=1.0, trace_suffix="1"),
        "candidate_eval_summary": _eval_summary("cand-run", pass_rate=1.0, trace_suffix="2"),
        "baseline_eval_results": [_eval_result("case-1", status="pass"), _eval_result("case-2", status="pass")],
        "candidate_eval_results": [_eval_result("case-1", status="pass"), _eval_result("case-2", status="pass")],
        "baseline_coverage_summary": _coverage("cov-base", score=1.0),
        "candidate_coverage_summary": _coverage("cov-cand", score=1.0),
        "baseline_slice_summaries": [_slice_summary(1.0)],
        "candidate_slice_summaries": [_slice_summary(1.0)],
        "eval_summary_refs": {"baseline": "baseline/eval_summary.json", "candidate": "candidate/eval_summary.json"},
        "coverage_summary_refs": {
            "baseline": "baseline/eval_coverage_summary.json",
            "candidate": "candidate/eval_coverage_summary.json",
        },
        "policy": _policy(),
    }
    payload.update(overrides)
    return build_release_record(**payload)


def test_no_regression_promotes() -> None:
    record = _build()
    assert record["decision"] == "promote"


def test_slice_regression_blocks_promotion() -> None:
    record = _build(
        candidate_coverage_summary=_coverage("cov-cand", score=0.8, uncovered=["slice.alpha"]),
        candidate_slice_summaries=[_slice_summary(0.5)],
    )
    assert record["decision"] != "promote"
    assert any(reason.startswith("rollback_triggered:required_slice_regression") for reason in record["reasons"])


def test_new_failure_introduced_blocks_promotion() -> None:
    record = _build(candidate_eval_results=[_eval_result("case-1", status="pass"), _eval_result("case-2", status="fail")])
    assert record["decision"] != "promote"
    assert "case-2" in record["canary_comparison_results"]["new_failures"]


def test_indeterminate_is_blocking() -> None:
    record = _build(candidate_eval_results=[_eval_result("case-1", status="pass"), _eval_result("case-2", status="fail", indeterminate=True)])
    assert record["decision"] != "promote"
    assert "case-2" in record["canary_comparison_results"]["indeterminate_failures"]


def test_threshold_boundary_allows_promote() -> None:
    record = _build(
        baseline_eval_summary=_eval_summary("base-run", pass_rate=0.92, trace_suffix="3"),
        candidate_eval_summary=_eval_summary("cand-run", pass_rate=0.9, trace_suffix="4"),
    )
    assert record["canary_comparison_results"]["pass_rate_delta"] == -0.02
    assert record["decision"] == "promote"


def test_rollback_triggered_by_control_block() -> None:
    candidate_summary = _eval_summary("cand-run", pass_rate=1.0, trace_suffix="5")
    candidate_summary["reproducibility_score"] = 0.0
    record = _build(candidate_eval_summary=candidate_summary)
    assert record["decision"] == "rollback"
    assert record["rollback_target_version"] == "baseline-v1"


def test_deterministic_results_across_runs() -> None:
    one = _build()
    two = _build()
    assert one == two


def test_release_record_validates_against_schema() -> None:
    record = _build()
    validator = Draft202012Validator(load_schema("evaluation_release_record"), format_checker=FormatChecker())
    validator.validate(record)


def test_policy_threshold_failure_holds_when_no_rollback_trigger() -> None:
    policy = deepcopy(_policy())
    policy["rollback_triggers"] = []
    record = _build(
        policy=policy,
        baseline_eval_summary=_eval_summary("base-run", pass_rate=0.95, trace_suffix="6"),
        candidate_eval_summary=_eval_summary("cand-run", pass_rate=0.9, trace_suffix="7"),
    )
    assert record["decision"] == "hold"
