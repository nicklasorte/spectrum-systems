"""VAL-02 fail-closed exhaustive seam validation.

Runs deterministic seam-failure cases across governed runtime/governance entrypoints
and emits a single governed `fail_closed_exhaustive_result` artifact.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Dict, List

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.governance.done_certification import (
    DoneCertificationError,
    run_done_certification,
)
from spectrum_systems.modules.runtime.cross_run_intelligence import (
    CrossRunIntelligenceError,
    run_cross_run_intelligence,
)
from spectrum_systems.modules.runtime.evaluation_control import (
    EvaluationControlError,
    build_evaluation_control_decision,
)
from spectrum_systems.modules.runtime.evaluation_enforcement_bridge import (
    EnforcementBridgeError,
    enforce_budget_decision,
)
from spectrum_systems.modules.runtime.policy_backtesting import (
    PolicyBacktestingError,
    run_policy_backtest,
)
from spectrum_systems.modules.runtime.replay_engine import (
    compare_replay_outputs,
    validate_replay_prerequisites,
    validate_replay_result,
)


class FailClosedExhaustiveTestError(ValueError):
    """Raised when VAL-02 inputs are malformed."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_id(prefix: str, payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{prefix}-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:12].upper()}"


def _ok(outcome: str, artifact_ref: str, *, blocking_reason: str = "") -> Dict[str, Any]:
    return {
        "actual_outcome": outcome,
        "failure_artifact_ref": artifact_ref,
        "blocking_reason": blocking_reason,
        "is_blocking": True,
        "is_ambiguous": False,
    }


def _unexpected(outcome: str, artifact_ref: str, *, blocking_reason: str = "") -> Dict[str, Any]:
    return {
        "actual_outcome": outcome,
        "failure_artifact_ref": artifact_ref,
        "blocking_reason": blocking_reason,
        "is_blocking": False,
        "is_ambiguous": False,
    }


def _ambiguous(reason: str, artifact_ref: str = "") -> Dict[str, Any]:
    return {
        "actual_outcome": "ambiguous",
        "failure_artifact_ref": artifact_ref,
        "blocking_reason": reason,
        "is_blocking": False,
        "is_ambiguous": True,
    }


def _replay_case_missing_input() -> Dict[str, Any]:
    errors = validate_replay_prerequisites("")
    if errors:
        return _ok("block", "replay_prerequisites", blocking_reason="; ".join(errors))
    return _unexpected("allow", "", blocking_reason="missing input unexpectedly accepted")


def _replay_case_malformed_artifact() -> Dict[str, Any]:
    errors = validate_replay_result({"artifact_type": "replay_result"})
    if errors:
        return _ok("block", "replay_result_validation", blocking_reason="; ".join(errors))
    return _unexpected("allow", "", blocking_reason="malformed replay artifact unexpectedly valid")


def _replay_case_inconsistent_comparison_fields() -> Dict[str, Any]:
    comparison = compare_replay_outputs(
        [{"span_id": "s1", "status": "success"}],
        [{"original_span_id": "s1", "status": "failed"}],
    )
    matched = comparison.get("matched")
    if matched is False:
        return _ok("block", "replay_output_comparison", blocking_reason="replay status mismatch detected")
    if matched is None:
        return _ambiguous("comparison did not yield determinable mismatch", "replay_output_comparison")
    return _unexpected("allow", "", blocking_reason="inconsistent comparison fields unexpectedly matched")


def _eval_case_malformed_eval_summary() -> Dict[str, Any]:
    replay = copy.deepcopy(load_example("replay_result"))
    replay.pop("observability_metrics", None)
    try:
        build_evaluation_control_decision(replay)
    except EvaluationControlError as exc:
        return _ok("block", "evaluation_control_decision", blocking_reason=str(exc))
    return _unexpected("allow", "", blocking_reason="malformed eval summary path unexpectedly allowed")


