"""VAL-07 eval auto-generation quality validation over the real generation seam."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.cross_run_intelligence import (
    CrossRunIntelligenceError,
    run_cross_run_intelligence,
)
from spectrum_systems.modules.runtime.evaluation_auto_generation import (
    EvalCaseGenerationError,
    generate_eval_cases_from_cross_run_intelligence,
)


class EvalAutoGenerationQualityError(ValueError):
    """Raised when VAL-07 inputs are malformed or insufficient."""


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


def _stable_id(prefix: str, payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


def _deterministic_timestamp(seed_payload: Dict[str, Any]) -> str:
    canonical = json.dumps(seed_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    offset_seconds = int(digest[:8], 16) % (365 * 24 * 60 * 60)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_list_of_objects(input_refs: Dict[str, Any], field: str) -> List[Dict[str, Any]]:
    value = input_refs.get(field)
    if not isinstance(value, list) or not value:
        raise EvalAutoGenerationQualityError(f"{field} must be a non-empty list")
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise EvalAutoGenerationQualityError(f"{field}[{idx}] must be an object")
        out.append(_clone(item))
    return out


def _require_policy_ref(input_refs: Dict[str, Any]) -> Dict[str, Any]:
    value = input_refs.get("policy_ref")
    if not isinstance(value, dict):
        raise EvalAutoGenerationQualityError("policy_ref must be an object")
    if not str(value.get("policy_version") or "").strip():
        raise EvalAutoGenerationQualityError("policy_ref.policy_version must be a non-empty string")
    return _clone(value)


def _load_optional_list(input_refs: Dict[str, Any], field: str) -> List[Dict[str, Any]]:
    value = input_refs.get(field)
    if value is None:
        return []
    if not isinstance(value, list):
        raise EvalAutoGenerationQualityError(f"{field} must be a list when provided")
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise EvalAutoGenerationQualityError(f"{field}[{idx}] must be an object")
        out.append(_clone(item))
    return out


def _base_inputs(input_refs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    if not isinstance(input_refs, dict):
        raise EvalAutoGenerationQualityError("input_refs must be an object")

    base = {
        "replay_results": _require_list_of_objects(input_refs, "replay_results"),
        "eval_summaries": _require_list_of_objects(input_refs, "eval_summaries"),
        "regression_results": _require_list_of_objects(input_refs, "regression_results"),
        "drift_results": _require_list_of_objects(input_refs, "drift_results"),
        "monitor_records": _require_list_of_objects(input_refs, "monitor_records"),
        "policy_ref": _require_policy_ref(input_refs),
        "cross_run_intelligence_decisions": _load_optional_list(input_refs, "cross_run_intelligence_decisions"),
        "failure_injection_results": _load_optional_list(input_refs, "failure_injection_results"),
    }

    expected_outcomes = input_refs.get("expected_outcomes_ref")
    if expected_outcomes is None:
        expected_outcomes = {}
    if not isinstance(expected_outcomes, dict):
        raise EvalAutoGenerationQualityError("expected_outcomes_ref must be an object when provided")

    expected_ref = str(input_refs.get("expected_outcomes_ref_path") or "").strip()

    for idx, summary in enumerate(base["eval_summaries"]):
        try:
            validate_artifact(summary, "eval_summary")
        except Exception as exc:
            raise EvalAutoGenerationQualityError(f"eval_summaries[{idx}] is invalid: {exc}") from exc
    for idx, drift in enumerate(base["drift_results"]):
        try:
            validate_artifact(drift, "drift_detection_result")
        except Exception as exc:
            raise EvalAutoGenerationQualityError(f"drift_results[{idx}] is invalid: {exc}") from exc
    for idx, monitor in enumerate(base["monitor_records"]):
        try:
            validate_artifact(monitor, "evaluation_monitor_record")
        except Exception as exc:
            raise EvalAutoGenerationQualityError(f"monitor_records[{idx}] is invalid: {exc}") from exc

    return base, _clone(expected_outcomes), expected_ref


def _expected_override(expected_outcomes: Dict[str, Any], case_id: str, key: str, default: Any) -> Any:
    case_payload = expected_outcomes.get(case_id)
    if isinstance(case_payload, dict) and key in case_payload:
        return _clone(case_payload[key])
    return _clone(default)


def _build_case_payload(base: Dict[str, Any], case_id: str) -> Dict[str, Any]:
    payload = {
        "replay_results": _clone(base["replay_results"]),
        "eval_summaries": _clone(base["eval_summaries"]),
        "regression_results": _clone(base["regression_results"]),
        "drift_results": _clone(base["drift_results"]),
        "monitor_records": _clone(base["monitor_records"]),
        "policy_ref": _clone(base["policy_ref"]),
    }

    if case_id == "VAL07-A":
        payload["eval_summaries"][0]["failure_rate"] = 0.10
        payload["eval_summaries"][0]["pass_rate"] = 0.90
        payload["eval_summaries"][-1]["failure_rate"] = 0.35
        payload["eval_summaries"][-1]["pass_rate"] = 0.65
        return payload

    if case_id == "VAL07-B":
        payload["eval_summaries"][0]["drift_rate"] = 0.05
        payload["eval_summaries"][-1]["drift_rate"] = 0.40
        return payload

    if case_id == "VAL07-C":
        for regression in payload["regression_results"]:
            results = regression.get("results")
            if isinstance(results, list):
                mismatch_target = max(1, int(len(results) * 0.5))
                for idx, result in enumerate(results):
                    if isinstance(result, dict):
                        result["mismatch_summary"] = [{"field": "replay_final_status"}] if idx < mismatch_target else []
        return payload

    if case_id == "VAL07-D":
        return payload

    if case_id == "VAL07-E":
        payload["eval_summaries"] = [_clone(payload["eval_summaries"][0])]
        return payload

    raise EvalAutoGenerationQualityError(f"unknown case_id for seam payload generation: {case_id}")


def _is_eval_executable(eval_case: Dict[str, Any]) -> bool:
    refs = eval_case.get("input_artifact_refs")
    expected = eval_case.get("expected_output_spec")
    rubric = eval_case.get("scoring_rubric")
    if not isinstance(refs, list) or not refs:
        return False
    if not isinstance(expected, dict) or not expected:
        return False
    if not isinstance(rubric, dict) or not rubric:
        return False
    if not isinstance(eval_case.get("trace_id"), str) or not eval_case.get("trace_id"):
        return False
    if not isinstance(eval_case.get("eval_case_id"), str) or not eval_case.get("eval_case_id"):
        return False
    return True


def _is_eval_meaningful(eval_case: Dict[str, Any], expected_pattern: str) -> bool:
    refs = [str(ref) for ref in (eval_case.get("input_artifact_refs") or []) if isinstance(ref, str)]
    expected = eval_case.get("expected_output_spec") or {}
    source_signal_ref = f"pattern:{expected_pattern}"
    return source_signal_ref in refs and expected.get("must_detect_pattern") == expected_pattern


def _evaluate_generation_case(
    *,
    case_id: str,
    case_type: str,
    source_signal: str,
    payload: Dict[str, Any],
    expected_patterns: List[str],
    should_generate: bool,
) -> Tuple[Dict[str, Any], Dict[str, bool], List[Dict[str, Any]]]:
    generated_eval_cases: List[Dict[str, Any]] = []
    actual_properties: List[str] = []
    generated_eval_refs: List[str] = []
    executable = True
    meaningful = True
    blocking_reason = ""

    missed_generation = False
    malformed_generation = False
    non_executable_eval = False
    low_signal_eval = False

    try:
        output = run_cross_run_intelligence(payload)
        decision = output["cross_run_intelligence_decision"]
        actual_patterns = sorted(set(decision.get("detected_patterns") or []))
        generated_eval_cases = _clone(output.get("generated_eval_cases") or [])
        generated_eval_refs = [str(case.get("eval_case_id") or "") for case in generated_eval_cases if isinstance(case, dict)]

        if expected_patterns:
            if set(actual_patterns) & set(expected_patterns):
                actual_properties.append("pattern_detected")
            else:
                blocking_reason = "expected pattern not detected"
                meaningful = False

        if should_generate:
            if generated_eval_cases:
                actual_properties.append("eval_generated")
            else:
                missed_generation = True
                blocking_reason = "expected eval generation but none emitted"

            for idx, generated in enumerate(generated_eval_cases):
                try:
                    validate_artifact(generated, "eval_case")
                except Exception as exc:
                    malformed_generation = True
                    blocking_reason = f"generated_eval_cases[{idx}] invalid: {exc}"
                    continue

                if _is_eval_executable(generated):
                    actual_properties.append(f"eval_executable:{idx}")
                else:
                    executable = False
                    non_executable_eval = True
                    blocking_reason = f"generated_eval_cases[{idx}] is non-executable"

                if any(_is_eval_meaningful(generated, pattern) for pattern in expected_patterns):
                    actual_properties.append(f"eval_meaningful:{idx}")
                else:
                    meaningful = False
                    low_signal_eval = True
                    blocking_reason = f"generated_eval_cases[{idx}] missing source-signal relevance"
        else:
            if not generated_eval_cases:
                actual_properties.append("no_eval_spam")
            else:
                low_signal_eval = True
                meaningful = False
                blocking_reason = "unexpected eval generation for stable baseline"

    except CrossRunIntelligenceError as exc:
        executable = False
        meaningful = False
        if should_generate:
            missed_generation = True
        blocking_reason = str(exc)

    passed = not (missed_generation or malformed_generation or non_executable_eval or low_signal_eval or not meaningful)
    if not passed and not blocking_reason:
        blocking_reason = "quality criteria not satisfied"

    return (
        {
            "case_id": case_id,
            "case_type": case_type,
            "source_signal": source_signal,
            "generated_eval_refs": generated_eval_refs,
            "expected_properties": (
                ["pattern_detected", "eval_generated", "schema_valid", "traceable", "executable"]
                if should_generate
                else ["no_eval_spam", "no_low_signal_generation"]
            ),
            "actual_properties": sorted(set(actual_properties)),
            "executable": executable,
            "meaningful": meaningful,
            "passed": passed,
            "blocking_reason": blocking_reason,
        },
        {
            "missed_generation_detected": missed_generation,
            "malformed_generation_detected": malformed_generation,
            "non_executable_eval_detected": non_executable_eval,
            "low_signal_eval_detected": low_signal_eval,
        },
        generated_eval_cases,
    )


def _evaluate_direct_generation_case(
    *,
    case_id: str,
    case_type: str,
    source_signal: str,
    decision: Dict[str, Any],
    expected_pattern: str,
) -> Tuple[Dict[str, Any], Dict[str, bool], List[Dict[str, Any]]]:
    malformed_generation = False
    non_executable_eval = False
    low_signal_eval = False
    blocking_reason = ""
    actual_properties: List[str] = []
    generated_eval_refs: List[str] = []
    generated_eval_cases: List[Dict[str, Any]] = []

    try:
        generated_eval_cases = generate_eval_cases_from_cross_run_intelligence(decision)
        generated_eval_refs = [str(case.get("eval_case_id") or "") for case in generated_eval_cases if isinstance(case, dict)]
        if generated_eval_cases:
            actual_properties.append("eval_generated")
        else:
            blocking_reason = "expected eval generation but none emitted"

        for idx, generated in enumerate(generated_eval_cases):
            try:
                validate_artifact(generated, "eval_case")
            except Exception as exc:
                malformed_generation = True
                blocking_reason = f"generated_eval_cases[{idx}] invalid: {exc}"
                continue
            if _is_eval_executable(generated):
                actual_properties.append(f"eval_executable:{idx}")
            else:
                non_executable_eval = True
                blocking_reason = f"generated_eval_cases[{idx}] is non-executable"
            if _is_eval_meaningful(generated, expected_pattern):
                actual_properties.append(f"eval_meaningful:{idx}")
            else:
                low_signal_eval = True
                blocking_reason = f"generated_eval_cases[{idx}] missing source-signal relevance"
    except EvalCaseGenerationError as exc:
        malformed_generation = True
        blocking_reason = str(exc)

    passed = bool(generated_eval_cases) and not (malformed_generation or non_executable_eval or low_signal_eval)
    return (
        {
            "case_id": case_id,
            "case_type": case_type,
            "source_signal": source_signal,
            "generated_eval_refs": generated_eval_refs,
            "expected_properties": ["eval_generated", "schema_valid", "traceable", "executable"],
            "actual_properties": sorted(set(actual_properties)),
            "executable": not non_executable_eval,
            "meaningful": not low_signal_eval,
            "passed": passed,
            "blocking_reason": blocking_reason,
        },
        {
            "missed_generation_detected": not bool(generated_eval_cases),
            "malformed_generation_detected": malformed_generation,
            "non_executable_eval_detected": non_executable_eval,
            "low_signal_eval_detected": low_signal_eval,
        },
        generated_eval_cases,
    )


def _evaluate_malformed_source_input_case(base: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, bool]]:
    source_decision = None
    for candidate in base["cross_run_intelligence_decisions"]:
        if candidate.get("artifact_type") == "cross_run_intelligence_decision":
            source_decision = _clone(candidate)
            break

    if source_decision is None:
        source_decision = {
            "artifact_type": "cross_run_intelligence_decision",
            "schema_version": "2.0.0",
            "intelligence_id": "XRI-AAAAAAAAAAAA",
            "timestamp": "2026-03-28T00:00:00Z",
            "recommended_actions": ["generate_eval_cases"],
            "detected_patterns": ["recurring_failure_type"],
            "trace_ids": ["11111111-1111-4111-8111-111111111111"],
            "policy_version": str(base["policy_ref"].get("policy_version") or "2026.03.28"),
        }

    source_decision["trace_ids"] = []

    malformed_generation = False
    blocking_reason = ""
    try:
        generate_eval_cases_from_cross_run_intelligence(source_decision)
        malformed_generation = True
        blocking_reason = "malformed source decision accepted by generator"
    except EvalCaseGenerationError as exc:
        blocking_reason = str(exc)

    passed = not malformed_generation
    return (
        {
            "case_id": "VAL07-F",
            "case_type": "malformed_source_input",
            "source_signal": "malformed_cross_run_intelligence_decision",
            "generated_eval_refs": [],
            "expected_properties": ["fail_closed", "no_malformed_eval_acceptance"],
            "actual_properties": ["fail_closed"] if passed else ["malformed_accepted"],
            "executable": False,
            "meaningful": False,
            "passed": passed,
            "blocking_reason": blocking_reason,
        },
        {
            "missed_generation_detected": False,
            "malformed_generation_detected": malformed_generation,
            "non_executable_eval_detected": False,
            "low_signal_eval_detected": False,
        },
    )


def _evaluate_insufficient_input_case(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, bool]]:
    blocking_reason = ""
    try:
        run_cross_run_intelligence(payload)
        passed = False
        blocking_reason = "insufficient input accepted by cross-run seam"
    except CrossRunIntelligenceError as exc:
        passed = True
        blocking_reason = str(exc)

    return (
        {
            "case_id": "VAL07-E",
            "case_type": "insufficient_input",
            "source_signal": "xrun:insufficient_input",
            "generated_eval_refs": [],
            "expected_properties": ["fail_closed", "no_partial_generation"],
            "actual_properties": ["fail_closed"] if passed else [],
            "executable": False,
            "meaningful": False,
            "passed": passed,
            "blocking_reason": blocking_reason,
        },
        {
            "missed_generation_detected": False,
            "malformed_generation_detected": False,
            "non_executable_eval_detected": False,
            "low_signal_eval_detected": False,
        },
    )


def _evaluate_executability_case(generated_eval_cases: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, bool]]:
    non_executable = False
    malformed = False

    eval_refs: List[str] = []
    actual_properties: List[str] = []
    for idx, generated in enumerate(generated_eval_cases):
        eval_refs.append(str(generated.get("eval_case_id") or ""))
        try:
            validate_artifact(generated, "eval_case")
        except Exception:
            malformed = True
            continue
        if _is_eval_executable(generated):
            actual_properties.append(f"executable_eval:{idx}")
        else:
            non_executable = True

    if not generated_eval_cases:
        non_executable = True

    passed = not (non_executable or malformed)
    return (
        {
            "case_id": "VAL07-G",
            "case_type": "generated_eval_executability",
            "source_signal": "generated_eval_cases",
            "generated_eval_refs": eval_refs,
            "expected_properties": ["schema_valid", "executable"],
            "actual_properties": sorted(set(actual_properties)),
            "executable": passed,
            "meaningful": passed,
            "passed": passed,
            "blocking_reason": "" if passed else "generated eval contains malformed or non-executable artifact",
        },
        {
            "missed_generation_detected": not bool(generated_eval_cases),
            "malformed_generation_detected": malformed,
            "non_executable_eval_detected": non_executable,
            "low_signal_eval_detected": False,
        },
    )


def _input_refs_artifact(base: Dict[str, Any], expected_outcomes_ref: str = "") -> Dict[str, Any]:
    refs = {
        "replay_results": [str(i.get("replay_id") or i.get("artifact_id") or "unknown") for i in base["replay_results"]],
        "eval_summaries": [str(i.get("eval_run_id") or "unknown") for i in base["eval_summaries"]],
        "regression_results": [str(i.get("run_id") or i.get("suite_id") or "unknown") for i in base["regression_results"]],
        "drift_results": [str(i.get("artifact_id") or "unknown") for i in base["drift_results"]],
        "monitor_records": [str(i.get("monitor_record_id") or i.get("record_id") or "unknown") for i in base["monitor_records"]],
        "policy_ref": str(base["policy_ref"].get("policy_id") or base["policy_ref"].get("policy_version") or "unknown"),
    }
    if base["cross_run_intelligence_decisions"]:
        refs["cross_run_intelligence_decisions"] = [
            str(i.get("intelligence_id") or i.get("decision_id") or "unknown")
            for i in base["cross_run_intelligence_decisions"]
        ]
    if base["failure_injection_results"]:
        refs["failure_injection_results"] = [
            str(i.get("id") or i.get("chaos_run_id") or "unknown")
            for i in base["failure_injection_results"]
        ]
    if expected_outcomes_ref:
        refs["expected_outcomes_ref"] = expected_outcomes_ref
    return refs


def run_eval_auto_generation_quality_validation(input_refs: dict) -> dict:
    """Run VAL-07 deterministic matrix over real eval auto-generation seam."""
    base, expected_outcomes, expected_outcomes_ref = _base_inputs(input_refs)

    validation_cases: List[Dict[str, Any]] = []
    generated_for_executability: List[Dict[str, Any]] = []

    summary_flags = {
        "non_executable_eval_detected": False,
        "low_signal_eval_detected": False,
        "missed_generation_detected": False,
        "malformed_generation_detected": False,
    }

    matrix = [
        ("VAL07-A", "repeated_failure_pattern", "xrun:recurring_failure_type", ["recurring_failure_type"], True),
        ("VAL07-D", "stable_baseline", "xrun:stable", [], False),
    ]

    for case_id, case_type, source_signal, default_patterns, should_generate in matrix:
        expected_patterns = _expected_override(expected_outcomes, case_id, "expected_patterns", default_patterns)
        case_result, flags, generated = _evaluate_generation_case(
            case_id=case_id,
            case_type=case_type,
            source_signal=source_signal,
            payload=_build_case_payload(base, case_id),
            expected_patterns=list(expected_patterns),
            should_generate=should_generate,
        )
        validation_cases.append(case_result)
        for name, value in flags.items():
            summary_flags[name] = summary_flags[name] or bool(value)
        if case_id == "VAL07-A":
            generated_for_executability = generated

    reference_trace_id = str(base["eval_summaries"][0].get("trace_id") or "")
    drift_decision = {
        "artifact_type": "cross_run_intelligence_decision",
        "schema_version": "2.0.0",
        "intelligence_id": _stable_id("XRI", {"case_id": "VAL07-B", "trace_id": reference_trace_id}),
        "timestamp": str(base["eval_summaries"][-1].get("timestamp") or base["monitor_records"][-1].get("created_at") or "2026-03-28T00:00:00Z"),
        "input_refs": _input_refs_artifact(base),
        "aggregated_metrics": {
            "failure_rate_trend": 0.0,
            "drift_trend": 0.35,
            "regression_density": 0.1,
            "reproducibility_variance": 0.01,
        },
        "detected_patterns": ["drift_cluster"],
        "recommended_actions": ["generate_eval_cases", "tighten_policy_threshold", "trigger_drift_alert"],
        "system_signal": "warning",
        "trace_ids": [reference_trace_id],
        "policy_version": str(base["policy_ref"]["policy_version"]),
    }
    case_b_result, case_b_flags, _ = _evaluate_direct_generation_case(
        case_id="VAL07-B",
        case_type="drift_related_pattern",
        source_signal="xrun:drift_cluster",
        decision=drift_decision,
        expected_pattern="drift_cluster",
    )
    validation_cases.append(case_b_result)
    for name, value in case_b_flags.items():
        summary_flags[name] = summary_flags[name] or bool(value)

    regression_decision = {
        "artifact_type": "cross_run_intelligence_decision",
        "schema_version": "2.0.0",
        "intelligence_id": _stable_id("XRI", {"case_id": "VAL07-C", "trace_id": reference_trace_id}),
        "timestamp": str(base["eval_summaries"][-1].get("timestamp") or base["monitor_records"][-1].get("created_at") or "2026-03-28T00:00:00Z"),
        "input_refs": _input_refs_artifact(base),
        "aggregated_metrics": {
            "failure_rate_trend": 0.0,
            "drift_trend": 0.0,
            "regression_density": 0.5,
            "reproducibility_variance": 0.1,
        },
        "detected_patterns": ["unstable_module"],
        "recommended_actions": ["generate_eval_cases", "require_manual_review"],
        "system_signal": "unstable",
        "trace_ids": [reference_trace_id],
        "policy_version": str(base["policy_ref"]["policy_version"]),
    }
    case_c_result, case_c_flags, _ = _evaluate_direct_generation_case(
        case_id="VAL07-C",
        case_type="regression_density_pattern",
        source_signal="xrun:unstable_module",
        decision=regression_decision,
        expected_pattern="unstable_module",
    )
    validation_cases.append(case_c_result)
    for name, value in case_c_flags.items():
        summary_flags[name] = summary_flags[name] or bool(value)

    insufficient_case_result, insufficient_flags = _evaluate_insufficient_input_case(
        _build_case_payload(base, "VAL07-E")
    )
    validation_cases.append(insufficient_case_result)
    for name, value in insufficient_flags.items():
        summary_flags[name] = summary_flags[name] or bool(value)

    malformed_case_result, malformed_flags = _evaluate_malformed_source_input_case(base)
    validation_cases.append(malformed_case_result)
    for name, value in malformed_flags.items():
        summary_flags[name] = summary_flags[name] or bool(value)

    executability_case_result, executability_flags = _evaluate_executability_case(generated_for_executability)
    validation_cases.append(executability_case_result)
    for name, value in executability_flags.items():
        summary_flags[name] = summary_flags[name] or bool(value)

    total_cases = len(validation_cases)
    passed_cases = sum(1 for case in validation_cases if case["passed"])
    failed_cases = total_cases - passed_cases

    trace_ids: List[str] = []
    for summary in base["eval_summaries"]:
        trace_id = summary.get("trace_id")
        if isinstance(trace_id, str) and trace_id and trace_id not in trace_ids:
            trace_ids.append(trace_id)

    identity_payload = {
        "input_refs": _input_refs_artifact(base, expected_outcomes_ref),
        "validation_cases": validation_cases,
    }

    result = {
        "artifact_type": "eval_auto_generation_quality_result",
        "schema_version": "1.0.0",
        "validation_run_id": _stable_id("EAGQ", identity_payload),
        "timestamp": _deterministic_timestamp(identity_payload),
        "input_refs": _input_refs_artifact(base, expected_outcomes_ref),
        "validation_cases": validation_cases,
        "summary": {
            "total_cases": total_cases,
            "passed_cases": passed_cases,
            "failed_cases": failed_cases,
            "non_executable_eval_detected": summary_flags["non_executable_eval_detected"],
            "low_signal_eval_detected": summary_flags["low_signal_eval_detected"],
            "missed_generation_detected": summary_flags["missed_generation_detected"],
            "malformed_generation_detected": summary_flags["malformed_generation_detected"],
        },
        "final_status": "PASSED" if failed_cases == 0 else "FAILED",
        "trace_ids": trace_ids,
    }

    validate_artifact(result, "eval_auto_generation_quality_result")
    return result
