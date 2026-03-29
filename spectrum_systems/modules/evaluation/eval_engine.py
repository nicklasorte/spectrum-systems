"""Eval Artifact Engine (BAY).

Produces governed eval_result and eval_summary artifacts from schema-governed
inputs while preserving mandatory trace linkage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.identity_enforcement import ensure_required_ids, validate_required_ids

_STATUS_PASS = "pass"
_STATUS_FAIL = "fail"
_STATUS_INDETERMINATE = "indeterminate"


def _validate_contract(instance: Dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_case_executor(eval_case: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic fallback executor based on eval_case expected_output_spec."""
    spec = eval_case.get("expected_output_spec") or {}
    forced_status = spec.get("forced_status", _STATUS_PASS)
    forced_score = float(spec.get("forced_score", 1.0 if forced_status == _STATUS_PASS else 0.0))
    failure_modes = [] if forced_status == _STATUS_PASS else ["expected_output_mismatch"]
    return ensure_required_ids({
        "result_status": forced_status,
        "score": max(0.0, min(1.0, forced_score)),
        "failure_modes": failure_modes,
        "provenance_refs": [f"trace://{eval_case['trace_id']}"],
    }, run_id=str(eval_case.get("run_id") or ""), trace_id=str(eval_case.get("trace_id") or ""))


def run_eval_case(
    eval_case: Dict[str, Any],
    executor: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run one eval_case and produce a governed eval_result artifact.

    Enforces: indeterminate outcomes are treated as failures.
    """
    validate_required_ids(eval_case)
    _validate_contract(eval_case, "eval_case")

    runner = executor or _default_case_executor
    raw = runner(eval_case)

    result_status = raw.get("result_status", _STATUS_INDETERMINATE)
    failure_modes = list(raw.get("failure_modes") or [])
    if result_status == _STATUS_INDETERMINATE:
        result_status = _STATUS_FAIL
        failure_modes.append("indeterminate_treated_as_failure")

    result = ensure_required_ids({
        "artifact_type": "eval_result",
        "schema_version": "1.0.0",
        "eval_case_id": eval_case["eval_case_id"],
        "run_id": str(raw.get("run_id") or eval_case.get("run_id") or ""),
        "trace_id": str(raw.get("trace_id") or eval_case["trace_id"]),
        "result_status": result_status,
        "score": float(raw.get("score", 0.0)),
        "failure_modes": failure_modes,
        "provenance_refs": list(raw.get("provenance_refs") or [f"trace://{eval_case['trace_id']}"]),
    }, run_id=str(raw.get("run_id") or eval_case.get("run_id") or ""), trace_id=str(raw.get("trace_id") or eval_case["trace_id"]))

    if not result["eval_case_id"] or not result["trace_id"] or not result["run_id"]:
        raise ValueError("run_eval_case: eval_result requires eval_case_id, run_id, and trace_id")

    _validate_contract(result, "eval_result")
    return result


def compute_eval_summary(
    eval_run_id: str,
    trace_id: str,
    eval_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute governed eval_summary from case results."""
    total = len(eval_results)
    pass_count = sum(1 for r in eval_results if r.get("result_status") == _STATUS_PASS)
    fail_count = total - pass_count

    drift_count = sum(
        1 for r in eval_results if any("drift" in fm for fm in (r.get("failure_modes") or []))
    )
    reproducible_count = sum(
        1
        for r in eval_results
        if not any("non_reproducible" in fm for fm in (r.get("failure_modes") or []))
    )

    pass_rate = (pass_count / total) if total else 0.0
    failure_rate = (fail_count / total) if total else 1.0
    drift_rate = (drift_count / total) if total else 0.0
    reproducibility_score = (reproducible_count / total) if total else 0.0

    if failure_rate >= 0.5:
        system_status = "failing"
    elif failure_rate > 0.0 or drift_rate > 0.0:
        system_status = "degraded"
    else:
        system_status = "healthy"

    summary = {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "eval_run_id": eval_run_id,
        "pass_rate": pass_rate,
        "failure_rate": failure_rate,
        "drift_rate": drift_rate,
        "reproducibility_score": reproducibility_score,
        "system_status": system_status,
    }
    _validate_contract(summary, "eval_summary")
    return summary


def run_eval_run(
    eval_run: Dict[str, Any],
    eval_cases: List[Dict[str, Any]],
    executor: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run a governed eval_run across declared eval_case artifacts."""
    _validate_contract(eval_run, "eval_run")

    case_by_id = {c["eval_case_id"]: c for c in eval_cases}
    missing = [cid for cid in eval_run["eval_case_ids"] if cid not in case_by_id]
    if missing:
        raise ValueError(f"run_eval_run: missing eval_case definitions for ids: {missing}")

    results = [run_eval_case(case_by_id[cid], executor=executor) for cid in eval_run["eval_case_ids"]]

    summary = compute_eval_summary(
        eval_run_id=eval_run["eval_run_id"],
        trace_id=eval_run["trace_id"],
        eval_results=results,
    )

    execution_record = {
        "artifact_type": "eval_run_execution",
        "schema_version": "1.0.0",
        "trace_id": eval_run["trace_id"],
        "executed_at": _now_iso(),
        "eval_run": eval_run,
        "eval_results": results,
        "eval_summary": summary,
    }
    return execution_record
