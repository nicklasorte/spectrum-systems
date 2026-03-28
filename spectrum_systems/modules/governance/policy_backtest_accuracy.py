"""VAL-05 policy backtest accuracy validation over real ADV-01 seam."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.policy_backtesting import (
    PolicyBacktestingError,
    run_policy_backtest,
)


class PolicyBacktestAccuracyError(ValueError):
    """Raised when VAL-05 input refs are malformed."""


_CASE_TYPES = (
    "identical_policy_no_change",
    "candidate_improves_without_new_risk",
    "candidate_introduces_missed_failure",
    "candidate_overblocks_significantly",
    "mixed_delta_requires_review",
    "malformed_candidate_policy",
    "inconsistent_input_bundle",
)


_DEFAULT_EXPECTED = {
    "identical_policy_no_change": {"recommendation": "require_review", "risks": []},
    "candidate_improves_without_new_risk": {"recommendation": "accept_policy", "risks": []},
    "candidate_introduces_missed_failure": {"recommendation": "reject_policy", "risks": ["missed_failures"]},
    "candidate_overblocks_significantly": {"recommendation": "reject_policy", "risks": ["overblocking"]},
    "mixed_delta_requires_review": {"recommendation": "require_review", "risks": []},
    "malformed_candidate_policy": {"recommendation": "fail_closed", "risks": []},
    "inconsistent_input_bundle": {"recommendation": "fail_closed", "risks": []},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_id(prefix: str, payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


def _require_list_of_objects(input_refs: Dict[str, Any], field: str) -> List[Dict[str, Any]]:
    value = input_refs.get(field)
    if not isinstance(value, list) or not value:
        raise PolicyBacktestAccuracyError(f"{field} must be a non-empty list")
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise PolicyBacktestAccuracyError(f"{field}[{idx}] must be an object")
    return _clone(value)


def _require_object(input_refs: Dict[str, Any], field: str) -> Dict[str, Any]:
    value = input_refs.get(field)
    if not isinstance(value, dict):
        raise PolicyBacktestAccuracyError(f"{field} must be an object")
    return _clone(value)


def _default_bundle() -> Dict[str, Any]:
    replay = _clone(load_example("replay_result"))
    eval_summary = _clone(load_example("eval_summary"))
    budget = _clone(load_example("error_budget_status"))
    trace_id = "11111111-1111-4111-8111-111111111111"
    replay["trace_id"] = trace_id
    replay["timestamp"] = "2026-03-28T00:00:00Z"
    replay["replay_id"] = "rp-val05"
    replay["replay_run_id"] = "run-rp-val05"
    replay["consistency_status"] = "match"
    replay["drift_detected"] = False
    replay["observability_metrics"]["trace_refs"]["trace_id"] = trace_id
    replay["error_budget_status"]["trace_refs"]["trace_id"] = trace_id

    eval_summary["trace_id"] = trace_id
    eval_summary["eval_run_id"] = "eval-val05"

    budget["trace_refs"]["trace_id"] = trace_id
    budget["budget_status"] = "healthy"

    xrun = {
        "artifact_type": "cross_run_intelligence_decision",
        "schema_version": "2.0.0",
        "intelligence_id": "XRI-ABCDEF123456",
        "timestamp": "2026-03-28T00:00:00Z",
        "input_refs": {
            "replay_results": ["rp-val05"],
            "eval_summaries": ["eval-val05"],
            "regression_results": ["reg-1"],
            "drift_results": ["drift-1"],
            "monitor_records": ["monitor-1"],
            "policy_ref": "policy-v1",
        },
        "aggregated_metrics": {
            "failure_rate_trend": 0.0,
            "drift_trend": 0.0,
            "regression_density": 0.0,
            "reproducibility_variance": 0.0,
        },
        "detected_patterns": [],
        "recommended_actions": [],
        "system_signal": "stable",
        "trace_ids": [trace_id],
        "policy_version": "2026.03.28",
    }

    baseline = {
        "policy_id": "policy-baseline",
        "policy_version": "v1",
        "thresholds": {
            "reliability_threshold": 0.8,
            "drift_threshold": 0.2,
            "trust_threshold": 0.8,
        },
    }

    return {
        "replay_results": [replay],
        "eval_summaries": [eval_summary],
        "error_budget_statuses": [budget],
        "cross_run_intelligence_decisions": [xrun],
        "baseline_policy_ref": baseline,
    }


def _base_inputs(input_refs: Dict[str, Any]) -> Dict[str, Any]:
    defaults = _default_bundle()
    replay_results = _require_list_of_objects(input_refs if "replay_results" in input_refs else defaults, "replay_results")
    eval_summaries = _require_list_of_objects(input_refs if "eval_summaries" in input_refs else defaults, "eval_summaries")
    budgets = _require_list_of_objects(input_refs if "error_budget_statuses" in input_refs else defaults, "error_budget_statuses")
    xruns = _require_list_of_objects(input_refs if "cross_run_intelligence_decisions" in input_refs else defaults, "cross_run_intelligence_decisions")
    baseline = _require_object(input_refs if "baseline_policy_ref" in input_refs else defaults, "baseline_policy_ref")

    return {
        "replay_results": replay_results,
        "eval_summaries": eval_summaries,
        "error_budget_statuses": budgets,
        "cross_run_intelligence_decisions": xruns,
        "baseline_policy_ref": baseline,
    }


def _case_payload(base: Dict[str, Any], case_type: str) -> Dict[str, Any]:
    payload = _clone(base)
    baseline = payload["baseline_policy_ref"]

    if case_type == "identical_policy_no_change":
        payload["candidate_policy_ref"] = _clone(baseline)
        payload["candidate_policy_ref"]["policy_id"] = "policy-candidate-identical"
    elif case_type == "candidate_improves_without_new_risk":
        replay = payload["replay_results"][0]
        replay["consistency_status"] = "match"
        replay["drift_detected"] = False
        replay["observability_metrics"]["metrics"]["replay_success_rate"] = 0.85
        payload["baseline_policy_ref"]["thresholds"]["reliability_threshold"] = 0.9
        payload["candidate_policy_ref"] = {
            "policy_id": "policy-candidate-improved",
            "policy_version": "v2",
            "thresholds": {"reliability_threshold": 0.8, "drift_threshold": 0.2, "trust_threshold": 0.8},
        }
    elif case_type == "candidate_introduces_missed_failure":
        replay = payload["replay_results"][0]
        replay["consistency_status"] = "mismatch"
        replay["drift_detected"] = True
        replay["observability_metrics"]["metrics"]["drift_exceed_threshold_rate"] = 0.6
        replay["observability_metrics"]["metrics"]["replay_success_rate"] = 0.95
        payload["baseline_policy_ref"]["thresholds"]["trust_threshold"] = 0.0
        payload["baseline_policy_ref"]["thresholds"]["drift_threshold"] = 0.2
        payload["candidate_policy_ref"] = {
            "policy_id": "policy-candidate-missed-failure",
            "policy_version": "v2",
            "thresholds": {"reliability_threshold": 0.8, "drift_threshold": 0.8, "trust_threshold": 0.0},
        }
    elif case_type == "candidate_overblocks_significantly":
        replay = payload["replay_results"][0]
        replay["consistency_status"] = "mismatch"
        replay["drift_detected"] = True
        replay["observability_metrics"]["metrics"]["drift_exceed_threshold_rate"] = 0.0
        replay["observability_metrics"]["metrics"]["replay_success_rate"] = 0.95
        payload["baseline_policy_ref"]["thresholds"]["trust_threshold"] = 0.0
        payload["candidate_policy_ref"] = {
            "policy_id": "policy-candidate-overblock",
            "policy_version": "v2",
            "thresholds": {"reliability_threshold": 0.8, "drift_threshold": 0.2, "trust_threshold": 0.8},
        }
    elif case_type == "mixed_delta_requires_review":
        replay = payload["replay_results"][0]
        replay["consistency_status"] = "match"
        replay["drift_detected"] = False
        replay["observability_metrics"]["metrics"]["replay_success_rate"] = 0.82
        payload["baseline_policy_ref"]["thresholds"]["reliability_threshold"] = 0.8
        payload["candidate_policy_ref"] = {
            "policy_id": "policy-candidate-mixed",
            "policy_version": "v2",
            "thresholds": {"reliability_threshold": 0.85, "drift_threshold": 0.2, "trust_threshold": 0.8},
        }
    elif case_type == "malformed_candidate_policy":
        payload["candidate_policy_ref"] = {
            "policy_id": "policy-candidate-malformed",
            "policy_version": "v2",
            "thresholds": {"reliability_threshold": 0.8, "drift_threshold": 0.2},
        }
    elif case_type == "inconsistent_input_bundle":
        payload["candidate_policy_ref"] = {
            "policy_id": "policy-candidate-safe",
            "policy_version": "v2",
            "thresholds": {"reliability_threshold": 0.8, "drift_threshold": 0.2, "trust_threshold": 0.8},
        }
        payload["eval_summaries"][0]["trace_id"] = "22222222-2222-4222-8222-222222222222"
    else:
        raise PolicyBacktestAccuracyError(f"unsupported case_type: {case_type}")

    return payload


def _execute_case(case_type: str, payload: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, Any]:
    expected_recommendation = str(expected.get("recommendation", "require_review"))
    expected_risks = sorted({str(r) for r in (expected.get("risks") or [])})

    try:
        result = run_policy_backtest(payload)
        actual_recommendation = str(result.get("recommended_action") or "")
        actual_risks = sorted({str(r) for r in (result.get("detected_risks") or [])})
        passed = actual_recommendation == expected_recommendation and set(expected_risks).issubset(set(actual_risks))
        blocking_reason = "" if passed else "recommendation/risk mismatch"
    except PolicyBacktestingError as exc:
        actual_recommendation = "fail_closed"
        actual_risks = []
        passed = expected_recommendation == "fail_closed"
        blocking_reason = "" if passed else str(exc)

    return {
        "case_id": f"VAL05-{case_type}",
        "case_type": case_type,
        "expected_recommendation": expected_recommendation,
        "actual_recommendation": actual_recommendation,
        "expected_risks": expected_risks,
        "actual_risks": actual_risks,
        "passed": passed,
        "blocking_reason": blocking_reason,
    }


def _merge_expected(input_refs: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    resolved = _clone(_DEFAULT_EXPECTED)
    expected = input_refs.get("expected_outcomes_ref")
    if expected is None:
        return resolved
    if not isinstance(expected, dict):
        raise PolicyBacktestAccuracyError("expected_outcomes_ref must be an object when provided")
    for case_type, cfg in expected.items():
        if case_type not in resolved:
            continue
        if not isinstance(cfg, dict):
            raise PolicyBacktestAccuracyError(f"expected_outcomes_ref.{case_type} must be an object")
        recommendation = cfg.get("recommendation", resolved[case_type]["recommendation"])
        risks = cfg.get("risks", resolved[case_type]["risks"])
        if not isinstance(recommendation, str):
            raise PolicyBacktestAccuracyError(f"expected_outcomes_ref.{case_type}.recommendation must be a string")
        if not isinstance(risks, list):
            raise PolicyBacktestAccuracyError(f"expected_outcomes_ref.{case_type}.risks must be a list")
        resolved[case_type] = {"recommendation": recommendation, "risks": risks}
    return resolved


def _extract_trace_ids(base: Dict[str, Any]) -> List[str]:
    trace_ids = []
    for replay in base["replay_results"]:
        trace_id = replay.get("trace_id")
        if isinstance(trace_id, str) and trace_id:
            trace_ids.append(trace_id)
    return sorted(set(trace_ids)) or ["trace-unknown"]


def _flags_from_cases(validation_cases: List[Dict[str, Any]]) -> Tuple[bool, bool, bool]:
    false_accept = False
    false_reject = False
    ambiguous_miss = False
    for case in validation_cases:
        expected = case["expected_recommendation"]
        actual = case["actual_recommendation"]
        if expected == "reject_policy" and actual == "accept_policy":
            false_accept = True
        if expected == "accept_policy" and actual in {"reject_policy", "require_review", "fail_closed"}:
            false_reject = True
        if expected == "require_review" and actual == "accept_policy":
            ambiguous_miss = True
    return false_accept, false_reject, ambiguous_miss


def run_policy_backtest_accuracy(input_refs: dict) -> dict:
    """Run VAL-05 validation matrix against real ADV-01 policy backtesting seam."""
    if not isinstance(input_refs, dict):
        raise PolicyBacktestAccuracyError("input_refs must be an object")

    base = _base_inputs(input_refs)
    expected_map = _merge_expected(input_refs)

    validation_cases = [
        _execute_case(case_type, _case_payload(base, case_type), expected_map[case_type])
        for case_type in _CASE_TYPES
    ]

    false_accept, false_reject, ambiguous_miss = _flags_from_cases(validation_cases)
    total_cases = len(validation_cases)
    passed_cases = sum(1 for c in validation_cases if c["passed"])
    failed_cases = total_cases - passed_cases

    summary = {
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "false_accept_detected": false_accept,
        "false_reject_detected": false_reject,
        "ambiguous_review_detected": ambiguous_miss,
    }

    final_status = "PASSED"
    if failed_cases > 0 or false_accept or false_reject or ambiguous_miss:
        final_status = "FAILED"

    canonical_input_refs = {
        "replay_results": [r.get("replay_id", "replay-unknown") for r in base["replay_results"]],
        "eval_summaries": [e.get("eval_run_id", "eval-unknown") for e in base["eval_summaries"]],
        "error_budget_statuses": [b.get("artifact_id", "budget-unknown") for b in base["error_budget_statuses"]],
        "cross_run_intelligence_decisions": [x.get("intelligence_id", "xrun-unknown") for x in base["cross_run_intelligence_decisions"]],
        "baseline_policy_ref": base["baseline_policy_ref"].get("policy_id", "baseline-unknown"),
        "candidate_policy_refs": [
            _case_payload(base, case_type).get("candidate_policy_ref", {}).get("policy_id", f"candidate-{case_type}")
            for case_type in _CASE_TYPES
        ],
    }
    if "expected_outcomes_ref" in input_refs:
        canonical_input_refs["expected_outcomes_ref"] = "governed-override"

    result = {
        "artifact_type": "policy_backtest_accuracy_result",
        "schema_version": "1.0.0",
        "validation_run_id": _stable_id(
            "PBTA",
            {
                "baseline": canonical_input_refs["baseline_policy_ref"],
                "candidates": canonical_input_refs["candidate_policy_refs"],
                "trace_ids": _extract_trace_ids(base),
            },
        ),
        "timestamp": _now_iso(),
        "input_refs": canonical_input_refs,
        "validation_cases": validation_cases,
        "summary": summary,
        "final_status": final_status,
        "trace_ids": _extract_trace_ids(base),
    }

    validate_artifact(result, "policy_backtest_accuracy_result")
    return result