def _eval_case_missing_required_fields() -> Dict[str, Any]:
    replay = copy.deepcopy(load_example("replay_result"))
    replay.pop("trace_id", None)
    try:
        build_evaluation_control_decision(replay)
    except EvaluationControlError as exc:
        return _ok("block", "evaluation_control_decision", blocking_reason=str(exc))
    return _unexpected("allow", "", blocking_reason="missing required eval fields unexpectedly allowed")


def _eval_case_ambiguous_value() -> Dict[str, Any]:
    replay = copy.deepcopy(load_example("replay_result"))
    replay["consistency_status"] = "indeterminate"
    decision = build_evaluation_control_decision(replay)
    response = str(decision.get("system_response") or "")
    if response in {"block", "freeze"}:
        return _ok("block", str(decision.get("decision_id") or "evaluation_control_decision"), blocking_reason="indeterminate mapped to fail-closed response")
    if response == "warn":
        return _unexpected("warn", str(decision.get("decision_id") or "evaluation_control_decision"), blocking_reason="indeterminate degraded to warning")
    return _unexpected("allow", str(decision.get("decision_id") or "evaluation_control_decision"), blocking_reason="indeterminate was not fail-closed")


def _enforcement_case_invalid_input() -> Dict[str, Any]:
    try:
        enforce_budget_decision({"decision_id": "bad"})
    except (EnforcementBridgeError, Exception) as exc:  # InvalidDecisionError derives from EnforcementBridgeError
        return _ok("block", "evaluation_enforcement_action", blocking_reason=str(exc))
    return _unexpected("allow", "", blocking_reason="invalid enforcement input unexpectedly allowed")


def _enforcement_case_missing_promotion_evidence() -> Dict[str, Any]:
    decision = copy.deepcopy(load_example("evaluation_budget_decision"))
    action = enforce_budget_decision(decision, context={"enforcement_scope": "promotion"})
    if action.get("allowed_to_proceed") is False and action.get("action_type") == "block":
        return _ok("block", str(action.get("action_id") or "evaluation_enforcement_action"), blocking_reason="promotion missing done_certification blocked")
    return _unexpected(str(action.get("action_type") or "allow"), str(action.get("action_id") or ""), blocking_reason="promotion evidence missing did not block")


def _enforcement_case_malformed_cert_or_trace_linkage() -> Dict[str, Any]:
    decision = copy.deepcopy(load_example("evaluation_budget_decision"))
    with TemporaryDirectory(prefix="val02-enf-") as tmp_dir:
        cert_path = Path(tmp_dir) / "bad_done_cert.json"
        cert_path.write_text(json.dumps({"certification_id": "bad", "trace_id": "wrong-trace"}), encoding="utf-8")
        action = enforce_budget_decision(
            decision,
            context={
                "enforcement_scope": "promotion",
                "done_certification_path": str(cert_path),
            },
        )
    if action.get("allowed_to_proceed") is False and action.get("action_type") == "block":
        return _ok("block", str(action.get("action_id") or "evaluation_enforcement_action"), blocking_reason="malformed certification blocked")
    return _unexpected(str(action.get("action_type") or "allow"), str(action.get("action_id") or ""), blocking_reason="malformed certification unexpectedly allowed")


