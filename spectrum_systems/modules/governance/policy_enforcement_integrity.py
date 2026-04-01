"""VAL-10 policy enforcement integrity validation across governed seams."""

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
from spectrum_systems.modules.runtime.evaluation_budget_governor import (
    build_validation_budget_decision,
)
from spectrum_systems.modules.runtime.evaluation_control import (
    EvaluationControlError,
    build_evaluation_control_decision,
)
from spectrum_systems.modules.runtime.evaluation_enforcement_bridge import run_enforcement_bridge
from spectrum_systems.modules.runtime.policy_backtesting import run_policy_backtest
from spectrum_systems.modules.runtime.policy_registry import (
    PolicyResolutionError,
    resolve_effective_slo_policy,
    validate_slo_policy_registry,
)
from spectrum_systems.modules.runtime.routing_policy import (
    RoutingPolicyError,
    load_routing_policy,
    resolve_routing_decision,
)


class PolicyEnforcementIntegrityError(ValueError):
    """Raised when validation input refs are malformed."""


_CASE_SPECS: Tuple[Tuple[str, str, str], ...] = (
    ("VAL10-A", "missing_policy_input", "policy_registry"),
    ("VAL10-B", "malformed_policy_input", "policy_registry"),
    ("VAL10-C", "control_seam_policy_enforcement", "evaluation_control"),
    ("VAL10-D", "enforcement_seam_policy_enforcement", "evaluation_enforcement_bridge"),
    ("VAL10-E", "certification_seam_policy_enforcement", "done_certification"),
    ("VAL10-F", "backtesting_policy_identity_integrity", "policy_backtesting"),
    ("VAL10-G", "routing_adapter_policy_integrity", "routing_policy"),
    ("VAL10-H", "inconsistent_policy_application", "evaluation_control"),
)


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


