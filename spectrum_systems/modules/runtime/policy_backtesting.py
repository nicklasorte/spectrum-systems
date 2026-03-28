"""Deterministic policy backtesting / scenario simulation (ADV-01).

This module reuses replay_result artifacts as the authoritative execution surface
and replays control decisions under baseline and candidate policy thresholds.

Fail-closed rules
-----------------
- Missing or malformed governed input artifacts raise ``PolicyBacktestingError``.
- Schema-invalid inputs raise ``PolicyBacktestingError``.
- Invalid policy refs or threshold values raise ``PolicyBacktestingError``.
- Inconsistent trace linkage across replay/eval/budget/XRUN inputs raises
  ``PolicyBacktestingError``.
- Output is returned only after successful schema validation.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema, validate_artifact
from spectrum_systems.modules.runtime.evaluation_control import (
    EvaluationControlError,
    build_evaluation_control_decision,
)


class PolicyBacktestingError(ValueError):
    """Raised for deterministic fail-closed backtesting failures."""


def _validate_schema_or_raise(payload: Dict[str, Any], schema_name: str, context: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise PolicyBacktestingError(f"{context} failed schema validation: {details}")


def _require_sequence(input_refs: Dict[str, Any], field: str) -> List[Dict[str, Any]]:
    value = input_refs.get(field)
    if not isinstance(value, list) or not value:
        raise PolicyBacktestingError(f"{field} must be a non-empty list")
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise PolicyBacktestingError(f"{field}[{idx}] must be an object")
    return value


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyBacktestingError(f"{field} must be a non-empty string")
    return value.strip()


def _require_ratio(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)):
        raise PolicyBacktestingError(f"{field} must be numeric")
    ratio = float(value)
    if ratio < 0.0 or ratio > 1.0:
        raise PolicyBacktestingError(f"{field} must be between 0.0 and 1.0")
    return ratio


def _parse_policy_ref(policy_ref: Any, field: str) -> Dict[str, Any]:
    if not isinstance(policy_ref, dict):
        raise PolicyBacktestingError(f"{field} must be an object")

    policy_version = _require_non_empty_string(policy_ref.get("policy_version"), f"{field}.policy_version")
    thresholds = policy_ref.get("thresholds")
    if not isinstance(thresholds, dict):
        raise PolicyBacktestingError(f"{field}.thresholds must be an object")

    required = ("reliability_threshold", "drift_threshold", "trust_threshold")
    parsed_thresholds: Dict[str, float] = {}
    for key in required:
        parsed_thresholds[key] = _require_ratio(thresholds.get(key), f"{field}.thresholds.{key}")

    return {
        "policy_id": _require_non_empty_string(
            policy_ref.get("policy_id") or policy_version,
            f"{field}.policy_id",
        ),
        "policy_version": policy_version,
        "thresholds": parsed_thresholds,
    }


def _stable_id(prefix: str, payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


def _decision_change_type(baseline: str, candidate: str) -> str:
    if baseline == candidate:
        return "no_change"
    return f"{baseline}→{candidate}"


def _is_blocking_response(response: str) -> bool:
    return response in {"freeze", "block"}


def run_policy_backtest(input_refs: dict) -> dict:
    """Run deterministic policy backtesting against governed runtime artifacts."""
    if not isinstance(input_refs, dict):
        raise PolicyBacktestingError("input_refs must be an object")

    replay_results = _require_sequence(input_refs, "replay_results")
    eval_summaries = _require_sequence(input_refs, "eval_summaries")
    error_budget_statuses = _require_sequence(input_refs, "error_budget_statuses")
    xrun_decisions = _require_sequence(input_refs, "cross_run_intelligence_decisions")

    baseline_policy = _parse_policy_ref(input_refs.get("baseline_policy_ref"), "baseline_policy_ref")
    candidate_policy = _parse_policy_ref(input_refs.get("candidate_policy_ref"), "candidate_policy_ref")

    replay_trace_ids: List[str] = []
    replay_timestamps: List[str] = []
    replay_refs: List[str] = []

    for idx, replay in enumerate(replay_results):
        _validate_schema_or_raise(replay, "replay_result", f"replay_results[{idx}]")
        trace_id = _require_non_empty_string(replay.get("trace_id"), f"replay_results[{idx}].trace_id")
        replay_trace_ids.append(trace_id)
        replay_timestamps.append(_require_non_empty_string(replay.get("timestamp"), f"replay_results[{idx}].timestamp"))
        replay_refs.append(_require_non_empty_string(replay.get("replay_id"), f"replay_results[{idx}].replay_id"))

    eval_trace_ids = set()
    eval_refs: List[str] = []
    for idx, summary in enumerate(eval_summaries):
        _validate_schema_or_raise(summary, "eval_summary", f"eval_summaries[{idx}]")
        eval_trace_ids.add(_require_non_empty_string(summary.get("trace_id"), f"eval_summaries[{idx}].trace_id"))
        eval_refs.append(_require_non_empty_string(summary.get("eval_run_id"), f"eval_summaries[{idx}].eval_run_id"))

    budget_trace_ids = set()
    budget_refs: List[str] = []
    budget_impact = {"healthy": 0, "warning": 0, "exhausted": 0, "invalid": 0}
    for idx, status in enumerate(error_budget_statuses):
        _validate_schema_or_raise(status, "error_budget_status", f"error_budget_statuses[{idx}]")
        trace_ref = status.get("trace_refs") or {}
        budget_trace_id = _require_non_empty_string(trace_ref.get("trace_id"), f"error_budget_statuses[{idx}].trace_refs.trace_id")
        budget_trace_ids.add(budget_trace_id)
        budget_refs.append(_require_non_empty_string(status.get("artifact_id"), f"error_budget_statuses[{idx}].artifact_id"))
        budget_status = _require_non_empty_string(status.get("budget_status"), f"error_budget_statuses[{idx}].budget_status")
        if budget_status not in budget_impact:
            raise PolicyBacktestingError(
                f"error_budget_statuses[{idx}].budget_status must be one of {sorted(budget_impact.keys())}"
            )
        budget_impact[budget_status] += 1

    xrun_refs: List[str] = []
    xrun_trace_ids = set()
    for idx, decision in enumerate(xrun_decisions):
        _validate_schema_or_raise(decision, "cross_run_intelligence_decision", f"cross_run_intelligence_decisions[{idx}]")
        if decision.get("schema_version") != "2.0.0":
            raise PolicyBacktestingError(
                "cross_run_intelligence_decisions must use schema_version=2.0.0 for governed runtime integration"
            )
        trace_ids = decision.get("trace_ids")
        if not isinstance(trace_ids, list) or not trace_ids:
            raise PolicyBacktestingError(f"cross_run_intelligence_decisions[{idx}].trace_ids must be non-empty")
        for trace_id in trace_ids:
            xrun_trace_ids.add(_require_non_empty_string(trace_id, f"cross_run_intelligence_decisions[{idx}].trace_ids[]"))
        xrun_refs.append(_require_non_empty_string(decision.get("intelligence_id"), f"cross_run_intelligence_decisions[{idx}].intelligence_id"))

    replay_trace_set = set(replay_trace_ids)
    if not replay_trace_set.issubset(eval_trace_ids):
        raise PolicyBacktestingError("inconsistent input: replay trace_ids missing from eval_summaries")
    if not replay_trace_set.issubset(budget_trace_ids):
        raise PolicyBacktestingError("inconsistent input: replay trace_ids missing from error_budget_statuses")
    if not replay_trace_set.issubset(xrun_trace_ids):
        raise PolicyBacktestingError("inconsistent input: replay trace_ids missing from cross_run_intelligence_decisions")

    decision_deltas: List[Dict[str, str]] = []
    baseline_block_count = 0
    candidate_block_count = 0
    baseline_pass_count = 0
    candidate_pass_count = 0

    missed_failures = 0
    overblocking_events = 0

    candidate_trace_responses: Dict[str, set[str]] = {}

    for replay in replay_results:
        try:
            baseline_decision = build_evaluation_control_decision(
                replay,
                thresholds=baseline_policy["thresholds"],
            )
            candidate_decision = build_evaluation_control_decision(
                replay,
                thresholds=candidate_policy["thresholds"],
            )
        except EvaluationControlError as exc:
            raise PolicyBacktestingError(f"inconsistent decision results: {exc}") from exc

        trace_id = _require_non_empty_string(replay.get("trace_id"), "replay_results[].trace_id")

        baseline_response = _require_non_empty_string(
            baseline_decision.get("system_response"),
            "baseline decision.system_response",
        )
        candidate_response = _require_non_empty_string(
            candidate_decision.get("system_response"),
            "candidate decision.system_response",
        )

        if baseline_response == "allow":
            baseline_pass_count += 1
        if candidate_response == "allow":
            candidate_pass_count += 1

        if _is_blocking_response(baseline_response):
            baseline_block_count += 1
        if _is_blocking_response(candidate_response):
            candidate_block_count += 1

        if _is_blocking_response(baseline_response) and candidate_response == "allow":
            missed_failures += 1
        if not _is_blocking_response(baseline_response) and _is_blocking_response(candidate_response):
            overblocking_events += 1

        candidate_trace_responses.setdefault(trace_id, set()).add(candidate_response)

        decision_deltas.append(
            {
                "trace_id": trace_id,
                "baseline_decision": baseline_response,
                "candidate_decision": candidate_response,
                "change_type": _decision_change_type(baseline_response, candidate_response),
            }
        )

    total = float(len(replay_results))
    baseline_pass_rate = round(baseline_pass_count / total, 6)
    candidate_pass_rate = round(candidate_pass_count / total, 6)
    baseline_block_rate = round(baseline_block_count / total, 6)
    candidate_block_rate = round(candidate_block_count / total, 6)

    delta_pass_rate = round(candidate_pass_rate - baseline_pass_rate, 6)
    delta_block_rate = round(candidate_block_rate - baseline_block_rate, 6)

    instability = any(len(responses) > 1 for responses in candidate_trace_responses.values())

    detected_risks: List[str] = []
    if missed_failures > 0:
        detected_risks.append("missed_failures")
    if overblocking_events > 0 and (delta_block_rate >= 0.2 or overblocking_events >= 2):
        detected_risks.append("overblocking")
    if instability:
        detected_risks.append("instability")

    if "missed_failures" in detected_risks or "overblocking" in detected_risks:
        recommended_action = "reject_policy"
    elif delta_pass_rate > 0 and delta_block_rate <= 0 and not detected_risks:
        recommended_action = "accept_policy"
    else:
        recommended_action = "require_review"

    if recommended_action == "accept_policy" and not detected_risks:
        system_confidence = "high"
    elif "missed_failures" in detected_risks or "instability" in detected_risks:
        system_confidence = "low"
    else:
        system_confidence = "medium"

    input_identity = {
        "replay_results": replay_refs,
        "eval_summaries": eval_refs,
        "error_budget_statuses": budget_refs,
        "cross_run_intelligence_decisions": xrun_refs,
        "baseline_policy_ref": baseline_policy["policy_id"],
        "candidate_policy_ref": candidate_policy["policy_id"],
    }

    result = {
        "artifact_type": "policy_backtest_result",
        "schema_version": "1.0.0",
        "backtest_id": _stable_id(
            "PBT",
            {
                "inputs": input_identity,
                "baseline_policy_version": baseline_policy["policy_version"],
                "candidate_policy_version": candidate_policy["policy_version"],
            },
        ),
        "timestamp": max(replay_timestamps),
        "input_refs": input_identity,
        "baseline_policy_version": baseline_policy["policy_version"],
        "candidate_policy_version": candidate_policy["policy_version"],
        "comparison_summary": {
            "baseline_pass_rate": baseline_pass_rate,
            "candidate_pass_rate": candidate_pass_rate,
            "baseline_block_rate": baseline_block_rate,
            "candidate_block_rate": candidate_block_rate,
            "delta_pass_rate": delta_pass_rate,
            "delta_block_rate": delta_block_rate,
            "error_budget_impact": budget_impact,
        },
        "decision_deltas": decision_deltas,
        "detected_risks": detected_risks,
        "recommended_action": recommended_action,
        "system_confidence": system_confidence,
        "trace_ids": sorted(replay_trace_set),
    }

    validate_artifact(result, "policy_backtest_result")
    return result
