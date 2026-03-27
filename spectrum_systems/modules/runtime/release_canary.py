"""Deterministic release canary comparison and decision builder (SF-14)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_example, load_schema
from spectrum_systems.modules.runtime.decision_precedence import most_severe
from spectrum_systems.modules.runtime.evaluation_control import build_evaluation_control_decision
from spectrum_systems.utils.artifact_envelope import build_artifact_envelope


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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    regressions.update(sorted(candidate_uncovered - baseline_uncovered))

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


def _case_set_mismatch(
    baseline_eval_results: list[dict[str, Any]],
    candidate_eval_results: list[dict[str, Any]],
) -> dict[str, list[str]]:
    baseline_cases = sorted({str(item.get("eval_case_id")) for item in baseline_eval_results if item.get("eval_case_id")})
    candidate_cases = sorted({str(item.get("eval_case_id")) for item in candidate_eval_results if item.get("eval_case_id")})
    baseline_set = set(baseline_cases)
    candidate_set = set(candidate_cases)
    return {
        "baseline_only_case_ids": sorted(baseline_set - candidate_set),
        "candidate_only_case_ids": sorted(candidate_set - baseline_set),
    }


def _slice_set_mismatch(
    baseline_slice_summaries: list[dict[str, Any]],
    candidate_slice_summaries: list[dict[str, Any]],
) -> dict[str, list[str]]:
    baseline_slices = sorted({str(item.get("slice_id")) for item in baseline_slice_summaries if item.get("slice_id")})
    candidate_slices = sorted({str(item.get("slice_id")) for item in candidate_slice_summaries if item.get("slice_id")})
    baseline_set = set(baseline_slices)
    candidate_set = set(candidate_slices)
    return {
        "baseline_only_slice_ids": sorted(baseline_set - candidate_set),
        "candidate_only_slice_ids": sorted(candidate_set - baseline_set),
    }


def _threshold_result(threshold: str, passed: bool, actual: Any, expected: Any) -> dict[str, Any]:
    return {
        "threshold": threshold,
        "passed": passed,
        "actual": actual,
        "expected": expected,
    }


def _replay_result_from_eval_summary(eval_summary: dict[str, Any]) -> dict[str, Any]:
    replay_result = load_example("replay_result")
    if not isinstance(replay_result, dict):
        raise ReleaseCanaryError("contracts example replay_result must be an object")

    eval_run_id = str(eval_summary.get("eval_run_id") or "").strip()
    trace_id = str(eval_summary.get("trace_id") or "").strip()
    created_at = str(eval_summary.get("created_at") or "").strip()
    if not eval_run_id or not trace_id:
        raise ReleaseCanaryError("eval_summary must include eval_run_id and trace_id")

    pass_rate = float(eval_summary.get("pass_rate", 0.0))
    drift_rate = float(eval_summary.get("drift_rate", 1.0))
    reproducibility_score = float(eval_summary.get("reproducibility_score", 0.0))
    consistency_status = "match" if reproducibility_score >= 0.8 else "mismatch"

    replay_result["replay_id"] = f"RPL-{eval_run_id}"
    replay_result["replay_run_id"] = eval_run_id
    replay_result["original_run_id"] = eval_run_id
    replay_result["trace_id"] = trace_id
    replay_result["timestamp"] = created_at or replay_result.get("timestamp")
    replay_result["input_artifact_reference"] = f"eval_summary:{eval_run_id}"
    replay_result["consistency_status"] = consistency_status
    replay_result["drift_detected"] = consistency_status == "mismatch"
    replay_result["failure_reason"] = None
    replay_result["provenance"]["source_artifact_id"] = eval_run_id
    replay_result["provenance"]["trace_id"] = trace_id
    replay_result["observability_metrics"]["trace_refs"]["trace_id"] = trace_id
    replay_result["observability_metrics"]["metrics"]["replay_success_rate"] = pass_rate
    replay_result["observability_metrics"]["metrics"]["drift_exceed_threshold_rate"] = drift_rate
    replay_result["error_budget_status"]["trace_refs"]["trace_id"] = trace_id
    replay_result["error_budget_status"]["observability_metrics_id"] = replay_result["observability_metrics"]["artifact_id"]
    summary_status = str(eval_summary.get("system_status") or "invalid")
    replay_result["error_budget_status"]["budget_status"] = (
        summary_status if summary_status in {"healthy", "warning", "exhausted", "invalid"} else "invalid"
    )
    replay_result["alert_trigger"]["trace_refs"]["trace_id"] = trace_id
    replay_result["alert_trigger"]["replay_result_id"] = replay_result["replay_id"]
    return replay_result


def build_release_record(
    *,
    release_id: str,
    timestamp: str | None,
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
    baseline_replay_result = _replay_result_from_eval_summary(baseline_eval_summary)
    candidate_replay_result = _replay_result_from_eval_summary(candidate_eval_summary)
    _validate(baseline_replay_result, "replay_result")
    _validate(candidate_replay_result, "replay_result")
    baseline_control = build_evaluation_control_decision(baseline_replay_result, thresholds=control_thresholds)
    candidate_control = build_evaluation_control_decision(candidate_replay_result, thresholds=control_thresholds)

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

    baseline_failures = _failure_case_ids(baseline_eval_results)
    candidate_failures = _failure_case_ids(candidate_eval_results)
    new_failures = sorted(candidate_failures - baseline_failures)

    indeterminate_failures = sorted(_indeterminate_case_ids(candidate_eval_results))

    min_sample_size = int(policy.get("minimum_eval_sample_size", 1))
    max_pass_drop = float(policy.get("max_pass_rate_delta_drop", 0.0))
    max_coverage_drop = float(policy.get("max_coverage_score_delta_drop", 0.0))

    threshold_results: list[dict[str, Any]] = [
        _threshold_result("minimum_eval_sample_size", sample_size >= min_sample_size, sample_size, min_sample_size),
        _threshold_result(
            "max_pass_rate_delta_drop",
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

    if bool(policy.get("required_slices_must_not_degrade", True)):
        threshold_results.append(
            _threshold_result(
                "required_slices_must_not_degrade",
                len(required_slice_regressions) == 0,
                len(required_slice_regressions),
                0,
            )
        )

    allow_new_failures = bool(policy.get("allow_new_failures", False))
    threshold_results.append(
        _threshold_result(
            "allow_new_failures",
            allow_new_failures or len(new_failures) == 0,
            len(new_failures),
            0 if not allow_new_failures else "any",
        )
    )

    if bool(policy.get("indeterminate_is_blocking", policy.get("indeterminate_counts_as_regression", True))):
        threshold_results.append(
            _threshold_result(
                "indeterminate_is_blocking",
                len(indeterminate_failures) == 0,
                len(indeterminate_failures),
                0,
            )
        )

    case_set_mismatch = _case_set_mismatch(baseline_eval_results, candidate_eval_results)
    if bool(policy.get("coverage_parity_require_case_set_match", True)):
        has_case_set_mismatch = bool(case_set_mismatch["baseline_only_case_ids"] or case_set_mismatch["candidate_only_case_ids"])
        threshold_results.append(
            _threshold_result(
                "coverage_parity_require_case_set_match",
                not has_case_set_mismatch,
                case_set_mismatch,
                {"baseline_only_case_ids": [], "candidate_only_case_ids": []},
            )
        )

    slice_set_mismatch = _slice_set_mismatch(baseline_slice_summaries, candidate_slice_summaries)
    if bool(policy.get("coverage_parity_require_slice_set_match", True)):
        has_slice_set_mismatch = bool(
            slice_set_mismatch["baseline_only_slice_ids"] or slice_set_mismatch["candidate_only_slice_ids"]
        )
        threshold_results.append(
            _threshold_result(
                "coverage_parity_require_slice_set_match",
                not has_slice_set_mismatch,
                slice_set_mismatch,
                {"baseline_only_slice_ids": [], "candidate_only_slice_ids": []},
            )
        )

    candidate_system_response = str(candidate_control.get("system_response", "block"))
    blocking_system_responses = set(policy.get("blocking_system_responses") or ["freeze", "block"])
    threshold_results.append(
        _threshold_result(
            "candidate_control_response",
            candidate_system_response not in blocking_system_responses,
            candidate_system_response,
            sorted(blocking_system_responses),
        )
    )

    reasons: list[str] = []
    rollback_reason_map: dict[str, bool] = {
        "candidate_blocked_by_control": candidate_system_response in set(policy.get("rollback_system_responses") or ["block"]),
        "required_slice_regression": len(required_slice_regressions) > 0,
        "coverage_case_set_mismatch": bool(
            case_set_mismatch["baseline_only_case_ids"] or case_set_mismatch["candidate_only_case_ids"]
        ),
        "coverage_slice_set_mismatch": bool(
            slice_set_mismatch["baseline_only_slice_ids"] or slice_set_mismatch["candidate_only_slice_ids"]
        ),
        "new_failures_introduced": len(new_failures) > 0,
        "indeterminate_case_detected": len(indeterminate_failures) > 0,
        "pass_rate_drop_exceeds_rollback_threshold": pass_rate_delta < (-1.0 * float(policy.get("rollback_pass_rate_delta_drop_threshold", 1.0))),
    }

    failed_thresholds = [item["threshold"] for item in threshold_results if not item["passed"]]
    if failed_thresholds:
        reasons.extend(f"threshold_failed:{name}" for name in failed_thresholds)

    active_rollback_triggers = []
    for trigger in policy.get("rollback_triggers") or []:
        if rollback_reason_map.get(str(trigger), False):
            active_rollback_triggers.append(str(trigger))
    reasons.extend(f"rollback_triggered:{name}" for name in active_rollback_triggers)

    decision_candidates: list[str] = ["promote"]
    if failed_thresholds:
        decision_candidates.append("hold")
    if active_rollback_triggers:
        decision_candidates.append("rollback")
    decision = most_severe(decision_candidates, default="promote")
    rollback_target_version: str | None = baseline_version if decision == "rollback" else None
    if decision == "promote":
        reasons.append("all_release_policy_checks_passed")

    release_timestamp = timestamp or _utc_now()
    release_traces = sorted(
        {
            str(baseline_eval_summary.get("trace_id", "")).strip(),
            str(candidate_eval_summary.get("trace_id", "")).strip(),
        }
        - {""}
    )
    envelope = build_artifact_envelope(
        artifact_id=release_id,
        timestamp=release_timestamp,
        schema_version="1.1.0",
        primary_trace_ref=release_traces[0] if release_traces else release_id,
        related_trace_refs=release_traces[1:] if len(release_traces) > 1 else [],
    )

    record = {
        "artifact_type": "evaluation_release_record",
        **envelope,
        "release_id": release_id,
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
    }

    _validate(record, "evaluation_release_record")
    return record


def decision_exit_code(decision: str) -> int:
    mapping = {"promote": 0, "hold": 1, "rollback": 2}
    if decision not in mapping:
        raise ReleaseCanaryError(f"unsupported decision: {decision}")
    return mapping[decision]
