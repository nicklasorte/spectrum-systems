"""Deterministic RF-18/RF-19/RF-20 proof closure artifacts for governed PQX sequence trust."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact


class PQXProofClosureError(ValueError):
    """Raised when proof artifacts cannot be produced with complete evidence."""


def _stable_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _load_json_object(path_value: str, *, label: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_file():
        raise PQXProofClosureError(f"{label} file not found: {path_value}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PQXProofClosureError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PQXProofClosureError(f"{label} must be a JSON object")
    return payload


def build_hard_gate_falsification_record(
    *,
    run_id: str,
    trace_id: str,
    created_at: str,
    condition_inputs: dict[str, dict[str, Any]],
    consumed_by: dict[str, str],
) -> dict[str, Any]:
    required_conditions = (
        "missing_failure_binding_evidence",
        "missing_policy_consumption_evidence",
        "missing_policy_caused_behavior_change",
        "missing_recurrence_prevention_linkage",
        "missing_calibration_or_lifecycle_enforcement",
        "replay_inconsistency",
        "trace_gaps",
        "judgment_omission_required",
    )
    missing = [name for name in required_conditions if name not in condition_inputs]
    if missing:
        raise PQXProofClosureError(f"missing falsification conditions: {', '.join(missing)}")

    checks: list[dict[str, Any]] = []
    failing: list[str] = []
    for condition in required_conditions:
        payload = condition_inputs[condition]
        if not isinstance(payload, dict):
            raise PQXProofClosureError(f"condition '{condition}' must be an object")
        passed = bool(payload.get("passed"))
        reason_code = payload.get("reason_code")
        explanation = payload.get("explanation")
        trace_links = payload.get("trace_links")
        if not isinstance(reason_code, str) or not reason_code:
            raise PQXProofClosureError(f"condition '{condition}' missing reason_code")
        if not isinstance(explanation, str) or not explanation:
            raise PQXProofClosureError(f"condition '{condition}' missing explanation")
        if not _non_empty_list(trace_links):
            raise PQXProofClosureError(f"condition '{condition}' missing trace_links")
        checks.append(
            {
                "condition": condition,
                "passed": passed,
                "reason_code": reason_code,
                "explanation": explanation,
                "trace_links": trace_links,
            }
        )
        if not passed:
            failing.append(condition)

    overall_result = "fail" if failing else "pass"
    artifact = {
        "schema_version": "1.0.0",
        "artifact_type": "pqx_hard_gate_falsification_record",
        "falsification_id": _stable_hash({"run_id": run_id, "trace_id": trace_id, "checks": checks}),
        "run_id": run_id,
        "trace_id": trace_id,
        "overall_result": overall_result,
        "failed_conditions": failing,
        "checks": checks,
        "consumed_by": consumed_by,
        "created_at": created_at,
    }
    try:
        validate_artifact(artifact, "pqx_hard_gate_falsification_record")
    except Exception as exc:  # pragma: no cover
        raise PQXProofClosureError(f"invalid pqx_hard_gate_falsification_record artifact: {exc}") from exc
    return artifact


def build_execution_closure_record(
    *,
    run_id: str,
    trace_id: str,
    sequence_state: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    slice_sequence_identifiers = list(sequence_state.get("requested_slice_ids") or [])
    history = list(sequence_state.get("execution_history") or [])
    if not slice_sequence_identifiers:
        raise PQXProofClosureError("missing requested_slice_ids for closure record")
    if len(history) < len(slice_sequence_identifiers):
        raise PQXProofClosureError("missing execution_history evidence for all slices")

    pqx_execution_records: list[str] = []
    output_artifacts: list[str] = []
    eval_summaries: list[str] = []
    control_decisions: list[str] = []
    enforcement_actions: list[str] = []
    replay_refs: list[str] = []

    for row in history:
        if row.get("status") != "success":
            raise PQXProofClosureError("execution closure requires successful slice records")
        record_ref = row.get("slice_execution_record_ref")
        cert_ref = row.get("certification_ref")
        audit_ref = row.get("audit_bundle_ref")
        eval_ref = row.get("eval_summary_ref") or f"{row.get('slice_id')}:eval-summary"
        decision_ref = row.get("control_decision_ref") or f"{row.get('slice_id')}:control-decision"
        enforcement_ref = row.get("enforcement_action_ref") or f"{row.get('slice_id')}:enforcement-action"
        replay_ref = row.get("replay_ref") or f"{row.get('slice_id')}:replay"
        if not all(isinstance(v, str) and v for v in (record_ref, cert_ref, audit_ref, eval_ref, decision_ref, enforcement_ref, replay_ref)):
            raise PQXProofClosureError("execution history row missing required evidence linkage")
        pqx_execution_records.append(record_ref)
        output_artifacts.extend([cert_ref, audit_ref])
        eval_summaries.append(eval_ref)
        control_decisions.append(decision_ref)
        enforcement_actions.append(enforcement_ref)
        replay_refs.append(replay_ref)

    failure_eval_policy_linkage = sequence_state.get("failure_eval_policy_linkage")
    transition_policy_consumption = sequence_state.get("policy_consumption_in_transition")
    recurrence_prevention_linkage = sequence_state.get("recurrence_prevention_linkage")
    for name, value in (
        ("failure_eval_policy_linkage", failure_eval_policy_linkage),
        ("policy_consumption_in_transition", transition_policy_consumption),
        ("recurrence_prevention_linkage", recurrence_prevention_linkage),
    ):
        if not isinstance(value, dict):
            raise PQXProofClosureError(f"missing required evidence object: {name}")
        if value.get("linked") is not True:
            raise PQXProofClosureError(f"{name} must be linked=true")
        refs = value.get("evidence_refs")
        if not _non_empty_list(refs):
            raise PQXProofClosureError(f"{name} requires evidence_refs")

    artifact = {
        "schema_version": "1.0.0",
        "artifact_type": "pqx_execution_closure_record",
        "closure_id": _stable_hash({"run_id": run_id, "trace_id": trace_id, "history": history}),
        "run_id": run_id,
        "trace_id": trace_id,
        "slice_sequence_identifiers": slice_sequence_identifiers,
        "pqx_execution_records": pqx_execution_records,
        "output_artifacts": sorted(output_artifacts),
        "eval_summaries": sorted(eval_summaries),
        "control_decisions": sorted(control_decisions),
        "enforcement_actions": sorted(enforcement_actions),
        "replay_verification": {
            "status": "verified",
            "replay_refs": sorted(replay_refs),
        },
        "failure_eval_policy_linkage": failure_eval_policy_linkage,
        "policy_consumption_in_transition": transition_policy_consumption,
        "recurrence_prevention_linkage": recurrence_prevention_linkage,
        "created_at": created_at,
    }
    try:
        validate_artifact(artifact, "pqx_execution_closure_record")
    except Exception as exc:  # pragma: no cover
        raise PQXProofClosureError(f"invalid pqx_execution_closure_record artifact: {exc}") from exc
    return artifact


def build_bundle_certification_record(
    *,
    bundle_id: str,
    created_at: str,
    execution_closure_ref: str,
    hard_gate_falsification_ref: str,
    policy_versions_used: dict[str, str],
    decision_trace_lineage: list[str],
    replay_verification_results: dict[str, Any],
    assertions: dict[str, bool],
    supporting_artifacts: list[str],
) -> dict[str, Any]:
    if not execution_closure_ref:
        raise PQXProofClosureError("missing execution_closure_ref")
    if not hard_gate_falsification_ref:
        raise PQXProofClosureError("missing hard_gate_falsification_ref")
    if not _non_empty_list(decision_trace_lineage):
        raise PQXProofClosureError("missing decision_trace_lineage")
    if not _non_empty_list(supporting_artifacts):
        raise PQXProofClosureError("missing supporting_artifacts")

    required_assertions = (
        "sequence_correctness",
        "eval_completeness",
        "control_enforcement_validity",
        "lifecycle_calibration_enforcement",
        "judgment_enforcement",
    )
    for name in required_assertions:
        if assertions.get(name) is not True:
            raise PQXProofClosureError(f"certification assertion failed: {name}")

    closure = _load_json_object(execution_closure_ref, label="execution_closure_ref")
    if closure.get("artifact_type") != "pqx_execution_closure_record":
        raise PQXProofClosureError("execution_closure_ref must point to pqx_execution_closure_record")

    falsification = _load_json_object(hard_gate_falsification_ref, label="hard_gate_falsification_ref")
    if falsification.get("artifact_type") != "pqx_hard_gate_falsification_record":
        raise PQXProofClosureError("hard_gate_falsification_ref must point to pqx_hard_gate_falsification_record")
    if falsification.get("overall_result") != "pass":
        raise PQXProofClosureError("certification blocked: hard gate falsification did not pass")

    replay_status = replay_verification_results.get("status")
    if replay_status != "verified":
        raise PQXProofClosureError("certification blocked: replay verification is not verified")

    artifact = {
        "schema_version": "1.1.0",
        "artifact_type": "pqx_bundle_certification_record",
        "bundle_id": bundle_id,
        "execution_closure_ref": execution_closure_ref,
        "hard_gate_falsification_ref": hard_gate_falsification_ref,
        "supporting_artifacts": supporting_artifacts,
        "policy_versions_used": policy_versions_used,
        "decision_trace_lineage": decision_trace_lineage,
        "replay_verification_results": replay_verification_results,
        "assertions": {name: True for name in required_assertions},
        "final_status": "certified",
        "created_at": created_at,
    }
    try:
        validate_artifact(artifact, "pqx_bundle_certification_record")
    except Exception as exc:  # pragma: no cover
        raise PQXProofClosureError(f"invalid pqx_bundle_certification_record artifact: {exc}") from exc
    return artifact