def _valid_done_inputs(tmp: Path) -> Dict[str, str]:
    replay = copy.deepcopy(load_example("replay_result"))
    replay["consistency_status"] = "match"
    replay["drift_detected"] = False
    replay["failure_reason"] = None

    regression = {
        "blocked": False,
        "regression_status": "pass",
        "schema_version": "1.1.0",
        "artifact_type": "regression_result",
        "run_id": "reg-run-001",
        "suite_id": "suite-001",
        "created_at": "2026-03-28T00:00:00Z",
        "total_traces": 1,
        "passed_traces": 1,
        "failed_traces": 0,
        "pass_rate": 1.0,
        "overall_status": "pass",
        "results": [{"trace_id": replay["trace_id"], "comparison_digest": "a" * 64, "mismatch_summary": [], "passed": True}],
        "summary": {"drift_counts": {}, "average_reproducibility_score": 1.0},
    }

    cert_pack = copy.deepcopy(load_example("control_loop_certification_pack"))
    cert_pack["decision"] = "pass"
    cert_pack["certification_status"] = "certified"

    error_budget = copy.deepcopy(load_example("error_budget_status"))
    error_budget["budget_status"] = "healthy"

    policy = copy.deepcopy(load_example("evaluation_control_decision"))
    policy["system_status"] = "healthy"
    policy["system_response"] = "allow"
    policy["decision"] = "allow"

    refs = {
        "replay_result_ref": str(tmp / "replay.json"),
        "regression_result_ref": str(tmp / "regression.json"),
        "certification_pack_ref": str(tmp / "cert_pack.json"),
        "error_budget_ref": str(tmp / "error_budget.json"),
        "policy_ref": str(tmp / "policy.json"),
    }
    (tmp / "replay.json").write_text(json.dumps(replay), encoding="utf-8")
    (tmp / "regression.json").write_text(json.dumps(regression), encoding="utf-8")
    (tmp / "cert_pack.json").write_text(json.dumps(cert_pack), encoding="utf-8")
    (tmp / "error_budget.json").write_text(json.dumps(error_budget), encoding="utf-8")
    (tmp / "policy.json").write_text(json.dumps(policy), encoding="utf-8")
    return refs


def _cert_case_missing_required_refs() -> Dict[str, Any]:
    try:
        run_done_certification({"replay_result_ref": "missing.json"})
    except DoneCertificationError as exc:
        return _ok("block", "done_certification_record", blocking_reason=str(exc))
    return _unexpected("allow", "", blocking_reason="missing required certification refs unexpectedly allowed")


def _cert_case_invalid_error_budget_shape() -> Dict[str, Any]:
    with TemporaryDirectory(prefix="val02-done-") as tmp_dir:
        tmp = Path(tmp_dir)
        refs = _valid_done_inputs(tmp)
        bad = json.loads((tmp / "error_budget.json").read_text(encoding="utf-8"))
        bad["sli_values"] = "not-an-object"
        (tmp / "error_budget.json").write_text(json.dumps(bad), encoding="utf-8")
        try:
            run_done_certification(refs)
        except DoneCertificationError as exc:
            return _ok("block", "done_certification_record", blocking_reason=str(exc))
    return _unexpected("allow", "", blocking_reason="invalid error budget shape unexpectedly allowed")


def _cert_case_malformed_cert_pack() -> Dict[str, Any]:
    with TemporaryDirectory(prefix="val02-done-") as tmp_dir:
        tmp = Path(tmp_dir)
        refs = _valid_done_inputs(tmp)
        (tmp / "cert_pack.json").write_text("{bad json", encoding="utf-8")
        try:
            run_done_certification(refs)
        except DoneCertificationError as exc:
            return _ok("block", "done_certification_record", blocking_reason=str(exc))
    return _unexpected("allow", "", blocking_reason="malformed certification pack unexpectedly allowed")


def _cert_case_inconsistent_checks() -> Dict[str, Any]:
    with TemporaryDirectory(prefix="val02-done-") as tmp_dir:
        tmp = Path(tmp_dir)
        refs = _valid_done_inputs(tmp)
        replay = json.loads((tmp / "replay.json").read_text(encoding="utf-8"))
        replay["consistency_status"] = "mismatch"
        replay["drift_detected"] = True
        (tmp / "replay.json").write_text(json.dumps(replay), encoding="utf-8")
        result = run_done_certification(refs)
    if result.get("final_status") == "FAILED" and result.get("system_response") == "block":
        return _ok("fail", str(result.get("certification_id") or "done_certification_record"), blocking_reason="inconsistent checks failed certification")
    return _unexpected("allow", str(result.get("certification_id") or ""), blocking_reason="inconsistent check results did not fail closed")


