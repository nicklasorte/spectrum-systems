"""Deterministic release canary comparison and decision builder (SF-14)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.evaluation_control import build_evaluation_control_decision


class ReleaseCanaryError(Exception):
    """Raised when release canary computation cannot proceed."""


@dataclass(frozen=True)
class ReleaseInputVersions:
    prompt_version_id: str
    schema_version: str
    policy_version_id: str
    route_policy_version_id: str | None


def _validate(instance: dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def _round_delta(value: float) -> float:
    return round(value, 6)


def _slice_index(slice_summaries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("slice_id")): item for item in slice_summaries if item.get("slice_id")}


def _failure_case_ids(eval_results: list[dict[str, Any]]) -> set[str]:
    return {
        str(item.get("eval_case_id"))
        for item in eval_results
        if str(item.get("result_status", "")).strip().lower() == "fail"
    }


def _indeterminate_case_ids(eval_results: list[dict[str, Any]]) -> set[str]:
    hits: set[str] = set()
    for item in eval_results:
        case_id = str(item.get("eval_case_id", "")).strip()
        if not case_id:
            continue
        status = str(item.get("result_status", "")).strip().lower()
        failure_modes = [str(mode).lower() for mode in (item.get("failure_modes") or [])]
        if status == "indeterminate" or any("indeterminate" in mode for mode in failure_modes):
            hits.add(case_id)
    return hits


def _required_slice_regressions(
    *,
    baseline_coverage: dict[str, Any],
    candidate_coverage: dict[str, Any],
    baseline_slices: list[dict[str, Any]],
    candidate_slices: list[dict[str, Any]],
) -> list[str]:
    regressions: set[str] = set()

    baseline_uncovered = set(baseline_coverage.get("uncovered_required_slices") or [])
    candidate_uncovered = set(candidate_coverage.get("uncovered_required_slices") or [])
    regressions.update(candidate_uncovered - baseline_uncovered)

    baseline_idx = _slice_index(baseline_slices)
    candidate_idx = _slice_index(candidate_slices)

    for slice_id, baseline_item in baseline_idx.items():
        candidate_item = candidate_idx.get(slice_id)
        if not candidate_item:
            continue
        if int(baseline_item.get("total_cases", 0)) == 0:
            continue
        if int(candidate_item.get("total_cases", 0)) == 0:
            regressions.add(slice_id)
            continue

        baseline_pass_rate = float(baseline_item.get("pass_rate", 0.0))
        candidate_pass_rate = float(candidate_item.get("pass_rate", 0.0))
        if candidate_pass_rate < baseline_pass_rate:
            regressions.add(slice_id)

    return sorted(regressions)


def _coverage_mismatch_details(
    *,
    baseline_coverage: dict[str, Any],
    candidate_coverage: dict[str, Any],
) -> list[str]:
    mismatches: list[str] = []

    if int(baseline_coverage.get("total_eval_cases", 0)) != int(candidate_coverage.get("total_eval_cases", 0)):
        mismatches.append("total_eval_cases")

    baseline_covered = sorted(str(x) for x in (baseline_coverage.get("covered_slices") or []))
    candidate_covered = sorted(str(x) for x in (candidate_coverage.get("covered_slices") or []))
    if baseline_covered != candidate_covered:
        mismatches.append("covered_slices")

    baseline_uncovered = sorted(str(x) for x in (baseline_coverage.get("uncovered_required_slices") or []))
    candidate_uncovered = sorted(str(x) for x in (candidate_coverage.get("uncovered_required_slices") or []))
    if baseline_uncovered != candidate_uncovered:
        mismatches.append("uncovered_required_slices")

    baseline_counts = {str(k): int(v) for k, v in dict(baseline_coverage.get("slice_case_counts") or {}).items()}
    candidate_counts = {str(k): int(v) for k, v in dict(candidate_coverage.get("slice_case_counts") or {}).items()}
    if baseline_counts != candidate_counts:
        mismatches.append("slice_case_counts")

    return sorted(mismatches)


def _threshold_result(threshold: str, passed: bool, actual: Any, expected: Any) -> dict[str, Any]:
    return {
        "threshold": threshold,
        "passed": passed,
        "actual": actual,
        "expected": expected,
    }


def build_release_record(
    *,
    release_id: str,
    timestamp: str,
    baseline_version: str,
    candidate_version: str,
    artifact_types: list[str],
    baseline_versions: ReleaseInputVersions,
    candidate_versions: ReleaseInputVersions,
    baseline_eval_summary: dict[str, Any],
    candidate_eval_summary: dict[str, Any],
    baseline_eval_results: list[dict[str, Any]],
    candidate_eval_results: list[dict[str, Any]],
    baseline_coverage_summary: dict[str, Any],
    candidate_coverage_summary: dict[str, Any],
    baseline_slice_summaries: list[dict[str, Any]],
    candidate_slice_summaries: list[dict[str, Any]],
    eval_summary_refs: dict[str, str],
    coverage_summary_refs: dict[str, str],
    policy: dict[str, Any],
) -> dict[str, Any]:
    _validate(baseline_eval_summary, "eval_summary")
    _validate(candidate_eval_summary, "eval_summary")
    _validate(baseline_coverage_summary, "eval_coverage_summary")
    _validate(candidate_coverage_summary, "eval_coverage_summary")

    for result in baseline_eval_results:
        _validate(result, "eval_result")
    for result in candidate_eval_results:
        _validate(result, "eval_result")

    for item in baseline_slice_summaries:
        _validate(item, "eval_slice_summary")
    for item in candidate_slice_summaries:
        _validate(item, "eval_slice_summary")

    control_thresholds = dict(policy.get("control_thresholds") or {})
    baseline_control = build_evaluation_control_decision(baseline_eval_summary, thresholds=control_thresholds)
    candidate_control = build_evaluation_control_decision(candidate_eval_summary, thresholds=control_thresholds)

    sample_size = int(candidate_coverage_summary.get("total_eval_cases", 0))
    pass_rate_delta = _round_delta(
        float(candidate_eval_summary.get("pass_rate", 0.0)) - float(baseline_eval_summary.get("pass_rate", 0.0))
    )
    coverage_score_delta = _round_delta(
        float(candidate_coverage_summary.get("risk_weighted_coverage_score", 0.0))
        - float(baseline_coverage_summary.get("risk_weighted_coverage_score", 0.0))
    )

    required_slice_regressions = _required_slice_regressions(
        baseline_coverage=baseline_coverage_summary,
        candidate_coverage=candidate_coverage_summary,
        baseline_slices=baseline_slice_summaries,
        candidate_slices=candidate_slice_summaries,
    )
    coverage_mismatch_fields = _coverage_mismatch_details(
        baseline_coverage=baseline_coverage_summary,
        candidate_coverage=candidate_coverage_summary,
    )

    baseline_failures = _failure_case_ids(baseline_eval_results)
    candidate_failures = _failure_case_ids(candidate_eval_results)
    new_failures = sorted(candidate_failures - baseline_failures)

    indeterminate_failures = sorted(_indeterminate_case_ids(candidate_eval_results))

    min_sample_size = int(policy.get("minimum_eval_sample_size", 1))
    max_pass_drop = float(policy.get("max_acceptable_aggregate_regression", policy.get("max_pass_rate_delta_drop", 0.0)))
    max_coverage_drop = float(policy.get("max_coverage_score_delta_drop", 0.0))

    coverage_parity_required = bool(policy.get("coverage_parity_required", True))
    new_failures_block = bool(policy.get("new_failures_block", True))
    indeterminate_blocks = bool(policy.get("indeterminate_blocks", True))
    required_slices_no_regression = bool(policy.get("required_slices_no_regression", True))

    threshold_results: list[dict[str, Any]] = [
        _threshold_result("minimum_eval_sample_size", sample_size >= min_sample_size, sample_size, min_sample_size),
        _threshold_result(
            "max_acceptable_aggregate_regression",
            pass_rate_delta >= (-1.0 * max_pass_drop),
            pass_rate_delta,
            -1.0 * max_pass_drop,
        ),
        _threshold_result(
            "max_coverage_score_delta_drop",
            coverage_score_delta >= (-1.0 * max_coverage_drop),
            coverage_score_delta,
            -1.0 * max_coverage_drop,
        ),
    ]

    if required_slices_no_regression:
        threshold_results.append(
            _threshold_result(
                "required_slices_no_regression",
                len(required_slice_regressions) == 0,
                required_slice_regressions,
                [],
            )
        )

    if coverage_parity_required:
        threshold_results.append(
            _threshold_result(
                "coverage_parity_required",
                len(coverage_mismatch_fields) == 0,
                coverage_mismatch_fields,
                [],
            )
        )

    if new_failures_block:
        threshold_results.append(
            _threshold_result(
                "new_failures_block",
                len(new_failures) == 0,
                new_failures,
                [],
            )
        )

    if indeterminate_blocks:
        threshold_results.append(
            _threshold_result(
                "indeterminate_blocks",
                len(indeterminate_failures) == 0,
                indeterminate_failures,
                [],
            )
        )

    candidate_system_response = str(candidate_control.get("system_response", "block"))
    blocking_system_responses = sorted(set(policy.get("blocking_system_responses") or ["freeze", "block"]))
    threshold_results.append(
        _threshold_result(
            "candidate_control_response",
            candidate_system_response not in set(blocking_system_responses),
            candidate_system_response,
            blocking_system_responses,
        )
    )

    failed_thresholds = sorted(item["threshold"] for item in threshold_results if not item["passed"])

    rollback_reason_map: dict[str, bool] = {
        "candidate_blocked_by_control": candidate_system_response in set(policy.get("rollback_system_responses") or ["block"]),
        "required_slice_regression": len(required_slice_regressions) > 0,
        "coverage_mismatch": len(coverage_mismatch_fields) > 0,
        "new_failures_introduced": len(new_failures) > 0,
        "indeterminate_case_detected": len(indeterminate_failures) > 0,
        "pass_rate_drop_exceeds_rollback_threshold": pass_rate_delta
        < (-1.0 * float(policy.get("rollback_pass_rate_delta_drop_threshold", 1.0))),
    }
    active_rollback_triggers = sorted(
        str(trigger)
        for trigger in (policy.get("rollback_triggers") or [])
        if rollback_reason_map.get(str(trigger), False)
    )

    # Explicit precedence: rollback > hold > promote
    if active_rollback_triggers:
        decision = "rollback"
        rollback_target_version: str | None = baseline_version
    elif failed_thresholds:
        decision = "hold"
        rollback_target_version = None
    else:
        decision = "promote"
        rollback_target_version = None

    reasons = [*(f"threshold_failed:{name}" for name in failed_thresholds), *(f"rollback_triggered:{name}" for name in active_rollback_triggers)]
    if decision == "promote":
        reasons.append("all_release_policy_checks_passed")

    record = {
        "artifact_type": "evaluation_release_record",
        "schema_version": "1.1.0",
        "release_id": release_id,
        "timestamp": timestamp,
        "candidate_version": candidate_version,
        "baseline_version": baseline_version,
        "artifact_types": sorted(set(artifact_types)),
        "version_set": {
            "baseline": {
                "prompt_version_id": baseline_versions.prompt_version_id,
                "schema_version": baseline_versions.schema_version,
                "policy_version_id": baseline_versions.policy_version_id,
                "route_policy_version_id": baseline_versions.route_policy_version_id,
            },
            "candidate": {
                "prompt_version_id": candidate_versions.prompt_version_id,
                "schema_version": candidate_versions.schema_version,
                "policy_version_id": candidate_versions.policy_version_id,
                "route_policy_version_id": candidate_versions.route_policy_version_id,
            },
        },
        "eval_summary_refs": {
            "baseline": eval_summary_refs["baseline"],
            "candidate": eval_summary_refs["candidate"],
        },
        "coverage_summary_refs": {
            "baseline": coverage_summary_refs["baseline"],
            "candidate": coverage_summary_refs["candidate"],
        },
        "canary_comparison_results": {
            "baseline_eval_run_id": str(baseline_eval_summary.get("eval_run_id", "unknown-baseline")),
            "candidate_eval_run_id": str(candidate_eval_summary.get("eval_run_id", "unknown-candidate")),
            "sample_size": sample_size,
            "pass_rate_delta": pass_rate_delta,
            "coverage_score_delta": coverage_score_delta,
            "required_slice_regressions": required_slice_regressions,
            "coverage_mismatch_fields": coverage_mismatch_fields,
            "new_failures": new_failures,
            "indeterminate_failures": indeterminate_failures,
            "control_responses": {
                "baseline": str(baseline_control.get("system_response", "block")),
                "candidate": candidate_system_response,
            },
            "threshold_results": sorted(threshold_results, key=lambda item: str(item["threshold"])),
        },
        "decision": decision,
        "reasons": sorted(set(reasons)),
        "rollback_target_version": rollback_target_version,
        "policy_version_id": str(policy.get("policy_version_id", "unknown")),
    }

    _validate(record, "evaluation_release_record")
    return record


def decision_exit_code(decision: str) -> int:
    mapping = {"promote": 0, "hold": 1, "rollback": 2}
    if decision not in mapping:
        raise ReleaseCanaryError(f"unsupported decision: {decision}")
    return mapping[decision]
