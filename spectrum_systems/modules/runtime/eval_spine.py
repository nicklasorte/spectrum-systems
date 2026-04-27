"""EVL Spine — consolidated eval-loop entry point.

NX-04: This module is a thin, deterministic spine that wraps existing
evaluation runtime/governance code. It does not duplicate evaluation logic;
it exposes a small interface so the rest of the runtime has a single seam
for eval-related queries.

Contracts:
    required_eval_lookup(artifact_family, registry?) → tuple[str, ...]
    normalize_eval_result(raw_result) → dict (canonical eval_result-shaped row)
    build_eval_summary(slice_id, results) → dict (eval_slice_summary)
    normalize_failure_reason(reason) → str (canonical reason code)
    eval_to_control_signal(coverage_signal_or_enforcement) → dict (control handoff)

All functions fail closed. Missing required inputs raise ``EvalSpineError``;
they never silently downgrade to "allow".
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping, Tuple

from spectrum_systems.modules.runtime.eval_slice_summary import build_eval_slice_summary
from spectrum_systems.modules.runtime.required_eval_coverage import (
    RequiredEvalCoverageError,
    enforce_required_eval_coverage,
    load_required_eval_registry,
)


class EvalSpineError(ValueError):
    """Raised when the consolidated spine cannot deterministically resolve an eval signal."""


_CANONICAL_FAILURE_REASONS = {
    "missing_required_eval_definition",
    "missing_required_eval_result",
    "missing_required_eval_mapping",
    "indeterminate_required_eval",
    "required_eval_failed",
    "schema_validation_failed",
    "weak_evidence_coverage",
    "contradiction_signal",
    "policy_mismatch",
    "none",
}

_REASON_ALIASES = {
    "missing_definition": "missing_required_eval_definition",
    "missing_result": "missing_required_eval_result",
    "missing_mapping": "missing_required_eval_mapping",
    "indeterminate_result": "indeterminate_required_eval",
    "failed_required_eval": "required_eval_failed",
    "schema_invalid": "schema_validation_failed",
    "evidence_thin": "weak_evidence_coverage",
    "contradiction": "contradiction_signal",
    "policy_violation": "policy_mismatch",
    "policy_drift": "policy_mismatch",
    "": "none",
}


_STATUS_PASS = "pass"
_STATUS_FAIL = "fail"
_STATUS_INDETERMINATE = "indeterminate"


def required_eval_lookup(
    *,
    artifact_family: str,
    registry: Mapping[str, Any] | None = None,
) -> Tuple[str, ...]:
    """Return the canonical required eval IDs for an artifact family.

    Wraps the existing ``required_eval_coverage`` registry loader. Returns a
    deterministic tuple in registry order; raises if the family is unknown.
    """
    if not isinstance(artifact_family, str) or not artifact_family.strip():
        raise EvalSpineError("artifact_family must be a non-empty string")

    reg: Dict[str, Any]
    if registry is None:
        try:
            reg = load_required_eval_registry()
        except RequiredEvalCoverageError as exc:
            raise EvalSpineError(f"required eval registry unavailable: {exc}") from exc
    else:
        reg = dict(registry)

    mappings = reg.get("mappings")
    if not isinstance(mappings, list):
        raise EvalSpineError("required eval registry missing 'mappings'")

    for item in mappings:
        if isinstance(item, dict) and item.get("artifact_family") == artifact_family:
            required = [
                str(entry.get("eval_id"))
                for entry in (item.get("required_evals") or [])
                if isinstance(entry, dict)
                and isinstance(entry.get("eval_id"), str)
                and entry.get("mandatory_for_progression") is True
            ]
            return tuple(sorted(set(required)))

    raise EvalSpineError(
        f"missing required eval mapping for artifact family: {artifact_family!r}"
    )


def normalize_eval_result(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """Project an arbitrary eval result row into the canonical spine shape.

    Spine row shape:
        {"eval_id": str, "passed": bool, "result_status": "pass|fail|indeterminate",
         "score": float, "failure_reason": str (canonical), "trace_id": str,
         "raw": original row}

    Indeterminate results are NOT silently treated as pass; the spine
    preserves the indeterminate status so the caller can fail closed.
    """
    if not isinstance(raw, Mapping):
        raise EvalSpineError("eval result must be a mapping")

    eval_id = raw.get("eval_id") or raw.get("eval_type")
    if not isinstance(eval_id, str) or not eval_id.strip():
        raise EvalSpineError("eval result missing eval_id")

    status = str(raw.get("result_status") or "").lower()
    passed = raw.get("passed")
    if status == "":
        if passed is True:
            status = _STATUS_PASS
        elif passed is False:
            status = _STATUS_FAIL
        elif passed is None:
            status = _STATUS_INDETERMINATE
    if status not in {_STATUS_PASS, _STATUS_FAIL, _STATUS_INDETERMINATE}:
        raise EvalSpineError(
            f"eval result has invalid result_status: {status!r} for {eval_id!r}"
        )

    if passed is None:
        passed_canonical = (status == _STATUS_PASS)
    else:
        passed_canonical = bool(passed)

    score_raw = raw.get("score")
    try:
        score = float(score_raw) if score_raw is not None else (1.0 if status == _STATUS_PASS else 0.0)
    except (TypeError, ValueError) as exc:
        raise EvalSpineError(f"eval result score is not numeric for {eval_id!r}: {exc}") from exc
    score = max(0.0, min(1.0, score))

    failure_reason = raw.get("failure_reason") or raw.get("reason_code") or ""
    canonical_reason = normalize_failure_reason(str(failure_reason)) if failure_reason else ("none" if passed_canonical else "required_eval_failed")

    trace_id = raw.get("trace_id") or ""
    return {
        "eval_id": eval_id,
        "passed": passed_canonical,
        "result_status": status,
        "score": score,
        "failure_reason": canonical_reason,
        "trace_id": str(trace_id),
        "raw": dict(raw),
    }


def build_eval_summary(
    *,
    trace_id: str,
    artifact_family: str,
    stage: str,
    required_eval_ids: Iterable[str],
    observed_eval_ids: Iterable[str],
) -> Dict[str, Any]:
    """Wrap the existing ``build_eval_slice_summary`` with stricter input checks."""
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise EvalSpineError("trace_id must be a non-empty string")
    if not isinstance(artifact_family, str) or not artifact_family.strip():
        raise EvalSpineError("artifact_family must be a non-empty string")
    if not isinstance(stage, str) or not stage.strip():
        raise EvalSpineError("stage must be a non-empty string")
    required_list = sorted({str(item).strip() for item in required_eval_ids if str(item).strip()})
    observed_list = sorted({str(item).strip() for item in observed_eval_ids if str(item).strip()})
    return build_eval_slice_summary(
        trace_id=trace_id,
        artifact_family=artifact_family,
        stage=stage,
        required_eval_ids=required_list,
        observed_eval_ids=observed_list,
    )


def normalize_failure_reason(reason: str) -> str:
    """Map a raw failure reason to a canonical reason code.

    Returns one of ``_CANONICAL_FAILURE_REASONS``. Unknown strings are mapped
    to ``"required_eval_failed"`` (fail-closed default), never silently dropped.
    """
    if not isinstance(reason, str):
        raise EvalSpineError("failure reason must be a string")
    raw = reason.strip().lower()
    if raw in _CANONICAL_FAILURE_REASONS:
        return raw
    if raw in _REASON_ALIASES:
        return _REASON_ALIASES[raw]
    # Heuristic mapping for legacy reason strings.
    if "missing" in raw and "mapping" in raw:
        return "missing_required_eval_mapping"
    if "missing" in raw and "definition" in raw:
        return "missing_required_eval_definition"
    if "missing" in raw and ("result" in raw or "judgment" in raw):
        return "missing_required_eval_result"
    if "indeterminate" in raw:
        return "indeterminate_required_eval"
    if "schema" in raw:
        return "schema_validation_failed"
    if "evidence" in raw and ("weak" in raw or "thin" in raw or "insuff" in raw):
        return "weak_evidence_coverage"
    if "contradict" in raw:
        return "contradiction_signal"
    if "policy" in raw and ("mismatch" in raw or "violation" in raw or "drift" in raw):
        return "policy_mismatch"
    return "required_eval_failed"


def eval_to_control_signal(handoff_input: Mapping[str, Any]) -> Dict[str, Any]:
    """Convert an eval enforcement / coverage signal into a control handoff.

    Accepts either:
      - the ``enforcement`` dict from ``enforce_required_eval_coverage``
      - the ``coverage_signal`` dict from the same function
      - any dict with a ``decision`` key

    Returns:
      {"decision": allow|warn|freeze|block,
       "reason_code": canonical_reason,
       "blocking_reasons": [str,...],
       "trace_id": str, "run_id": str,
       "source_artifact_type": str, "source_artifact_id": str}
    """
    if not isinstance(handoff_input, Mapping):
        raise EvalSpineError("eval-to-control handoff input must be a mapping")

    decision = str(handoff_input.get("decision") or handoff_input.get("coverage_status") or "").lower()
    if decision == "complete":
        decision = "allow"
    if decision not in {"allow", "warn", "freeze", "block"}:
        raise EvalSpineError(
            f"unsupported decision in eval handoff: {handoff_input.get('decision')!r}"
        )

    raw_reason = (
        handoff_input.get("reason_code")
        or handoff_input.get("block_reason")
        or ("none" if decision == "allow" else "required_eval_failed")
    )
    reason_code = normalize_failure_reason(str(raw_reason))

    blocking = handoff_input.get("blocking_reasons")
    if blocking is None:
        blocking = []
    elif isinstance(blocking, str):
        blocking = [blocking]
    elif isinstance(blocking, list):
        blocking = [str(item) for item in blocking]
    else:
        raise EvalSpineError("blocking_reasons must be list, str, or absent")

    trace = handoff_input.get("trace") if isinstance(handoff_input.get("trace"), Mapping) else {}
    trace_id = str(handoff_input.get("trace_id") or trace.get("trace_id") or "")
    run_id = str(handoff_input.get("run_id") or trace.get("run_id") or "")
    source_type = str(handoff_input.get("artifact_type") or "")
    source_id = str(
        handoff_input.get("enforcement_id")
        or handoff_input.get("signal_id")
        or handoff_input.get("coverage_registry_id")
        or ""
    )

    if decision != "allow" and not blocking:
        # Fail closed: a block decision must carry at least one reason.
        blocking = [f"decision={decision} reason={reason_code}"]

    return {
        "decision": decision,
        "reason_code": reason_code,
        "blocking_reasons": blocking,
        "trace_id": trace_id,
        "run_id": run_id,
        "source_artifact_type": source_type,
        "source_artifact_id": source_id,
    }


def evaluate_artifact_family(
    *,
    artifact_family: str,
    eval_definitions: list[str],
    eval_results: list[Dict[str, Any]],
    trace_id: str,
    run_id: str,
    created_at: str,
    registry: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Single-call seam: required_eval_lookup → enforcement → control handoff.

    Returns {"coverage_registry": ..., "coverage_signal": ...,
             "enforcement": ..., "control_handoff": ...}.
    """
    if not isinstance(eval_definitions, list):
        raise EvalSpineError("eval_definitions must be a list")
    if not isinstance(eval_results, list):
        raise EvalSpineError("eval_results must be a list")

    normalized = [normalize_eval_result(row) for row in eval_results]
    raw_for_engine = [
        {
            "eval_id": item["eval_id"],
            "passed": item["passed"] if item["result_status"] != _STATUS_INDETERMINATE else None,
            "result_status": item["result_status"],
            "failure_reason": item["failure_reason"],
        }
        for item in normalized
    ]

    try:
        result = enforce_required_eval_coverage(
            artifact_family=artifact_family,
            eval_definitions=eval_definitions,
            eval_results=raw_for_engine,
            trace_id=trace_id,
            run_id=run_id,
            created_at=created_at,
            registry=dict(registry) if registry is not None else None,
        )
    except RequiredEvalCoverageError as exc:
        raise EvalSpineError(str(exc)) from exc

    handoff = eval_to_control_signal(result["enforcement"])
    result = dict(result)
    result["control_handoff"] = handoff
    return result


__all__ = [
    "EvalSpineError",
    "build_eval_summary",
    "evaluate_artifact_family",
    "eval_to_control_signal",
    "normalize_eval_result",
    "normalize_failure_reason",
    "required_eval_lookup",
]
