"""Deterministic HNX long-running continuity policy and artifact helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

_CONTEXT_STAGE_SEQUENCE = (
    "context_map",
    "context_admission",
    "context_assembly",
    "context_preflight",
    "context_checkpoint_resume",
)


def _stable_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _base_result(*, allowed: bool, state: str, reason_codes: list[str] | None = None, validation_failures: list[str] | None = None, policy_failures: list[str] | None = None) -> dict[str, Any]:
    return {
        "allowed": allowed,
        "recommended_state": state,
        "reason_codes": sorted(set(reason_codes or [])),
        "validation_failures": sorted(set(validation_failures or [])),
        "policy_failures": sorted(set(policy_failures or [])),
    }


def create_checkpoint(
    *,
    checkpoint_id: str,
    workflow_id: str,
    stage_contract_id: str,
    stage_name: str,
    stage_sequence: int,
    execution_mode: str,
    state_snapshot: Mapping[str, Any],
    execution_context: Mapping[str, Any],
    created_at: str,
    trace: Mapping[str, Any],
    provenance: Mapping[str, Any],
    parent_checkpoint_id: str | None = None,
) -> dict[str, Any]:
    artifact: dict[str, Any] = {
        "artifact_type": "checkpoint_record",
        "schema_version": "1.0.0",
        "checkpoint_id": checkpoint_id,
        "workflow_id": workflow_id,
        "stage_contract_id": stage_contract_id,
        "stage_name": stage_name,
        "stage_sequence": int(stage_sequence),
        "execution_mode": execution_mode,
        "state_snapshot": dict(state_snapshot),
        "execution_context": dict(execution_context),
        "created_at": created_at,
        "trace": dict(trace),
        "provenance": dict(provenance),
    }
    if parent_checkpoint_id:
        artifact["parent_checkpoint_id"] = parent_checkpoint_id

    content_hash = _stable_hash(artifact)
    artifact["content_hash"] = content_hash
    return {
        "artifact": artifact,
        "content_hash": content_hash,
        "result": _base_result(allowed=True, state="freeze", reason_codes=["CHECKPOINT_CREATED"]),
    }


def validate_resume(
    *,
    checkpoint_record: Mapping[str, Any] | None,
    resume_policy: Mapping[str, Any],
    checkpoint_age_minutes: int,
    has_validation_evidence: bool,
) -> dict[str, Any]:
    reason_codes: list[str] = []
    validation_failures: list[str] = []
    policy_failures: list[str] = []

    if checkpoint_record is None:
        validation_failures.append("CHECKPOINT_RECORD_MISSING")

    if resume_policy.get("allowed") is not True:
        policy_failures.append("RESUME_NOT_ALLOWED")

    max_age = int(resume_policy.get("max_resume_age_minutes") or 0)
    if max_age < 1:
        policy_failures.append("RESUME_POLICY_MAX_AGE_INVALID")
    elif checkpoint_age_minutes > max_age:
        policy_failures.append("RESUME_AGE_EXCEEDED")

    if resume_policy.get("validation_required") is True and not has_validation_evidence:
        validation_failures.append("RESUME_VALIDATION_EVIDENCE_MISSING")

    blocked = bool(validation_failures or policy_failures)
    reason_codes.extend(validation_failures)
    reason_codes.extend(policy_failures)
    return _base_result(
        allowed=not blocked,
        state="block" if blocked else "resume",
        reason_codes=reason_codes or ["RESUME_VALID"],
        validation_failures=validation_failures,
        policy_failures=policy_failures,
    )


def apply_resume(*, resume_validation: Mapping[str, Any], checkpoint_record: Mapping[str, Any] | None) -> dict[str, Any]:
    allowed = bool(resume_validation.get("allowed"))
    if not allowed or checkpoint_record is None:
        return {
            "applied": False,
            "state_snapshot": None,
            "result": _base_result(allowed=False, state="block", reason_codes=["RESUME_APPLY_BLOCKED"]),
        }

    state_snapshot = dict(checkpoint_record.get("state_snapshot") or {})
    return {
        "applied": True,
        "state_snapshot": state_snapshot,
        "result": _base_result(allowed=True, state="resume", reason_codes=["RESUME_APPLIED"]),
    }


def create_async_wait(
    *,
    checkpoint_id: str,
    wait_id: str,
    wait_condition: str,
    trigger_type: str,
    created_at: str,
    trace: Mapping[str, Any],
    async_policy: Mapping[str, Any],
) -> dict[str, Any]:
    if async_policy.get("allowed") is not True:
        return {"artifact": None, "result": _base_result(allowed=False, state="block", policy_failures=["ASYNC_WAIT_NOT_ALLOWED"]) }

    artifact = {
        "artifact_type": "async_wait_record",
        "schema_version": "1.0.0",
        "wait_id": wait_id,
        "checkpoint_id": checkpoint_id,
        "wait_condition": wait_condition,
        "trigger_type": trigger_type,
        "timeout_policy": {
            "max_wait_minutes": int(async_policy.get("max_wait_minutes") or 0),
            "timeout_behavior": str(async_policy.get("timeout_behavior") or "freeze"),
        },
        "created_at": created_at,
        "trace": dict(trace),
    }
    return {"artifact": artifact, "result": _base_result(allowed=True, state="wait", reason_codes=["ASYNC_WAIT_CREATED"])}


def validate_handoff(*, handoff_artifact: Mapping[str, Any] | None, stage_contract: Mapping[str, Any]) -> dict[str, Any]:
    execution_mode = str(stage_contract.get("execution_mode") or "continuous")
    if execution_mode != "reset_with_handoff":
        return _base_result(allowed=True, state="resume", reason_codes=["HANDOFF_NOT_REQUIRED"])

    failures: list[str] = []
    if handoff_artifact is None:
        failures.append("HANDOFF_REQUIRED")
    else:
        if handoff_artifact.get("artifact_type") != "handoff_artifact":
            failures.append("HANDOFF_ARTIFACT_TYPE_INVALID")
        if handoff_artifact.get("stage_contract_id") != stage_contract.get("contract_id"):
            failures.append("HANDOFF_STAGE_CONTRACT_MISMATCH")

    blocked = bool(failures)
    return _base_result(
        allowed=not blocked,
        state="handoff_required" if blocked else "resume",
        reason_codes=failures or ["HANDOFF_VALID"],
        validation_failures=failures,
    )


def evaluate_long_running_policy(
    *,
    stage_contract: Mapping[str, Any],
    checkpoint_record: Mapping[str, Any] | None,
    handoff_artifact: Mapping[str, Any] | None,
    request_resume: bool,
    checkpoint_age_minutes: int,
    has_resume_validation_evidence: bool,
    request_async_wait: bool,
    wait_elapsed_minutes: int,
) -> dict[str, Any]:
    reasons: list[str] = []
    validation_failures: list[str] = []
    policy_failures: list[str] = []

    handoff_result = validate_handoff(handoff_artifact=handoff_artifact, stage_contract=stage_contract)
    if handoff_result["allowed"] is False:
        validation_failures.extend(handoff_result["validation_failures"])

    if request_resume:
        resume_result = validate_resume(
            checkpoint_record=checkpoint_record,
            resume_policy=stage_contract.get("resume_policy") or {},
            checkpoint_age_minutes=checkpoint_age_minutes,
            has_validation_evidence=has_resume_validation_evidence,
        )
        if resume_result["allowed"] is False:
            validation_failures.extend(resume_result["validation_failures"])
            policy_failures.extend(resume_result["policy_failures"])
        reasons.extend(resume_result["reason_codes"])

    async_policy = stage_contract.get("async_policy") or {}
    if request_async_wait:
        if async_policy.get("allowed") is not True:
            policy_failures.append("ASYNC_WAIT_NOT_ALLOWED")
        max_wait = int(async_policy.get("max_wait_minutes") or 0)
        if max_wait < 1:
            policy_failures.append("ASYNC_WAIT_POLICY_MAX_INVALID")
        elif wait_elapsed_minutes > max_wait:
            timeout_behavior = str(async_policy.get("timeout_behavior") or "freeze")
            reasons.append("ASYNC_WAIT_TIMEOUT_EXCEEDED")
            if timeout_behavior == "block":
                policy_failures.append("ASYNC_WAIT_TIMEOUT_BLOCK")
            else:
                return _base_result(
                    allowed=False,
                    state="freeze",
                    reason_codes=reasons,
                    validation_failures=validation_failures,
                    policy_failures=policy_failures,
                )

    blocked = bool(validation_failures or policy_failures)
    if blocked:
        return _base_result(
            allowed=False,
            state="block",
            reason_codes=reasons,
            validation_failures=validation_failures,
            policy_failures=policy_failures,
        )

    if request_async_wait:
        return _base_result(allowed=True, state="wait", reason_codes=reasons or ["ASYNC_WAIT_ALLOWED"])
    if request_resume:
        return _base_result(allowed=True, state="resume", reason_codes=reasons or ["RESUME_ALLOWED"])
    return _base_result(allowed=True, state="resume", reason_codes=["LONG_RUNNING_POLICY_OK"])


def evaluate_context_stage_semantics(
    *,
    stage_name: str,
    artifacts: Mapping[str, Any],
    resume_requested: bool = False,
) -> dict[str, Any]:
    """HNX-owned context stage structure + continuity semantics (no execution/policy decisions)."""
    if stage_name not in _CONTEXT_STAGE_SEQUENCE:
        return _base_result(
            allowed=False,
            state="block",
            validation_failures=["UNKNOWN_CONTEXT_STAGE"],
            reason_codes=["UNKNOWN_CONTEXT_STAGE"],
        )

    failures: list[str] = []
    outputs_required: list[str] = []
    continuity_required: list[str] = []
    payload = dict(artifacts)

    if stage_name == "context_map":
        outputs_required = ["context_recipe_spec"]
    elif stage_name == "context_admission":
        outputs_required = ["context_source_admission_record"]
        if not isinstance(payload.get("context_recipe_spec"), Mapping):
            failures.append("MISSING_CONTEXT_RECIPE_SPEC")
    elif stage_name == "context_assembly":
        outputs_required = ["context_bundle_record"]
        for field in ("build_admission_record", "normalized_execution_request", "tlc_handoff_record", "tpa_slice_artifact"):
            if not isinstance(payload.get(field), Mapping):
                failures.append(f"MISSING_REQUIRED_LINEAGE_{field.upper()}")
    elif stage_name == "context_preflight":
        outputs_required = ["pqx_slice_execution_record"]
        for field in ("context_bundle_record", "tpa_slice_artifact"):
            if not isinstance(payload.get(field), Mapping):
                failures.append(f"MISSING_REQUIRED_INPUT_{field.upper()}")
    elif stage_name == "context_checkpoint_resume":
        outputs_required = ["checkpoint_record"]
        continuity_required = ["checkpoint_id", "checkpoint_hash", "resume_token"]
        if resume_requested:
            checkpoint = payload.get("checkpoint_record")
            if not isinstance(checkpoint, Mapping):
                failures.append("CHECKPOINT_RECORD_REQUIRED_FOR_RESUME")
            else:
                for key in continuity_required:
                    value = checkpoint.get(key)
                    if not isinstance(value, str) or not value.strip():
                        failures.append(f"MISSING_CONTINUITY_FIELD_{key.upper()}")

    status = "ready" if not failures else "blocked"
    return {
        **_base_result(
            allowed=not failures,
            state="resume" if not failures else "block",
            validation_failures=failures,
            reason_codes=failures or [f"{stage_name.upper()}_SEMANTICS_VALID"],
        ),
        "stage_name": stage_name,
        "outputs_required": outputs_required,
        "continuity_required": continuity_required,
        "status": status,
    }
