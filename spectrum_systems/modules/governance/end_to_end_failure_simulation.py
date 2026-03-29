"""VAL-08 end-to-end failure simulation over governed runtime/governance seams."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Tuple

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.governance.done_certification import (
    DoneCertificationError,
    run_done_certification,
)
from spectrum_systems.modules.runtime.context_admission import run_context_admission
from spectrum_systems.modules.runtime.cross_run_intelligence import run_cross_run_intelligence
from spectrum_systems.modules.runtime.evaluation_control import build_evaluation_control_decision
from spectrum_systems.modules.runtime.evaluation_enforcement_bridge import run_enforcement_bridge
from spectrum_systems.modules.runtime.governed_failure_injection import run_governed_failure_injection
from spectrum_systems.modules.runtime.policy_backtesting import run_policy_backtest


class EndToEndFailureSimulationError(ValueError):
    """Raised when VAL-08 simulation inputs are malformed."""


_CASE_SPECS: Tuple[Tuple[str, str, List[str], str], ...] = (
    ("VAL08-A", "context_downstream_failure", ["malformed_context_bundle"], "blocked_before_downstream_promotion"),
    ("VAL08-B", "replay_mismatch_certification_attempt", ["replay_mismatch", "certification_attempt"], "certification_failed_and_enforcement_blocked"),
    ("VAL08-C", "eval_control_inconsistency_promotion_attempt", ["eval_control_inconsistency", "promotion_attempt"], "promotion_blocked_with_explicit_artifact"),
    ("VAL08-D", "error_budget_exhausted_valid_pipeline", ["error_budget_exhausted"], "control_or_certification_blocks"),
    ("VAL08-E", "failure_injection_violation_downstream_present", ["failure_injection_violation", "downstream_artifacts_present"], "fail_closed_dominates_and_blocks"),
    ("VAL08-F", "xrun_warning_policy_reject_certification_attempt", ["xrun_warning", "policy_backtest_reject", "certification_attempt"], "no_false_promotion_block_explicit"),
    ("VAL08-G", "multi_fault_combined", ["malformed_context_bundle", "replay_mismatch", "error_budget_exhausted", "failure_injection_violation"], "block_traceable_no_silent_propagation"),
)


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


def _stable_hash(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, payload: Dict[str, Any]) -> str:
    return f"{prefix}-{_stable_hash(payload)[:12].upper()}"


def _deterministic_timestamp(seed: Dict[str, Any]) -> str:
    # Deterministic timestamp derived from hash, anchored to 2026-01-01 UTC.
    digest = _stable_hash(seed)
    offset_seconds = int(digest[:8], 16) % (365 * 24 * 60 * 60)
    base_epoch = 1735689600  # 2025-01-01T00:00:00Z
    epoch = base_epoch + offset_seconds
    from datetime import datetime, timezone

    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _regression_result(trace_id: str, *, pass_result: bool) -> Dict[str, Any]:
    status = "pass" if pass_result else "fail"
    failed = 0 if pass_result else 1
    passed = 1 if pass_result else 0
    return {
        "blocked": not pass_result,
        "regression_status": status,
        "schema_version": "1.1.0",
        "artifact_type": "regression_result",
        "run_id": "reg-run-001",
        "suite_id": "suite-001",
        "created_at": "2026-03-28T00:00:00Z",
        "total_traces": 1,
        "passed_traces": passed,
        "failed_traces": failed,
        "pass_rate": float(passed),
        "overall_status": status,
        "results": [
            {
                "trace_id": trace_id,
                "replay_result_id": "replay-001",
                "analysis_id": "analysis-001",
                "decision_status": "consistent" if pass_result else "drifted",
                "reproducibility_score": 1.0 if pass_result else 0.0,
                "drift_type": "",
                "passed": pass_result,
                "failure_reasons": [] if pass_result else ["deterministic_mismatch"],
                "baseline_replay_result_id": "base-001",
                "current_replay_result_id": "cur-001",
                "baseline_trace_id": trace_id,
                "current_trace_id": trace_id,
                "baseline_reference": "replay_result:base-001",
                "current_reference": "replay_result:cur-001",
                "mismatch_summary": [] if pass_result else [{"field": "consistency_status", "baseline_value": "match", "current_value": "mismatch"}],
                "comparison_digest": "a" * 64,
            }
        ],
        "summary": {"drift_counts": {}, "average_reproducibility_score": 1.0 if pass_result else 0.0},
    }


def _budget_decision_from_control(control: Dict[str, Any], *, summary_id: str = "ems-001") -> Dict[str, Any]:
    decision = _clone(load_example("evaluation_budget_decision"))
    decision["decision_id"] = str(control.get("decision_id") or decision.get("decision_id") or "budget-decision-example-001")
    decision["summary_id"] = summary_id
    decision["trace_id"] = str(control.get("trace_id") or decision.get("trace_id") or "trace-001")
    system_response = str(control.get("system_response") or "block")
    if system_response not in {"allow", "warn", "freeze", "block"}:
        system_response = "block"
    decision["system_response"] = system_response
    decision["decision_dialect"] = "control_loop"
    decision["status"] = str(control.get("system_status") or decision.get("status") or "warning")
    if decision["status"] not in {"healthy", "warning", "exhausted", "blocked"}:
        decision["status"] = "blocked"
    decision["reasons"] = [str(control.get("rationale_code") or "simulation_bridge")]
    return decision


def _write_json(path: Path, payload: Dict[str, Any]) -> str:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(path)


def _base_artifacts() -> Dict[str, Any]:
    replay = _clone(load_example("replay_result"))
    canonical_trace_id = "44444444-4444-4444-8444-444444444444"
    replay["trace_id"] = canonical_trace_id
    replay["consistency_status"] = "match"
    replay["drift_detected"] = False
    replay["failure_reason"] = None
    run_id = str(replay.get("replay_run_id") or replay.get("original_run_id") or "eval-run-001")
    replay["replay_run_id"] = run_id
    replay["original_run_id"] = run_id

    trace_id = replay["trace_id"]
    replay["provenance"]["trace_id"] = trace_id
    replay["observability_metrics"]["trace_refs"]["trace_id"] = trace_id
    replay["error_budget_status"]["trace_refs"]["trace_id"] = trace_id

    control = _clone(load_example("evaluation_control_decision"))
    control["trace_id"] = trace_id
    control["run_id"] = run_id
    control["system_status"] = "healthy"
    control["system_response"] = "allow"
    control["decision"] = "allow"

    error_budget = _clone(load_example("error_budget_status"))
    error_budget["trace_refs"]["trace_id"] = trace_id
    error_budget["budget_status"] = "healthy"

    cert_pack = _clone(load_example("control_loop_certification_pack"))
    cert_pack["run_id"] = run_id
    cert_pack["decision"] = "pass"
    cert_pack["certification_status"] = "certified"
    cert_pack["provenance_trace_refs"]["trace_refs"] = [trace_id]

    failure_injection = _clone(load_example("governed_failure_injection_summary"))
    failure_injection["trace_refs"]["primary"] = trace_id
    failure_injection["trace_refs"]["related"] = []
    failure_injection["fail_count"] = 0
    failure_injection["pass_count"] = int(failure_injection.get("case_count") or 0)
    for result in failure_injection.get("results") or []:
        result["trace_refs"]["primary"] = trace_id
        result["trace_refs"]["related"] = []
        result["passed"] = True
        result["expected_outcome"] = "block"
        result["observed_outcome"] = "block"
        result["invariant_violations"] = []

    regression = _regression_result(trace_id, pass_result=True)
    regression["run_id"] = run_id

    return {
        "replay": replay,
        "control": control,
        "error_budget": error_budget,
        "cert_pack": cert_pack,
        "failure_injection": failure_injection,
        "regression": regression,
        "trace_id": trace_id,
    }


def _run_done_and_enforcement(
    *,
    replay: Dict[str, Any],
    regression: Dict[str, Any],
    cert_pack: Dict[str, Any],
    error_budget: Dict[str, Any],
    policy_control: Dict[str, Any],
    failure_injection: Dict[str, Any] | None,
    budget_decision: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    with TemporaryDirectory(prefix="val08-") as tmpdir:
        tmp = Path(tmpdir)
        refs = {
            "replay_result_ref": _write_json(tmp / "replay.json", replay),
            "regression_result_ref": _write_json(tmp / "regression.json", regression),
            "certification_pack_ref": _write_json(tmp / "cert_pack.json", cert_pack),
            "error_budget_ref": _write_json(tmp / "error_budget.json", error_budget),
            "policy_ref": _write_json(tmp / "policy.json", policy_control),
        }
        if failure_injection is not None:
            refs["failure_injection_ref"] = _write_json(tmp / "failure_injection.json", failure_injection)

        certification = run_done_certification(refs)
        cert_path = _write_json(tmp / "done_certification.json", certification)
        decision_path = _write_json(tmp / "evaluation_budget_decision.json", budget_decision)

        enforcement = run_enforcement_bridge(
            decision_path,
            context={
                "enforcement_scope": "promotion",
                "done_certification_path": cert_path,
            },
        )
    return certification, enforcement


def _run_xrun_and_backtest(base: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    trace_id = base["trace_id"]
    eval_summary = _clone(load_example("eval_summary"))
    eval_summary["trace_id"] = trace_id
    eval_summary["failure_rate"] = 0.45
    eval_summary["drift_rate"] = 0.22
    eval_summary["reproducibility_score"] = 0.5
    eval_summary["system_status"] = "degraded"
    eval_summary_2 = _clone(eval_summary)
    eval_summary_2["eval_run_id"] = "eval-run-20260321T120500Z"
    eval_summary_2["failure_rate"] = 0.5
    eval_summary_2["drift_rate"] = 0.3
    eval_summary_2["reproducibility_score"] = 0.4

    drift_result = _clone(load_example("drift_detection_result"))
    drift_result["trace_refs"]["trace_id"] = trace_id
    drift_result["drift_status"] = "exceeds_threshold"

    monitor_record = _clone(load_example("evaluation_monitor_record"))

    xrun_payload = {
        "replay_results": [base["replay"], _clone(base["replay"])],
        "eval_summaries": [eval_summary, eval_summary_2],
        "regression_results": [_regression_result(trace_id, pass_result=False)],
        "drift_results": [drift_result],
        "monitor_records": [monitor_record],
        "policy_ref": {
            "policy_id": "xrun-policy-001",
            "policy_version": "2.0.0",
        },
    }
    xrun_result = run_cross_run_intelligence(xrun_payload)

    backtest_result = run_policy_backtest(
        {
            "replay_results": [base["replay"]],
            "eval_summaries": [eval_summary],
            "error_budget_statuses": [base["error_budget"]],
            "cross_run_intelligence_decisions": [xrun_result["cross_run_intelligence_decision"]],
            "baseline_policy_ref": {
                "policy_id": "baseline-policy",
                "policy_version": "1.0.0",
                "thresholds": {"reliability_threshold": 0.99, "drift_threshold": 0.01, "trust_threshold": 0.99},
            },
            "candidate_policy_ref": {
                "policy_id": "candidate-policy",
                "policy_version": "1.1.0",
                "thresholds": {"reliability_threshold": 0.1, "drift_threshold": 1.0, "trust_threshold": 0.1},
            },
        }
    )
    return xrun_result["cross_run_intelligence_decision"], backtest_result


def _execute_case(case_id: str, case_type: str, injected_faults: List[str], expected_outcome: str, input_refs: Dict[str, Any]) -> Dict[str, Any]:
    base = _base_artifacts()
    failure_artifact_refs: List[str] = []
    control_decision_ref = ""
    enforcement_action_ref = ""
    actual_outcome = ""
    blocked = False
    divergence_reason = ""
    policy_reject = False

    if case_type == "context_downstream_failure":
        admission = run_context_admission(context_bundle=None, stage="observe")
        decision = admission["context_admission_decision"]
        blocked = decision.get("decision_status") == "block"
        actual_outcome = "blocked_before_downstream_promotion" if blocked else "unexpected_allow"
        failure_artifact_refs = [f"context_admission_decision:{decision.get('admission_decision_id', 'missing')}"]
        control_decision_ref = failure_artifact_refs[0]
        enforcement_action_ref = ""

    elif case_type in {
        "replay_mismatch_certification_attempt",
        "eval_control_inconsistency_promotion_attempt",
        "error_budget_exhausted_valid_pipeline",
        "failure_injection_violation_downstream_present",
        "xrun_warning_policy_reject_certification_attempt",
        "multi_fault_combined",
    }:
        replay = _clone(base["replay"])
        regression = _clone(base["regression"])
        cert_pack = _clone(base["cert_pack"])
        error_budget = _clone(base["error_budget"])
        control = _clone(base["control"])
        failure_injection = _clone(base["failure_injection"])

        if "replay_mismatch" in injected_faults:
            replay["consistency_status"] = "mismatch"
            replay["drift_detected"] = True
            replay["failure_reason"] = None
            regression = _regression_result(base["trace_id"], pass_result=False)
            regression["run_id"] = str(replay.get("replay_run_id") or replay.get("original_run_id") or "")

        if "eval_control_inconsistency" in injected_faults:
            control["system_status"] = "blocked"
            control["system_response"] = "block"
            control["decision"] = "deny"
            control["rationale_code"] = "eval_control_inconsistency"

        if "error_budget_exhausted" in injected_faults:
            error_budget["budget_status"] = "exhausted"

        if "failure_injection_violation" in injected_faults:
            failure_injection["fail_count"] = 1
            failure_injection["pass_count"] = max(0, int(failure_injection.get("case_count") or 1) - 1)
            if failure_injection.get("results"):
                failure_injection["results"][0]["passed"] = False
                failure_injection["results"][0]["observed_outcome"] = "allow"
                failure_injection["results"][0]["expected_outcome"] = "block"
                failure_injection["results"][0]["invariant_violations"] = ["unexpected_allow_path"]

        if case_type == "xrun_warning_policy_reject_certification_attempt":
            xrun_decision, backtest = _run_xrun_and_backtest(base)
            policy_reject = str(backtest.get("recommended_action") or "") in {"reject_policy", "require_review"}
            failure_artifact_refs.extend(
                [
                    f"cross_run_intelligence_decision:{xrun_decision.get('intelligence_id', 'missing')}",
                    f"policy_backtest_result:{backtest.get('backtest_id', 'missing')}",
                ]
            )
            control = build_evaluation_control_decision(replay, thresholds={"reliability_threshold": 0.99, "drift_threshold": 0.01, "trust_threshold": 0.99})

        if case_type == "multi_fault_combined":
            gfi = run_governed_failure_injection(case_filter=["context_missing_upstream_refs", "replay_missing_trace_context"])
            failure_artifact_refs.append(f"governed_failure_injection_summary:{gfi.get('chaos_run_id', 'missing')}")

        budget_decision = _budget_decision_from_control(control)
        try:
            certification, enforcement = _run_done_and_enforcement(
                replay=replay,
                regression=regression,
                cert_pack=cert_pack,
                error_budget=error_budget,
                policy_control=control,
                failure_injection=failure_injection,
                budget_decision=budget_decision,
            )
            control_decision_ref = f"done_certification_record:{certification.get('certification_id', 'missing')}"
            enforcement_action_ref = f"evaluation_enforcement_action:{enforcement.get('action_id', 'missing')}"
            failure_artifact_refs.extend([
                f"done_certification_record:{certification.get('certification_id', 'missing')}",
                f"evaluation_enforcement_action:{enforcement.get('action_id', 'missing')}",
            ])
            blocked = (
                ((enforcement.get("allowed_to_proceed") is False) and (certification.get("final_status") == "FAILED"))
                or (case_type == "xrun_warning_policy_reject_certification_attempt" and policy_reject)
            )
            actual_outcome = "blocked_with_governed_artifacts" if blocked else "unexpected_promotion_or_allow"
        except DoneCertificationError as exc:
            blocked = True
            actual_outcome = "blocked_with_done_certification_error"
            error_ref = f"done_certification_error:{exc}"
            failure_artifact_refs.append(error_ref)
            control_decision_ref = error_ref
            enforcement_action_ref = "evaluation_enforcement_action:not_executed_due_to_upstream_block"
            failure_artifact_refs.append(enforcement_action_ref)
            divergence_reason = str(exc)

    else:
        raise EndToEndFailureSimulationError(f"unsupported case_type: {case_type}")

    expected_block = True
    silent_propagation = expected_block and not blocked
    missing_failure_artifact = expected_block and len(failure_artifact_refs) == 0
    missing_enforcement = expected_block and case_type != "context_downstream_failure" and not enforcement_action_ref

    passed = not (silent_propagation or missing_failure_artifact or missing_enforcement)
    if not passed and not divergence_reason:
        reasons: List[str] = []
        if silent_propagation:
            reasons.append("silent_propagation_detected")
        if missing_failure_artifact:
            reasons.append("missing_failure_artifact")
        if missing_enforcement:
            reasons.append("missing_control_or_enforcement_consequence")
        divergence_reason = ";".join(reasons)

    if bool(input_refs.get("inject_silent_propagation_for_testing")) and case_id == "VAL08-G":
        blocked = False
        passed = False
        divergence_reason = "silent_propagation_detected"
    if bool(input_refs.get("inject_missing_failure_artifact_for_testing")) and case_id == "VAL08-F":
        failure_artifact_refs = []
        passed = False
        divergence_reason = "missing_failure_artifact"

    return {
        "case_id": case_id,
        "case_type": case_type,
        "injected_faults": injected_faults,
        "expected_outcome": expected_outcome,
        "actual_outcome": actual_outcome,
        "blocked": blocked,
        "failure_artifact_refs": sorted(set(failure_artifact_refs)),
        "control_decision_ref": control_decision_ref,
        "enforcement_action_ref": enforcement_action_ref,
        "passed": passed,
        "divergence_reason": divergence_reason,
    }


def run_end_to_end_failure_simulation(input_refs: dict) -> dict:
    """Run VAL-08 deterministic multi-layer fault simulation matrix."""
    if not isinstance(input_refs, dict):
        raise EndToEndFailureSimulationError("input_refs must be an object")

    simulation_cases = [
        _execute_case(case_id, case_type, injected_faults, expected_outcome, input_refs)
        for case_id, case_type, injected_faults, expected_outcome in _CASE_SPECS
    ]

    total_cases = len(simulation_cases)
    passed_cases = sum(1 for case in simulation_cases if case["passed"])
    failed_cases = total_cases - passed_cases

    silent_propagation_detected = any(case["blocked"] is False for case in simulation_cases)
    missing_failure_artifact_detected = any(len(case["failure_artifact_refs"]) == 0 for case in simulation_cases)
    end_to_end_block_failure_detected = any(
        (not case["blocked"]) or (case["case_type"] != "context_downstream_failure" and not case["enforcement_action_ref"])
        for case in simulation_cases
    )

    trace_ids = sorted(
        {
            str(input_refs.get("trace_id") or "")
        }
        | {"trace-001"}
    )
    trace_ids = [value for value in trace_ids if value]

    run_identity = {
        "input_refs": input_refs,
        "case_outcomes": [
            {
                "case_id": case["case_id"],
                "blocked": case["blocked"],
                "passed": case["passed"],
            }
            for case in simulation_cases
        ],
    }

    result = {
        "simulation_run_id": _stable_id("VAL08", run_identity),
        "timestamp": _deterministic_timestamp(run_identity),
        "input_refs": {key: str(value) for key, value in input_refs.items() if key.endswith("_ref")},
        "simulation_cases": simulation_cases,
        "summary": {
            "total_cases": total_cases,
            "passed_cases": passed_cases,
            "failed_cases": failed_cases,
            "silent_propagation_detected": silent_propagation_detected,
            "missing_failure_artifact_detected": missing_failure_artifact_detected,
            "end_to_end_block_failure_detected": end_to_end_block_failure_detected,
        },
        "final_status": (
            "FAILED"
            if failed_cases > 0
            or silent_propagation_detected
            or missing_failure_artifact_detected
            or end_to_end_block_failure_detected
            else "PASSED"
        ),
        "trace_ids": trace_ids or ["trace-unknown"],
    }

    validate_artifact(result, "end_to_end_failure_simulation_result")
    return result


__all__ = [
    "EndToEndFailureSimulationError",
    "run_end_to_end_failure_simulation",
]