def _stable_id(prefix: str, payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


def _load_json_path(path_value: str, *, label: str) -> Dict[str, Any]:
    path = Path(path_value)
    if not path.is_file():
        raise PolicyEnforcementIntegrityError(f"{label} file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PolicyEnforcementIntegrityError(f"{label} file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PolicyEnforcementIntegrityError(f"{label} must resolve to a JSON object")
    return payload


def _require_object_or_path(input_refs: Dict[str, Any], key: str, *, default: Dict[str, Any]) -> Dict[str, Any]:
    value = input_refs.get(key)
    if value is None:
        return _clone(default)
    if isinstance(value, dict):
        return _clone(value)
    if isinstance(value, str) and value.strip():
        return _load_json_path(value, label=key)
    raise PolicyEnforcementIntegrityError(f"{key} must be an object or a non-empty JSON file path")


def _default_inputs() -> Dict[str, Any]:
    trace_id = "11111111-1111-4111-8111-111111111111"
    replay = _clone(load_example("replay_result"))
    replay["trace_id"] = trace_id
    replay["timestamp"] = "2026-03-28T00:00:00Z"
    replay["replay_id"] = "replay-val10"
    replay["replay_run_id"] = "run-val10"
    replay["consistency_status"] = "match"
    replay["drift_detected"] = False
    replay["failure_reason"] = None
    replay["observability_metrics"]["trace_refs"]["trace_id"] = trace_id
    replay["error_budget_status"]["trace_refs"]["trace_id"] = trace_id
    replay["error_budget_status"]["budget_status"] = "healthy"

    eval_summary = _clone(load_example("eval_summary"))
    eval_summary["trace_id"] = trace_id
    eval_summary["eval_run_id"] = "eval-val10"

    error_budget = _clone(load_example("error_budget_status"))
    error_budget["trace_refs"]["trace_id"] = trace_id
    error_budget["budget_status"] = "healthy"

    monitor = _clone(load_example("evaluation_monitor_summary"))
    monitor["trace_id"] = trace_id
    monitor["overall_status"] = "blocked"
    monitor["generated_at"] = "2026-03-28T00:00:00Z"
    monitor.setdefault("aggregated_slis", {})["output_paths_valid_rate"] = 0.0

    control = _clone(load_example("evaluation_control_decision"))
    control["trace_id"] = trace_id
    control["system_status"] = "healthy"
    control["system_response"] = "allow"
    control["decision"] = "allow"

    certification_pack = _clone(load_example("control_loop_certification_pack"))
    certification_pack["decision"] = "pass"
    certification_pack["certification_status"] = "certified"
    certification_pack["provenance_trace_refs"]["trace_refs"] = [trace_id]

    done_cert = _clone(load_example("done_certification_record"))
    done_cert["final_status"] = "PASSED"
    done_cert["system_response"] = "allow"
    done_cert["trace_id"] = trace_id
    done_cert["input_refs"]["policy_ref"] = "policy.json"

    routing_input = {
        "routing_policy": _clone(load_example("routing_policy")),
        "prompt_registry_entries": [_clone(load_example("prompt_registry_entry"))],
        "prompt_alias_map": _clone(load_example("prompt_alias_map")),
        "route_key": "meeting_minutes_default",
        "task_class": "meeting_minutes",
    }

    policy_ref = {
        "artifact_type": "slo_policy_registry",
        "registry_version": "1.0.0",
        "contract_version": "1.0.0",
        "default_policy": "permissive",
        "policies": {
            "permissive": {
                "ti_1_0_decision": "allow",
                "ti_0_5_decision": "allow_with_warning",
                "ti_0_0_decision": "fail",
                "warnings_permitted": True,
                "degraded_lineage_allowed": True,
            },
            "decision_grade": {
                "ti_1_0_decision": "allow",
                "ti_0_5_decision": "fail",
                "ti_0_0_decision": "fail",
                "warnings_permitted": False,
                "degraded_lineage_allowed": False,
            },
            "exploratory": {
                "ti_1_0_decision": "allow",
                "ti_0_5_decision": "allow_with_warning",
                "ti_0_0_decision": "fail",
                "warnings_permitted": True,
                "degraded_lineage_allowed": True,
            },
        },
        "stage_bindings": {
            "observe": "permissive",
            "interpret": "permissive",
            "recommend": "decision_grade",
            "synthesis": "decision_grade",
            "export": "decision_grade",
        },
    }

    alternate_policy_ref = {
        "policy_id": "policy-val10-strict",
        "policy_version": "v2",
        "thresholds": {
            "reliability_threshold": 0.95,
            "drift_threshold": 0.05,
            "trust_threshold": 0.95,
        },
    }

    return {
        "policy_ref": policy_ref,
        "alternate_policy_ref": alternate_policy_ref,
        "eval_summary_ref": eval_summary,
        "error_budget_status_ref": error_budget,
        "monitor_record_ref": monitor,
        "control_decision_ref": control,
        "certification_pack_ref": certification_pack,
        "done_certification_ref": done_cert,
        "replay_result_ref": replay,
        "routing_input_ref": routing_input,
    }


def _base_inputs(input_refs: Dict[str, Any]) -> Dict[str, Any]:
    defaults = _default_inputs()
    if not isinstance(input_refs, dict):
        raise PolicyEnforcementIntegrityError("input_refs must be an object")

    return {
        "policy_ref": _require_object_or_path(input_refs, "policy_ref", default=defaults["policy_ref"]),
        "alternate_policy_ref": _require_object_or_path(
            input_refs, "alternate_policy_ref", default=defaults["alternate_policy_ref"]
        ),
        "eval_summary_ref": _require_object_or_path(input_refs, "eval_summary_ref", default=defaults["eval_summary_ref"]),
        "error_budget_status_ref": _require_object_or_path(
            input_refs, "error_budget_status_ref", default=defaults["error_budget_status_ref"]
        ),
        "monitor_record_ref": _require_object_or_path(input_refs, "monitor_record_ref", default=defaults["monitor_record_ref"]),
        "control_decision_ref": _require_object_or_path(
            input_refs, "control_decision_ref", default=defaults["control_decision_ref"]
        ),
        "certification_pack_ref": _require_object_or_path(
            input_refs, "certification_pack_ref", default=defaults["certification_pack_ref"]
        ),
        "done_certification_ref": _require_object_or_path(
            input_refs, "done_certification_ref", default=defaults["done_certification_ref"]
        ),
        "replay_result_ref": _require_object_or_path(input_refs, "replay_result_ref", default=defaults["replay_result_ref"]),
        "routing_input_ref": _require_object_or_path(input_refs, "routing_input_ref", default=defaults["routing_input_ref"]),
    }


def _write_json(path: Path, payload: Dict[str, Any]) -> str:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(path)


def _execute_case(case_id: str, case_type: str, target_seam: str, base: Dict[str, Any]) -> Dict[str, Any]:
    expected_outcome = "fail_closed"
    actual_outcome = "fail_closed"
    blocking_reason = ""
    bypass_detected = False
    policy_applied = "unknown"

    if case_type == "missing_policy_input":
        policy_applied = "missing"
        expected_outcome = "policy_resolution_error"
        try:
            resolve_effective_slo_policy(None, None)
            actual_outcome = "accepted_missing_policy"
            bypass_detected = True
            blocking_reason = "policy registry accepted missing explicit/stage policy"
        except PolicyResolutionError:
            actual_outcome = "policy_resolution_error"
    elif case_type == "malformed_policy_input":
        policy_applied = "malformed"
        expected_outcome = "registry_rejected"
        malformed = _clone(base["policy_ref"])
        malformed.pop("stage_bindings", None)
        errors = validate_slo_policy_registry(malformed)
        if errors:
            actual_outcome = "registry_rejected"
            try:
                malformed_replay = _clone(base["replay_result_ref"])
                malformed_replay.pop("trace_id", None)
                build_evaluation_control_decision(malformed_replay)
                bypass_detected = True
                blocking_reason = "control seam accepted malformed replay input"
            except EvaluationControlError:
                pass
        else:
            actual_outcome = "registry_accepted_malformed"
            bypass_detected = True
            blocking_reason = "policy registry accepted malformed policy registry payload"
    elif case_type == "control_seam_policy_enforcement":
        policy_applied = "threshold_policies"
        expected_outcome = "distinct_decisions"
        replay = _clone(base["replay_result_ref"])
        replay["consistency_status"] = "match"
        replay["drift_detected"] = False
        replay["observability_metrics"]["metrics"]["replay_success_rate"] = 0.88

        permissive = {
            "reliability_threshold": 0.80,
            "drift_threshold": 0.20,
            "trust_threshold": 0.80,
        }
        strict = _clone(base["alternate_policy_ref"]["thresholds"])

        p_decision = build_evaluation_control_decision(replay, thresholds=permissive, threshold_context="comparative_analysis")
        s_decision = build_evaluation_control_decision(replay, thresholds=strict, threshold_context="comparative_analysis")
        if p_decision["system_response"] != s_decision["system_response"]:
            actual_outcome = f"distinct:{p_decision['system_response']}->{s_decision['system_response']}"
        else:
            actual_outcome = f"same:{p_decision['system_response']}"
            bypass_detected = True
            blocking_reason = "control seam ignored threshold policy differences"
    elif case_type == "enforcement_seam_policy_enforcement":
        policy_applied = "restrictive_enforcement"
        expected_outcome = "blocked_or_frozen"
        monitor = _clone(base["monitor_record_ref"])
        monitor["overall_status"] = "blocked"
        monitor.setdefault("aggregated_slis", {})["output_paths_valid_rate"] = 0.0
        budget_decision = build_validation_budget_decision(monitor)
        with TemporaryDirectory(prefix="val10-d-") as tmp:
            decision_path = Path(tmp) / "evaluation_budget_decision.json"
            _write_json(decision_path, budget_decision)
            action = run_enforcement_bridge(str(decision_path), context={"enforcement_scope": "release"})
        if action["allowed_to_proceed"] is False and action["action_type"] in {"freeze", "block"}:
            actual_outcome = action["action_type"]
        else:
            actual_outcome = f"unexpected:{action['action_type']}"
            bypass_detected = True
            blocking_reason = "enforcement seam allowed restrictive budget decision"
    elif case_type == "certification_seam_policy_enforcement":
        policy_applied = "done_certification_policy_ref_required"
        expected_outcome = "done_certification_error"
        with TemporaryDirectory(prefix="val10-e-") as tmp:
            tmp_path = Path(tmp)
            replay = _clone(base["replay_result_ref"])
            trace_id = replay["trace_id"]
            regression = {
                "blocked": False,
                "regression_status": "pass",
                "schema_version": "1.1.0",
                "artifact_type": "regression_result",
                "run_id": "reg-val10",
                "suite_id": "suite-val10",
                "created_at": "2026-03-28T00:00:00Z",
                "total_traces": 1,
                "passed_traces": 1,
                "failed_traces": 0,
                "pass_rate": 1.0,
                "overall_status": "pass",
                "results": [
                    {
                        "trace_id": trace_id,
                        "replay_result_id": replay["replay_id"],
                        "analysis_id": "analysis-val10",
                        "decision_status": "consistent",
                        "reproducibility_score": 1.0,
                        "drift_type": "",
                        "passed": True,
                        "failure_reasons": [],
                        "baseline_replay_result_id": "base-1",
                        "current_replay_result_id": "cur-1",
                        "baseline_trace_id": trace_id,
                        "current_trace_id": trace_id,
                        "baseline_reference": "replay_result:base-1",
                        "current_reference": "replay_result:cur-1",
                        "mismatch_summary": [],
                        "comparison_digest": "a" * 64,
                    }
                ],
                "summary": {"drift_counts": {}, "average_reproducibility_score": 1.0},
            }
            budget = _clone(base["error_budget_status_ref"])
            budget["trace_refs"]["trace_id"] = trace_id
            control = _clone(base["control_decision_ref"])
            control["trace_id"] = trace_id
            control["decision"] = "allow"
            control["system_response"] = "allow"
            cert_pack = _clone(base["certification_pack_ref"])
            cert_pack["provenance_trace_refs"]["trace_refs"] = [trace_id]

            refs = {
                "replay_result_ref": _write_json(tmp_path / "replay.json", replay),
                "regression_result_ref": _write_json(tmp_path / "regression.json", regression),
                "certification_pack_ref": _write_json(tmp_path / "cert_pack.json", cert_pack),
                "error_budget_ref": _write_json(tmp_path / "budget.json", budget),
            }
            try:
                run_done_certification(refs)
                actual_outcome = "accepted_missing_policy_ref"
                bypass_detected = True
                blocking_reason = "done certification accepted input without policy_ref"
            except DoneCertificationError:
                actual_outcome = "done_certification_error"
    elif case_type == "backtesting_policy_identity_integrity":
        policy_applied = "baseline_vs_candidate_identity"
        expected_outcome = "distinct_policy_identities_honored"
        replay = _clone(base["replay_result_ref"])
        trace_id = replay["trace_id"]
        eval_summary = _clone(base["eval_summary_ref"])
        eval_summary["trace_id"] = trace_id
        budget = _clone(base["error_budget_status_ref"])
        budget["trace_refs"]["trace_id"] = trace_id
        xrun = {
            "artifact_type": "cross_run_intelligence_decision",
            "schema_version": "2.0.0",
            "intelligence_id": "XRI-ABCDEF123456",
            "timestamp": "2026-03-28T00:00:00Z",
            "input_refs": {
                "replay_results": [replay["replay_id"]],
                "eval_summaries": [eval_summary["eval_run_id"]],
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
            "policy_id": "policy-val10-baseline",
            "policy_version": "v1",
            "thresholds": {
                "reliability_threshold": 0.80,
                "drift_threshold": 0.20,
                "trust_threshold": 0.80,
            },
        }
        candidate = _clone(base["alternate_policy_ref"])

        replay["observability_metrics"]["metrics"]["replay_success_rate"] = 0.90

        result = run_policy_backtest(
            {
                "replay_results": [replay],
                "eval_summaries": [eval_summary],
                "error_budget_statuses": [budget],
                "cross_run_intelligence_decisions": [xrun],
                "baseline_policy_ref": baseline,
                "candidate_policy_ref": candidate,
            }
        )
        deltas = result.get("decision_deltas") or []
        has_policy_change = any(delta.get("change_type") != "no_change" for delta in deltas)
        input_refs = result.get("input_refs") or {}
        identities_preserved = (
            input_refs.get("baseline_policy_ref") == baseline["policy_id"]
            and input_refs.get("candidate_policy_ref") == candidate["policy_id"]
            and baseline["policy_id"] != candidate["policy_id"]
        )
        if has_policy_change and identities_preserved:
            actual_outcome = "distinct_policy_identities_honored"
        else:
            actual_outcome = "collapsed_policy_behavior"
            bypass_detected = True
            blocking_reason = "policy backtesting collapsed distinct policy identities or decisions"
    elif case_type == "routing_adapter_policy_integrity":
        policy_applied = "routing_policy_constraints"
        expected_outcome = "disallow_out_of_catalog_model"
        routing_input = _clone(base["routing_input_ref"])
        with TemporaryDirectory(prefix="val10-g-") as tmp:
            policy_path = Path(tmp) / "routing-policy.json"
            _write_json(policy_path, routing_input["routing_policy"])
            policy = load_routing_policy(policy_path)
            resolved = resolve_routing_decision(
                policy=policy,
                route_key=routing_input["route_key"],
                task_class=routing_input["task_class"],
                trace_id="trace-val10-route",
                agent_run_id="agent-run-val10",
                prompt_entries=routing_input["prompt_registry_entries"],
                prompt_alias_map=routing_input["prompt_alias_map"],
            )
            if not str(resolved["routing_decision"]["selected_model_id"]):
                raise PolicyEnforcementIntegrityError("routing_decision missing selected_model_id")

            bad_policy = _clone(routing_input["routing_policy"])
            bad_policy["routes"][0]["model_selection"]["selected_model_id"] = "openai:gpt-5"
            bad_policy_path = Path(tmp) / "routing-policy-bad.json"
            _write_json(bad_policy_path, bad_policy)
            try:
                load_routing_policy(bad_policy_path)
                actual_outcome = "accepted_out_of_catalog_model"
                bypass_detected = True
                blocking_reason = "routing policy accepted selected_model_id outside model_catalog"
            except RoutingPolicyError:
                actual_outcome = "disallow_out_of_catalog_model"
    elif case_type == "inconsistent_policy_application":
        policy_applied = "cross_seam_consistency"
        expected_outcome = "detect_inconsistent_policy_application"
        replay = _clone(base["replay_result_ref"])
        replay["consistency_status"] = "mismatch"
        replay["drift_detected"] = True
        replay["observability_metrics"]["metrics"]["drift_exceed_threshold_rate"] = 0.9
        control = build_evaluation_control_decision(
            replay,
            thresholds={"reliability_threshold": 0.8, "drift_threshold": 0.2, "trust_threshold": 0.8},
            threshold_context="comparative_analysis",
        )

        routing_input = _clone(base["routing_input_ref"])
        with TemporaryDirectory(prefix="val10-h-") as tmp:
            policy_path = Path(tmp) / "routing-policy.json"
            _write_json(policy_path, routing_input["routing_policy"])
            policy = load_routing_policy(policy_path)
            routing = resolve_routing_decision(
                policy=policy,
                route_key=routing_input["route_key"],
                task_class=routing_input["task_class"],
                trace_id="trace-val10-inconsistent",
                agent_run_id="agent-run-val10-inconsistent",
                prompt_entries=routing_input["prompt_registry_entries"],
                prompt_alias_map=routing_input["prompt_alias_map"],
            )

        inconsistency = control.get("system_response") in {"freeze", "block"} and bool(
            routing["routing_decision"].get("selected_model_id")
        )
        if inconsistency:
            actual_outcome = "detected_inconsistent_policy_application"
            bypass_detected = True
            blocking_reason = (
                "control seam blocks while routing seam still resolves model selection under same restrictive context"
            )
        else:
            actual_outcome = "no_inconsistency_detected"
    else:
        raise PolicyEnforcementIntegrityError(f"unsupported case_type: {case_type}")

    passed = False
    if case_type in {"missing_policy_input", "malformed_policy_input", "enforcement_seam_policy_enforcement", "certification_seam_policy_enforcement", "routing_adapter_policy_integrity", "backtesting_policy_identity_integrity", "control_seam_policy_enforcement"}:
        passed = not bypass_detected and not blocking_reason
    elif case_type == "inconsistent_policy_application":
        passed = bypass_detected

    return {
        "case_id": case_id,
        "case_type": case_type,
        "target_seam": target_seam,
        "expected_outcome": expected_outcome,
        "actual_outcome": actual_outcome,
        "policy_applied": policy_applied,
        "bypass_detected": bypass_detected,
        "passed": passed,
        "blocking_reason": blocking_reason,
    }


def _timestamp(base: Dict[str, Any]) -> str:
    for key in (
        "replay_result_ref",
        "eval_summary_ref",
        "error_budget_status_ref",
        "monitor_record_ref",
        "control_decision_ref",
    ):
        payload = base.get(key)
        if not isinstance(payload, dict):
            continue
        for field in ("timestamp", "created_at", "generated_at"):
            candidate = payload.get(field)
            if isinstance(candidate, str) and candidate:
                return candidate
    return "2026-03-28T00:00:00Z"


def _trace_ids(base: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for key in ("replay_result_ref", "eval_summary_ref", "control_decision_ref", "error_budget_status_ref"):
        payload = base.get(key)
        if not isinstance(payload, dict):
            continue
        trace_id = payload.get("trace_id")
        if isinstance(trace_id, str) and trace_id:
            values.append(trace_id)
        trace_refs = payload.get("trace_refs")
        if isinstance(trace_refs, dict):
            nested = trace_refs.get("trace_id")
            if isinstance(nested, str) and nested:
                values.append(nested)
    return sorted(set(values)) or ["trace-unknown"]


def run_policy_enforcement_integrity_validation(input_refs: dict) -> dict:
    """Run VAL-10 policy enforcement integrity matrix across real governed seams."""
    base = _base_inputs(input_refs)

    validation_cases = [
        _execute_case(case_id, case_type, seam, base)
        for case_id, case_type, seam in _CASE_SPECS
    ]

    total_cases = len(validation_cases)
    passed_cases = sum(1 for case in validation_cases if case["passed"])
    failed_cases = total_cases - passed_cases

    missing_policy_accepted = any(
        c["case_type"] == "missing_policy_input" and c["bypass_detected"] for c in validation_cases
    )
    malformed_policy_accepted = any(
        c["case_type"] == "malformed_policy_input" and c["bypass_detected"] for c in validation_cases
    )
    inconsistent_policy_application_detected = any(
        c["case_type"] == "inconsistent_policy_application" and c["bypass_detected"] for c in validation_cases
    )
    policy_bypass_detected = any(c["bypass_detected"] for c in validation_cases)

    canonical_input_refs = {
        "policy_ref": "slo_policy_registry",
        "alternate_policy_ref": str(base["alternate_policy_ref"].get("policy_id") or "policy-alt"),
        "eval_summary_ref": str(base["eval_summary_ref"].get("eval_run_id") or "eval-summary"),
        "error_budget_status_ref": str(base["error_budget_status_ref"].get("artifact_id") or "error-budget"),
        "monitor_record_ref": str(base["monitor_record_ref"].get("summary_id") or "monitor-summary"),
        "control_decision_ref": str(base["control_decision_ref"].get("decision_id") or "control-decision"),
        "certification_pack_ref": str(base["certification_pack_ref"].get("certification_pack_id") or "certification-pack"),
        "done_certification_ref": str(base["done_certification_ref"].get("certification_id") or "done-certification"),
        "replay_result_ref": str(base["replay_result_ref"].get("replay_id") or "replay-result"),
        "routing_input_ref": str((base["routing_input_ref"].get("routing_policy") or {}).get("policy_id") or "routing-policy"),
    }

    result = {
        "validation_run_id": _stable_id(
            "VAL10",
            {
                "input_refs": canonical_input_refs,
                "cases": [{"case_id": c["case_id"], "actual": c["actual_outcome"]} for c in validation_cases],
            },
        ),
        "timestamp": _timestamp(base),
        "input_refs": canonical_input_refs,
        "validation_cases": validation_cases,
        "summary": {
            "total_cases": total_cases,
            "passed_cases": passed_cases,
            "failed_cases": failed_cases,
            "policy_bypass_detected": policy_bypass_detected,
            "malformed_policy_accepted": malformed_policy_accepted,
            "missing_policy_accepted": missing_policy_accepted,
            "inconsistent_policy_application_detected": inconsistent_policy_application_detected,
        },
        "final_status": "FAILED"
        if (
            failed_cases > 0
            or policy_bypass_detected
            or malformed_policy_accepted
            or missing_policy_accepted
            or inconsistent_policy_application_detected
        )
        else "PASSED",
        "trace_ids": _trace_ids(base),
    }

    validate_artifact(result, "policy_enforcement_integrity_result")
    return result