def _xrun_base_inputs() -> Dict[str, Any]:
    trace_id = "11111111-1111-4111-8111-111111111111"
    return {
        "replay_results": [
            {"artifact_type": "replay_result", "schema_version": "1.0.0", "trace_id": trace_id, "replay_id": "rp-1"},
            {"artifact_type": "replay_result", "schema_version": "1.0.0", "trace_id": trace_id, "replay_id": "rp-2"},
        ],
        "eval_summaries": [
            copy.deepcopy(load_example("eval_summary")),
            copy.deepcopy(load_example("eval_summary")),
        ],
        "regression_results": [
            {"run_id": "reg-1", "results": [{"mismatch_summary": []}]},
            {"run_id": "reg-2", "results": [{"mismatch_summary": []}]},
        ],
        "drift_results": [
            copy.deepcopy(load_example("drift_detection_result")),
            copy.deepcopy(load_example("drift_detection_result")),
        ],
        "monitor_records": [
            copy.deepcopy(load_example("evaluation_monitor_record")),
            copy.deepcopy(load_example("evaluation_monitor_record")),
        ],
        "policy_ref": {"policy_id": "xrun-policy", "policy_version": "2026.03.28"},
    }


def _xrun_case_insufficient_inputs() -> Dict[str, Any]:
    payload = _xrun_base_inputs()
    payload.pop("drift_results")
    try:
        run_cross_run_intelligence(payload)
    except CrossRunIntelligenceError as exc:
        return _ok("block", "cross_run_intelligence_decision", blocking_reason=str(exc))
    return _unexpected("allow", "", blocking_reason="insufficient XRUN inputs unexpectedly allowed")


def _xrun_case_malformed_trend_metrics() -> Dict[str, Any]:
    payload = _xrun_base_inputs()
    payload["eval_summaries"][0]["failure_rate"] = "bad"
    try:
        run_cross_run_intelligence(payload)
    except CrossRunIntelligenceError as exc:
        return _ok("block", "cross_run_intelligence_decision", blocking_reason=str(exc))
    return _unexpected("allow", "", blocking_reason="malformed XRUN trend metrics unexpectedly allowed")


def _xrun_case_inconsistent_patterns_payload() -> Dict[str, Any]:
    payload = _xrun_base_inputs()
    payload["regression_results"] = [{"run_id": "reg-1", "results": []}, {"run_id": "reg-2", "results": []}]
    try:
        run_cross_run_intelligence(payload)
    except CrossRunIntelligenceError as exc:
        return _ok("block", "cross_run_intelligence_decision", blocking_reason=str(exc))
    return _unexpected("allow", "", blocking_reason="inconsistent XRUN pattern payload unexpectedly allowed")


