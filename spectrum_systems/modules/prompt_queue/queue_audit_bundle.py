"""Deterministic fail-closed queue audit bundle builder."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from spectrum_systems.modules.prompt_queue.execution_artifact_io import validate_execution_result_artifact
from spectrum_systems.modules.prompt_queue.prompt_queue_transition_artifact_io import (
    validate_prompt_queue_transition_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_artifact_io import (
    ArtifactValidationError,
    validate_observability_snapshot,
    validate_queue_audit_bundle,
    validate_queue_certification_record,
    validate_queue_state,
    validate_replay_record,
    validate_resume_checkpoint,
)
from spectrum_systems.modules.prompt_queue.queue_manifest_validator import validate_queue_manifest
from spectrum_systems.modules.prompt_queue.step_decision import validate_step_decision_artifact


class QueueAuditBundleError(ValueError):
    """Raised when queue audit bundle refs are invalid or malformed."""


_REQUIRED_REFS = (
    "manifest_ref",
    "final_queue_state_ref",
    "execution_result_refs",
    "step_decision_refs",
    "transition_decision_refs",
    "observability_ref",
    "certification_ref",
)


def _stable_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_json_object(path_value: str, *, label: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_file():
        raise QueueAuditBundleError(f"{label} file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise QueueAuditBundleError(f"{label} must be a JSON object: {path}")
    return payload


def _parse_refs(input_refs: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(input_refs, dict):
        raise QueueAuditBundleError("input_refs must be an object")

    parsed: dict[str, Any] = {}
    for key in _REQUIRED_REFS:
        value = input_refs.get(key)
        if key.endswith("_refs"):
            if not isinstance(value, list) or not value:
                raise QueueAuditBundleError(f"missing required input ref list: {key}")
            if not all(isinstance(item, str) and item.strip() for item in value):
                raise QueueAuditBundleError(f"{key} must be an array of non-empty strings")
            parsed[key] = sorted(set(value))
        else:
            if not isinstance(value, str) or not value.strip():
                raise QueueAuditBundleError(f"missing required input ref: {key}")
            parsed[key] = value

    replay_refs = input_refs.get("replay_refs", [])
    if replay_refs is None:
        replay_refs = []
    if not isinstance(replay_refs, list) or not all(isinstance(item, str) and item.strip() for item in replay_refs):
        raise QueueAuditBundleError("replay_refs must be an array of non-empty strings when provided")
    parsed["replay_refs"] = sorted(set(replay_refs))
    return parsed


def _validate_replay_artifact(payload: dict[str, Any], *, label: str) -> str:
    try:
        validate_replay_record(payload)
        return "record"
    except ArtifactValidationError:
        pass

    try:
        validate_resume_checkpoint(payload)
        return "checkpoint"
    except ArtifactValidationError as exc:
        raise QueueAuditBundleError(f"{label} is neither replay_record nor resume_checkpoint: {exc}") from exc


def _trace_matches(value: Any, *, trace_id: str, queue_id: str) -> bool:
    return isinstance(value, str) and value in {trace_id, queue_id}


def build_queue_audit_bundle(input_refs: dict) -> dict:
    """Build a deterministic fail-closed queue audit bundle artifact."""
    refs = _parse_refs(input_refs)

    manifest = _read_json_object(refs["manifest_ref"], label="manifest")
    validate_queue_manifest(manifest)

    final_state = _read_json_object(refs["final_queue_state_ref"], label="final_queue_state")
    validate_queue_state(final_state)

    observability = _read_json_object(refs["observability_ref"], label="observability")
    validate_observability_snapshot(observability)

    certification = _read_json_object(refs["certification_ref"], label="certification")
    validate_queue_certification_record(certification)

    execution_results: dict[str, dict[str, Any]] = {}
    for ref in refs["execution_result_refs"]:
        artifact = _read_json_object(ref, label="execution_result")
        validate_execution_result_artifact(artifact)
        step_id = artifact.get("step_id")
        if not isinstance(step_id, str) or not step_id:
            raise QueueAuditBundleError(f"execution_result missing step_id: {ref}")
        execution_results[step_id] = artifact

    step_decisions: dict[str, dict[str, Any]] = {}
    for ref in refs["step_decision_refs"]:
        artifact = _read_json_object(ref, label="step_decision")
        validate_step_decision_artifact(artifact)
        step_id = artifact.get("step_id")
        if not isinstance(step_id, str) or not step_id:
            raise QueueAuditBundleError(f"step_decision missing step_id: {ref}")
        step_decisions[step_id] = artifact

    transition_decisions: dict[str, dict[str, Any]] = {}
    for ref in refs["transition_decision_refs"]:
        artifact = _read_json_object(ref, label="transition_decision")
        validate_prompt_queue_transition_decision_artifact(artifact)
        step_id = artifact.get("step_id")
        if not isinstance(step_id, str) or not step_id:
            raise QueueAuditBundleError(f"transition_decision missing step_id: {ref}")
        transition_decisions[step_id] = artifact

    replay_types: list[str] = []
    replay_payloads: list[dict[str, Any]] = []
    for ref in refs["replay_refs"]:
        payload = _read_json_object(ref, label="replay")
        replay_types.append(_validate_replay_artifact(payload, label=f"replay:{ref}"))
        replay_payloads.append(payload)

    queue_id = str(manifest["queue_id"])
    trace_id = str(manifest["execution_policy"]["trace_id"])
    timestamp = str(final_state.get("last_updated") or final_state.get("updated_at") or manifest.get("created_at"))

    completeness_reasons: list[str] = []
    lineage_reasons: list[str] = []

    if final_state.get("queue_id") != queue_id:
        lineage_reasons.append("final_queue_state_queue_id_mismatch")
    if observability.get("health_metrics", {}).get("queue_id") != queue_id:
        lineage_reasons.append("observability_queue_id_mismatch")
    if certification.get("queue_id") != queue_id:
        lineage_reasons.append("certification_queue_id_mismatch")
    if certification.get("trace_id") != trace_id:
        lineage_reasons.append("certification_trace_id_mismatch")
    if certification.get("manifest_ref") != refs["manifest_ref"]:
        lineage_reasons.append("certification_manifest_ref_mismatch")
    if certification.get("final_queue_state_ref") != refs["final_queue_state_ref"]:
        lineage_reasons.append("certification_final_state_ref_mismatch")
    if certification.get("observability_ref") != refs["observability_ref"]:
        lineage_reasons.append("certification_observability_ref_mismatch")
    if certification.get("certification_status") != "passed":
        completeness_reasons.append("certification_not_passed")

    if final_state.get("queue_status") != "completed":
        completeness_reasons.append("queue_not_completed")

    completed_step_ids = sorted(
        entry["step_id"]
        for entry in final_state.get("step_results", [])
        if isinstance(entry, dict) and entry.get("status") == "completed" and isinstance(entry.get("step_id"), str)
    )
    if not completed_step_ids:
        completeness_reasons.append("missing_completed_step_results")

    for step_id in completed_step_ids:
        if step_id not in execution_results:
            completeness_reasons.append(f"missing_execution_result_for_{step_id}")
        if step_id not in step_decisions:
            completeness_reasons.append(f"missing_step_decision_for_{step_id}")
        if step_id not in transition_decisions:
            completeness_reasons.append(f"missing_transition_decision_for_{step_id}")

    for step_id in sorted(execution_results):
        if step_id not in completed_step_ids:
            completeness_reasons.append(f"unexpected_execution_result_for_{step_id}")
        trace_linkage = execution_results[step_id].get("trace_linkage")
        if not _trace_matches(trace_linkage, trace_id=trace_id, queue_id=queue_id):
            lineage_reasons.append(f"execution_trace_linkage_mismatch:{step_id}")
    for step_id in sorted(step_decisions):
        if step_id not in completed_step_ids:
            completeness_reasons.append(f"unexpected_step_decision_for_{step_id}")
        trace_linkage = step_decisions[step_id].get("trace_linkage")
        if trace_linkage is not None and not _trace_matches(trace_linkage, trace_id=trace_id, queue_id=queue_id):
            lineage_reasons.append(f"step_decision_trace_linkage_mismatch:{step_id}")
    for step_id in sorted(transition_decisions):
        if step_id not in completed_step_ids:
            completeness_reasons.append(f"unexpected_transition_decision_for_{step_id}")
        trace_linkage = transition_decisions[step_id].get("trace_linkage")
        if trace_linkage is not None and not _trace_matches(trace_linkage, trace_id=trace_id, queue_id=queue_id):
            lineage_reasons.append(f"transition_decision_trace_linkage_mismatch:{step_id}")

    certification_checkpoint_refs = certification.get("replay_checkpoint_refs", [])
    if certification_checkpoint_refs and not refs["replay_refs"]:
        completeness_reasons.append("missing_required_replay_refs")
    for checkpoint_ref in certification_checkpoint_refs:
        if checkpoint_ref not in refs["replay_refs"]:
            completeness_reasons.append(f"missing_certified_replay_ref:{checkpoint_ref}")

    for replay_type, replay_payload in zip(replay_types, replay_payloads):
        if replay_payload.get("queue_id") != queue_id:
            lineage_reasons.append(f"replay_queue_id_mismatch:{replay_type}")
        replay_trace_id = replay_payload.get("trace_id")
        if replay_trace_id != trace_id:
            lineage_reasons.append(f"replay_trace_id_mismatch:{replay_type}")

    lineage_status = "complete" if not lineage_reasons else "incomplete"
    completeness_status = "complete" if not (completeness_reasons or lineage_reasons) else "incomplete"

    deterministic_context = {
        "queue_id": queue_id,
        "manifest_ref": refs["manifest_ref"],
        "final_queue_state_ref": refs["final_queue_state_ref"],
        "execution_result_refs": refs["execution_result_refs"],
        "step_decision_refs": refs["step_decision_refs"],
        "transition_decision_refs": refs["transition_decision_refs"],
        "replay_refs": refs["replay_refs"],
        "observability_ref": refs["observability_ref"],
        "certification_ref": refs["certification_ref"],
        "lineage_status": lineage_status,
        "completeness_status": completeness_status,
        "lineage_reasons": sorted(set(lineage_reasons)),
        "completeness_reasons": sorted(set(completeness_reasons)),
        "trace_id": trace_id,
        "timestamp": timestamp,
    }

    bundle = {
        "audit_bundle_id": _stable_hash(deterministic_context),
        "queue_id": queue_id,
        "manifest_ref": refs["manifest_ref"],
        "final_queue_state_ref": refs["final_queue_state_ref"],
        "execution_result_refs": refs["execution_result_refs"],
        "step_decision_refs": refs["step_decision_refs"],
        "transition_decision_refs": refs["transition_decision_refs"],
        "replay_refs": refs["replay_refs"],
        "observability_ref": refs["observability_ref"],
        "certification_ref": refs["certification_ref"],
        "lineage_status": lineage_status,
        "completeness_status": completeness_status,
        "trace_id": trace_id,
        "timestamp": timestamp,
    }

    validate_queue_audit_bundle(bundle)
    return bundle
