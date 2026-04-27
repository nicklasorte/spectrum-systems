"""OBS: 5-step failure trace surface (NX-13).

Builds a deterministic 5-step view across the canonical loop:

  1. execution record       — what was executed (PQX)
  2. output artifact        — what was produced
  3. eval result/summary    — how it was evaluated (EVL)
  4. control decision       — what was decided (CDE / TPA)
  5. enforcement action     — what was enforced (SEL)

The output is both machine-readable (a structured dict) and human-readable
(a multi-line text rendering). Missing inputs produce a clear, fail-closed
``stage_status`` of ``"missing"`` for that step rather than silent gaps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


CANONICAL_STAGES = (
    "execution",
    "output",
    "eval",
    "control",
    "enforcement",
)

OWNING_SYSTEM_BY_STAGE = {
    "execution": "PQX",
    "output": "PQX",
    "eval": "EVL",
    "control": "CDE",
    "enforcement": "SEL",
}


class FailureTraceError(ValueError):
    """Raised when a failure trace cannot be deterministically constructed."""


@dataclass
class FailureTraceStep:
    stage: str
    owning_system: str
    artifact_id: Optional[str]
    artifact_type: Optional[str]
    status: str  # "ok" | "fail" | "missing" | "skipped"
    reason_code: Optional[str]
    summary: str
    next_recommended_action: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


def _safe_get(d: Optional[Mapping[str, Any]], *keys: str) -> Optional[Any]:
    if not isinstance(d, Mapping):
        return None
    cur: Any = d
    for key in keys:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(key)
        if cur is None:
            return None
    return cur


def _step_from_execution(record: Optional[Mapping[str, Any]]) -> FailureTraceStep:
    if not record:
        return FailureTraceStep(
            stage="execution",
            owning_system="PQX",
            artifact_id=None,
            artifact_type=None,
            status="missing",
            reason_code="OBS_MISSING_EXECUTION_RECORD",
            summary="No execution record found.",
            next_recommended_action="Re-run PQX with admission lineage and capture an execution record.",
        )
    artifact_id = record.get("artifact_id") or record.get("execution_id") or record.get("run_id")
    raw_status = str(record.get("status") or record.get("execution_status") or "").lower()
    failed = raw_status in {"error", "failed", "fail", "blocked"}
    status = "fail" if failed else ("ok" if raw_status in {"ok", "success", "succeeded"} else raw_status or "ok")
    reason_code = str(record.get("reason_code") or record.get("error_code") or "")
    summary = str(record.get("summary") or record.get("error_message") or "")
    if not summary:
        summary = "execution succeeded" if status == "ok" else "execution failed"
    return FailureTraceStep(
        stage="execution",
        owning_system="PQX",
        artifact_id=str(artifact_id) if artifact_id else None,
        artifact_type=str(record.get("artifact_type") or "execution_record"),
        status=status,
        reason_code=reason_code or None,
        summary=summary,
        next_recommended_action=(
            "Inspect PQX execution log, capture failure_diagnosis_record." if failed else None
        ),
    )


def _step_from_output(artifact: Optional[Mapping[str, Any]]) -> FailureTraceStep:
    if not artifact:
        return FailureTraceStep(
            stage="output",
            owning_system="PQX",
            artifact_id=None,
            artifact_type=None,
            status="missing",
            reason_code="OBS_MISSING_OUTPUT_ARTIFACT",
            summary="No output artifact found.",
            next_recommended_action="Confirm PQX emitted a downstream artifact and registered its lineage.",
        )
    artifact_id = artifact.get("artifact_id") or artifact.get("id")
    artifact_type = artifact.get("artifact_type")
    return FailureTraceStep(
        stage="output",
        owning_system="PQX",
        artifact_id=str(artifact_id) if artifact_id else None,
        artifact_type=str(artifact_type) if artifact_type else None,
        status="ok" if artifact_id else "fail",
        reason_code=None if artifact_id else "OBS_MISSING_OUTPUT_ARTIFACT_ID",
        summary=f"output artifact {artifact_type or 'unknown'} present"
        if artifact_id
        else "output artifact missing identifier",
    )


def _step_from_eval(result: Optional[Mapping[str, Any]]) -> FailureTraceStep:
    if not result:
        return FailureTraceStep(
            stage="eval",
            owning_system="EVL",
            artifact_id=None,
            artifact_type=None,
            status="missing",
            reason_code="OBS_MISSING_EVAL_RESULT",
            summary="No eval result/summary found.",
            next_recommended_action="Run required evals and produce eval_slice_summary.",
        )
    artifact_id = (
        result.get("artifact_id")
        or result.get("coverage_run_id")
        or result.get("slice_id")
        or result.get("eval_run_id")
    )
    raw_status = str(
        result.get("status")
        or result.get("coverage_completeness_status")
        or result.get("result_status")
        or ""
    ).lower()
    fail_status = raw_status in {"blocked", "fail", "incomplete", "indeterminate_blocking"}
    pass_status = raw_status in {"healthy", "complete", "pass", "ok"}
    status = "fail" if fail_status else ("ok" if pass_status else raw_status or "ok")
    reason_code = str(result.get("block_reason") or result.get("reason_code") or "")
    summary = (
        f"eval status: {raw_status or 'unknown'}; "
        f"missing={result.get('missing_eval_results') or result.get('missing_eval_definitions') or []}"
    )
    return FailureTraceStep(
        stage="eval",
        owning_system="EVL",
        artifact_id=str(artifact_id) if artifact_id else None,
        artifact_type=str(result.get("artifact_type") or "eval_summary"),
        status=status,
        reason_code=reason_code or None,
        summary=summary,
        next_recommended_action=(
            "Inspect missing/indeterminate evals and remediate before promotion."
            if fail_status
            else None
        ),
    )


def _step_from_control(decision: Optional[Mapping[str, Any]]) -> FailureTraceStep:
    if not decision:
        return FailureTraceStep(
            stage="control",
            owning_system="CDE",
            artifact_id=None,
            artifact_type=None,
            status="missing",
            reason_code="OBS_MISSING_CONTROL_DECISION",
            summary="No control decision found.",
            next_recommended_action="Issue CDE control decision before promotion.",
        )
    artifact_id = decision.get("decision_id") or decision.get("artifact_id")
    raw_decision = str(decision.get("decision") or decision.get("system_response") or "").lower()
    blocked = raw_decision in {"block", "deny", "freeze"}
    status = "fail" if blocked else ("ok" if raw_decision == "allow" else raw_decision or "ok")
    reason_code = str(decision.get("reason_code") or decision.get("block_reason") or "")
    summary = f"control decision: {raw_decision or 'unknown'}; reason: {reason_code or 'none'}"
    return FailureTraceStep(
        stage="control",
        owning_system="CDE",
        artifact_id=str(artifact_id) if artifact_id else None,
        artifact_type=str(decision.get("artifact_type") or "control_decision"),
        status=status,
        reason_code=reason_code or None,
        summary=summary,
        next_recommended_action=(
            "Review TPA/EVL inputs feeding CDE and remediate the blocking reason."
            if blocked
            else None
        ),
    )


def _step_from_enforcement(action: Optional[Mapping[str, Any]]) -> FailureTraceStep:
    if not action:
        return FailureTraceStep(
            stage="enforcement",
            owning_system="SEL",
            artifact_id=None,
            artifact_type=None,
            status="missing",
            reason_code="OBS_MISSING_ENFORCEMENT_ACTION",
            summary="No enforcement action found.",
            next_recommended_action="SEL must execute an enforcement action for every CDE block.",
        )
    artifact_id = (
        action.get("enforcement_id")
        or action.get("enforcement_result_id")
        or action.get("artifact_id")
    )
    raw_action = str(
        action.get("enforcement_action") or action.get("action") or ""
    ).lower()
    blocked = raw_action in {"deny_execution", "deny", "block", "block_promotion"}
    review = raw_action in {"require_manual_review", "warn"}
    if blocked:
        status = "fail"
    elif review:
        status = "skipped"
    elif raw_action == "allow_execution":
        status = "ok"
    else:
        status = raw_action or "ok"
    reason_code = str(action.get("reason_code") or "")
    summary = f"enforcement: {raw_action or 'unknown'}; reason: {reason_code or 'none'}"
    return FailureTraceStep(
        stage="enforcement",
        owning_system="SEL",
        artifact_id=str(artifact_id) if artifact_id else None,
        artifact_type=str(action.get("artifact_type") or "enforcement_action"),
        status=status,
        reason_code=reason_code or None,
        summary=summary,
        next_recommended_action=(
            "Verify SEL enforcement matched CDE decision and remediate the cause."
            if blocked
            else None
        ),
    )


def build_failure_trace(
    *,
    execution_record: Optional[Mapping[str, Any]] = None,
    output_artifact: Optional[Mapping[str, Any]] = None,
    eval_result: Optional[Mapping[str, Any]] = None,
    control_decision: Optional[Mapping[str, Any]] = None,
    enforcement_action: Optional[Mapping[str, Any]] = None,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a 5-step failure trace dict.

    The output is shaped for both machine and human consumers. The trace is
    fail-closed: any missing step is marked ``status = "missing"`` rather than
    silently dropped.
    """
    steps: List[FailureTraceStep] = [
        _step_from_execution(execution_record),
        _step_from_output(output_artifact),
        _step_from_eval(eval_result),
        _step_from_control(control_decision),
        _step_from_enforcement(enforcement_action),
    ]

    failed_step = next((s for s in steps if s.status in {"fail", "missing"}), None)
    overall_status = "ok" if failed_step is None else "failed"
    failed_stage = failed_step.stage if failed_step else None

    summary_lines = [
        f"trace_id={trace_id or 'unknown'} overall_status={overall_status}"
    ]
    for step in steps:
        summary_lines.append(
            f"  [{step.stage:<11}] system={step.owning_system} status={step.status:<8} "
            f"id={step.artifact_id or '-'} reason={step.reason_code or '-'}"
        )
        if step.next_recommended_action:
            summary_lines.append(f"      → next: {step.next_recommended_action}")

    return {
        "artifact_type": "failure_trace",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "overall_status": overall_status,
        "failed_stage": failed_stage,
        "owning_system_for_failed_stage": (
            OWNING_SYSTEM_BY_STAGE[failed_stage] if failed_stage else None
        ),
        "primary_reason_code": failed_step.reason_code if failed_step else None,
        "next_recommended_action": (
            failed_step.next_recommended_action if failed_step else None
        ),
        "steps": [
            {
                "stage": s.stage,
                "owning_system": s.owning_system,
                "artifact_id": s.artifact_id,
                "artifact_type": s.artifact_type,
                "status": s.status,
                "reason_code": s.reason_code,
                "summary": s.summary,
                "next_recommended_action": s.next_recommended_action,
            }
            for s in steps
        ],
        "human_readable": "\n".join(summary_lines),
    }


__all__ = [
    "CANONICAL_STAGES",
    "OWNING_SYSTEM_BY_STAGE",
    "FailureTraceError",
    "FailureTraceStep",
    "build_failure_trace",
]