def _policy_base_inputs() -> Dict[str, Any]:
    trace_id = "11111111-1111-4111-8111-111111111111"
    replay = copy.deepcopy(load_example("replay_result"))
    replay["trace_id"] = trace_id
    replay["replay_id"] = "rp-1"
    replay["replay_run_id"] = "run-rp-1"
    replay["observability_metrics"]["trace_refs"]["trace_id"] = trace_id
    replay["error_budget_status"]["trace_refs"]["trace_id"] = trace_id

    eval_summary = copy.deepcopy(load_example("eval_summary"))
    eval_summary["trace_id"] = trace_id
    eval_summary["eval_run_id"] = "ev-1"

    xrun = {
        "artifact_type": "cross_run_intelligence_decision",
        "schema_version": "2.0.0",
        "intelligence_id": "XRI-AAAAAAAAAAAA",
        "timestamp": "2026-03-28T00:00:00Z",
        "input_refs": {
            "replay_results": ["rp-1"],
            "eval_summaries": ["ev-1"],
            "regression_results": ["rg-1"],
            "drift_results": ["dr-1"],
            "monitor_records": ["mr-1"],
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

    return {
        "replay_results": [replay],
        "eval_summaries": [eval_summary],
        "error_budget_statuses": [copy.deepcopy(replay["error_budget_status"])],
        "cross_run_intelligence_decisions": [xrun],
        "baseline_policy_ref": {
            "policy_id": "policy-baseline",
            "policy_version": "v1",
            "thresholds": {"reliability_threshold": 0.8, "drift_threshold": 0.2, "trust_threshold": 0.8},
        },
        "candidate_policy_ref": {
            "policy_id": "policy-candidate",
            "policy_version": "v2",
            "thresholds": {"reliability_threshold": 0.8, "drift_threshold": 0.2, "trust_threshold": 0.8},
        },
    }


def _policy_case_missing_baseline() -> Dict[str, Any]:
    payload = _policy_base_inputs()
    payload.pop("baseline_policy_ref")
    try:
        run_policy_backtest(payload)
    except PolicyBacktestingError as exc:
        return _ok("block", "policy_backtest_result", blocking_reason=str(exc))
    return _unexpected("allow", "", blocking_reason="missing baseline policy unexpectedly allowed")


def _policy_case_malformed_candidate() -> Dict[str, Any]:
    payload = _policy_base_inputs()
    payload["candidate_policy_ref"] = {"policy_id": "candidate", "policy_version": "v2", "thresholds": {"reliability_threshold": 0.8}}
    try:
        run_policy_backtest(payload)
    except PolicyBacktestingError as exc:
        return _ok("block", "policy_backtest_result", blocking_reason=str(exc))
    return _unexpected("allow", "", blocking_reason="malformed candidate policy unexpectedly allowed")


def _policy_case_inconsistent_decision_inputs() -> Dict[str, Any]:
    payload = _policy_base_inputs()
    payload["cross_run_intelligence_decisions"][0]["trace_ids"] = ["trace-mismatch"]
    try:
        run_policy_backtest(payload)
    except PolicyBacktestingError as exc:
        return _ok("block", "policy_backtest_result", blocking_reason=str(exc))
    return _unexpected("allow", "", blocking_reason="inconsistent policy decision inputs unexpectedly allowed")


def _cases() -> List[Dict[str, Any]]:
    return [
        {"seam_name": "replay", "case_id": "replay_missing_input", "case_type": "missing_input", "fn": _replay_case_missing_input},
        {"seam_name": "replay", "case_id": "replay_malformed_artifact", "case_type": "malformed_artifact", "fn": _replay_case_malformed_artifact},
        {"seam_name": "replay", "case_id": "replay_inconsistent_comparison_fields", "case_type": "inconsistent_fields", "fn": _replay_case_inconsistent_comparison_fields},
        {"seam_name": "evaluation_control", "case_id": "eval_malformed_summary", "case_type": "malformed_input", "fn": _eval_case_malformed_eval_summary},
        {"seam_name": "evaluation_control", "case_id": "eval_missing_required_fields", "case_type": "missing_fields", "fn": _eval_case_missing_required_fields},
        {"seam_name": "evaluation_control", "case_id": "eval_ambiguous_indeterminate", "case_type": "ambiguous_value", "fn": _eval_case_ambiguous_value},
        {"seam_name": "evaluation_enforcement", "case_id": "enforcement_invalid_input", "case_type": "invalid_input", "fn": _enforcement_case_invalid_input},
        {"seam_name": "evaluation_enforcement", "case_id": "enforcement_missing_promotion_evidence", "case_type": "missing_evidence", "fn": _enforcement_case_missing_promotion_evidence},
        {"seam_name": "evaluation_enforcement", "case_id": "enforcement_malformed_certification", "case_type": "malformed_certification", "fn": _enforcement_case_malformed_cert_or_trace_linkage},
        {"seam_name": "done_certification", "case_id": "done_missing_required_refs", "case_type": "missing_input", "fn": _cert_case_missing_required_refs},
        {"seam_name": "done_certification", "case_id": "done_invalid_error_budget_shape", "case_type": "invalid_shape", "fn": _cert_case_invalid_error_budget_shape},
        {"seam_name": "done_certification", "case_id": "done_malformed_certification_pack", "case_type": "malformed_input", "fn": _cert_case_malformed_cert_pack},
        {"seam_name": "done_certification", "case_id": "done_inconsistent_check_results", "case_type": "inconsistent_checks", "fn": _cert_case_inconsistent_checks},
        {"seam_name": "cross_run_intelligence", "case_id": "xrun_insufficient_inputs", "case_type": "missing_input", "fn": _xrun_case_insufficient_inputs},
        {"seam_name": "cross_run_intelligence", "case_id": "xrun_malformed_trend_metrics", "case_type": "malformed_input", "fn": _xrun_case_malformed_trend_metrics},
        {"seam_name": "cross_run_intelligence", "case_id": "xrun_inconsistent_pattern_payload", "case_type": "inconsistent_payload", "fn": _xrun_case_inconsistent_patterns_payload},
        {"seam_name": "policy_backtesting", "case_id": "policy_missing_baseline", "case_type": "missing_policy", "fn": _policy_case_missing_baseline},
        {"seam_name": "policy_backtesting", "case_id": "policy_malformed_candidate", "case_type": "malformed_policy", "fn": _policy_case_malformed_candidate},
        {"seam_name": "policy_backtesting", "case_id": "policy_inconsistent_decision_inputs", "case_type": "inconsistent_inputs", "fn": _policy_case_inconsistent_decision_inputs},
    ]


def run_fail_closed_exhaustive_test(input_refs: dict) -> dict:
    """Run VAL-02 seam matrix and return governed fail_closed_exhaustive_result."""
    if not isinstance(input_refs, dict):
        raise FailClosedExhaustiveTestError("input_refs must be an object")

    matrix_results: List[Dict[str, Any]] = []
    silent_success_detected = False
    ambiguous_outcome_detected = False

    for case in _cases():
        expected = "block_or_failure_artifact"
        try:
            observed = case["fn"]()
        except Exception as exc:  # noqa: BLE001
            observed = _ok(
                "block",
                f"exception:{exc.__class__.__name__}",
                blocking_reason=f"governed exception path: {exc}",
            )

        actual_outcome = str(observed.get("actual_outcome") or "ambiguous")
        artifact_ref = str(observed.get("failure_artifact_ref") or "")
        is_blocking = bool(observed.get("is_blocking"))
        is_ambiguous = bool(observed.get("is_ambiguous"))

        if actual_outcome in {"allow", "warn", "partial_success"} or not is_blocking or not artifact_ref:
            silent_success_detected = True
        if is_ambiguous or actual_outcome == "ambiguous":
            ambiguous_outcome_detected = True

        passed = bool(is_blocking and artifact_ref and not is_ambiguous)

        matrix_results.append(
            {
                "seam_name": case["seam_name"],
                "case_id": case["case_id"],
                "case_type": case["case_type"],
                "expected_outcome": expected,
                "actual_outcome": actual_outcome,
                "passed": passed,
                "failure_artifact_ref": artifact_ref,
                "blocking_reason": str(observed.get("blocking_reason") or ""),
            }
        )

    total_cases = len(matrix_results)
    total_passed = sum(1 for item in matrix_results if item["passed"])
    total_failed = total_cases - total_passed
    final_status = "PASSED"
    if total_failed > 0 or silent_success_detected or ambiguous_outcome_detected:
        final_status = "FAILED"

    deterministic_seed = {
        "input_refs": input_refs,
        "seam_results": matrix_results,
        "silent_success_detected": silent_success_detected,
        "ambiguous_outcome_detected": ambiguous_outcome_detected,
    }

    result = {
        "validation_run_id": _stable_id("VAL02", deterministic_seed),
        "timestamp": _now_iso(),
        "input_refs": input_refs,
        "seam_results": matrix_results,
        "summary": {
            "total_cases": total_cases,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "silent_success_detected": silent_success_detected,
            "ambiguous_outcome_detected": ambiguous_outcome_detected,
        },
        "final_status": final_status,
        "trace_id": str(input_refs.get("trace_id") or _stable_id("TRACE", deterministic_seed)),
    }

    validate_artifact(result, "fail_closed_exhaustive_result")
    return result
