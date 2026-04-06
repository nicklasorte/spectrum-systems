"""Deterministic Closure Decision Engine (CDE-001).

CDE consumes governed review/closure artifacts and emits an evidence-traceable
closure_decision_artifact. Optionally, it emits a bounded next_step_prompt_artifact
when a deterministic governed next step can be produced without fuzzy reasoning.
"""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import deterministic_id

_ALLOWED_SOURCE_TYPES = {
    "review_artifact",
    "review_action_tracker_artifact",
    "review_signal_artifact",
    "review_control_signal_artifact",
    "review_integration_packet_artifact",
    "review_projection_bundle_artifact",
    "review_consumer_output_bundle_artifact",
}

_DECISION_TYPES = (
    "lock",
    "hardening_required",
    "final_verification_required",
    "continue_bounded",
    "blocked",
    "escalate",
)

_NEXT_STEP_CLASS_BY_DECISION = {
    "lock": "none",
    "hardening_required": "hardening_batch",
    "final_verification_required": "final_verification",
    "continue_bounded": "bounded_continue",
    "blocked": "none",
    "escalate": "escalation",
}


class ClosureDecisionEngineError(ValueError):
    """Raised when closure decisioning cannot proceed deterministically."""


def _validate_schema(instance: dict[str, Any], schema_name: str, *, label: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name))
    errors = sorted(validator.iter_errors(instance), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ClosureDecisionEngineError(f"{label} failed schema validation: {details}")


def _require_non_empty(value: Any, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ClosureDecisionEngineError(f"missing required non-empty field: {field_name}")
    return text


def _extract_source_ref(artifact: dict[str, Any]) -> str:
    if isinstance(artifact.get("artifact_ref"), str) and artifact["artifact_ref"].strip():
        return artifact["artifact_ref"].strip()

    for key, value in artifact.items():
        if key.endswith("_id") and isinstance(value, str) and value.strip():
            return f"{artifact.get('artifact_type')}:{value}"

    raise ClosureDecisionEngineError("source artifact is missing deterministic reference identity")


def _extract_counts(source_artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    blocker_count = 0
    critical_count = 0
    high_priority_count = 0
    medium_priority_count = 0
    unresolved_action_item_ids: set[str] = set()
    evidence_refs: set[str] = set()
    reason_codes: set[str] = set()
    escalation_present = False

    severity_to_counter = {
        "critical": "critical_count",
        "high": "high_priority_count",
        "medium": "medium_priority_count",
        "p0": "critical_count",
        "p1": "high_priority_count",
        "p2": "medium_priority_count",
    }

    for artifact in source_artifacts:
        source_ref = _extract_source_ref(artifact)
        evidence_refs.add(source_ref)

        blocker_count += int(artifact.get("blocker_count", 0) or 0)
        critical_count += int(artifact.get("critical_count", 0) or 0)
        high_priority_count += int(artifact.get("high_priority_count", 0) or 0)
        medium_priority_count += int(artifact.get("medium_priority_count", 0) or 0)

        if bool(artifact.get("blocker_present")):
            blocker_count += 1
            reason_codes.add("blocker_present")

        if bool(artifact.get("escalation_present")):
            escalation_present = True

        reasons = artifact.get("decision_reason_codes")
        if isinstance(reasons, list):
            for reason in reasons:
                if isinstance(reason, str) and reason.strip():
                    reason_codes.add(reason.strip())

        for key in ("unresolved_action_item_ids", "open_action_item_ids"):
            ids = artifact.get(key)
            if isinstance(ids, list):
                for item_id in ids:
                    if isinstance(item_id, str) and item_id.strip():
                        unresolved_action_item_ids.add(item_id.strip())

        for key in ("classified_signals", "control_queue_items", "readiness_items"):
            items = artifact.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                severity = str(item.get("severity", "")).strip().lower()
                counter_name = severity_to_counter.get(severity)
                if counter_name == "critical_count":
                    critical_count += 1
                elif counter_name == "high_priority_count":
                    high_priority_count += 1
                elif counter_name == "medium_priority_count":
                    medium_priority_count += 1
                if bool(item.get("blocker_related")):
                    blocker_count += 1

    malformed_evidence = any(value < 0 for value in (blocker_count, critical_count, high_priority_count, medium_priority_count))

    return {
        "blocker_count": max(blocker_count, 0),
        "critical_count": max(critical_count, 0),
        "high_priority_count": max(high_priority_count, 0),
        "medium_priority_count": max(medium_priority_count, 0),
        "unresolved_action_item_ids": sorted(unresolved_action_item_ids),
        "evidence_refs": sorted(evidence_refs),
        "reason_codes": sorted(reason_codes),
        "escalation_present": escalation_present,
        "malformed_evidence": malformed_evidence,
    }


def _validate_sources(source_artifacts: Any) -> list[dict[str, Any]]:
    if not isinstance(source_artifacts, list) or not source_artifacts:
        raise ClosureDecisionEngineError("source_artifacts must be a non-empty array")

    typed_sources: list[dict[str, Any]] = []
    for artifact in source_artifacts:
        if not isinstance(artifact, dict):
            raise ClosureDecisionEngineError("source_artifacts entries must be objects")
        artifact_type = _require_non_empty(artifact.get("artifact_type"), "source_artifacts[].artifact_type")
        if artifact_type not in _ALLOWED_SOURCE_TYPES:
            raise ClosureDecisionEngineError(f"unsupported source artifact type: {artifact_type}")
        typed_sources.append(artifact)
    return typed_sources


def _determine_decision(
    *,
    counts: dict[str, Any],
    closure_complete: bool,
    final_verification_passed: bool,
    hardening_completed: bool,
    escalation_required: bool,
    bounded_next_step_available: bool,
) -> tuple[str, list[str]]:
    reason_codes = set(counts["reason_codes"])

    if bool(counts.get("malformed_evidence")):
        return "blocked", sorted(reason_codes | {"malformed_evidence"})

    if escalation_required or counts["escalation_present"]:
        return "escalate", sorted(reason_codes | {"escalation_required"})

    if (
        final_verification_passed
        and closure_complete
        and counts["blocker_count"] == 0
        and counts["critical_count"] == 0
        and counts["high_priority_count"] == 0
        and not counts["unresolved_action_item_ids"]
    ):
        return "lock", sorted(reason_codes | {"final_verification_passed"})

    if counts["critical_count"] > 0 or counts["high_priority_count"] > 0:
        return "hardening_required", sorted(reason_codes | {"open_critical_or_high_items"})

    if hardening_completed and not final_verification_passed and counts["blocker_count"] == 0:
        return "final_verification_required", sorted(reason_codes | {"post_hardening_final_verification_required"})

    if counts["blocker_count"] > 0:
        return "blocked", sorted(reason_codes | {"blocking_items_present"})

    if bounded_next_step_available:
        return "continue_bounded", sorted(reason_codes | {"bounded_next_step_available"})

    return "blocked", sorted(reason_codes | {"no_safe_bounded_next_step"})


def build_closure_decision_artifact(request: dict[str, Any]) -> dict[str, Any]:
    """Build a schema-valid closure_decision_artifact from governed inputs."""
    subject_scope = _require_non_empty(request.get("subject_scope"), "subject_scope")
    emitted_at = _require_non_empty(request.get("emitted_at"), "emitted_at")
    trace_id = _require_non_empty(request.get("trace_id"), "trace_id")

    source_artifacts = _validate_sources(request.get("source_artifacts"))
    counts = _extract_counts(source_artifacts)

    closure_complete = bool(request.get("closure_complete", False))
    final_verification_passed = bool(request.get("final_verification_passed", False))
    hardening_completed = bool(request.get("hardening_completed", False))
    escalation_required = bool(request.get("escalation_required", False))
    bounded_next_step_available = bool(request.get("bounded_next_step_available", False))

    if not counts["evidence_refs"]:
        raise ClosureDecisionEngineError("insufficient evidence references for closure decision")

    decision_type, decision_reason_codes = _determine_decision(
        counts=counts,
        closure_complete=closure_complete,
        final_verification_passed=final_verification_passed,
        hardening_completed=hardening_completed,
        escalation_required=escalation_required,
        bounded_next_step_available=bounded_next_step_available,
    )

    if decision_type not in _DECISION_TYPES:
        raise ClosureDecisionEngineError(f"unsupported decision type derived: {decision_type}")

    next_step_class = _NEXT_STEP_CLASS_BY_DECISION[decision_type]
    source_artifact_refs = sorted(_extract_source_ref(artifact) for artifact in source_artifacts)

    requested_next_step_ref = request.get("next_step_ref")
    next_step_ref = str(requested_next_step_ref).strip() if isinstance(requested_next_step_ref, str) and requested_next_step_ref.strip() else None
    if next_step_class == "none":
        next_step_ref = None

    if decision_type in {"continue_bounded", "hardening_required", "final_verification_required"} and not next_step_ref:
        decision_type = "blocked"
        next_step_class = "none"
        decision_reason_codes = sorted(set(decision_reason_codes) | {"missing_next_step_ref"})

    lock_status = "not_locked"
    if decision_type == "lock":
        lock_status = "locked"
    elif decision_type in {"blocked", "escalate"}:
        lock_status = "blocked"

    decision_seed = {
        "subject_scope": subject_scope,
        "decision_type": decision_type,
        "decision_reason_codes": decision_reason_codes,
        "blocker_count": counts["blocker_count"],
        "critical_count": counts["critical_count"],
        "high_priority_count": counts["high_priority_count"],
        "medium_priority_count": counts["medium_priority_count"],
        "unresolved_action_item_ids": counts["unresolved_action_item_ids"],
        "source_artifact_refs": source_artifact_refs,
        "trace_id": trace_id,
    }

    artifact = {
        "artifact_type": "closure_decision_artifact",
        "artifact_class": "coordination",
        "schema_version": "1.0.0",
        "closure_decision_id": deterministic_id(
            prefix="cda",
            namespace="closure_decision_artifact",
            payload=decision_seed,
        ),
        "subject_scope": subject_scope,
        "subsystem_acronym": request.get("subsystem_acronym"),
        "run_id": request.get("run_id"),
        "review_date": request.get("review_date"),
        "action_tracker_ref": request.get("action_tracker_ref"),
        "decision_type": decision_type,
        "decision_reason_codes": decision_reason_codes,
        "blocker_count": counts["blocker_count"],
        "critical_count": counts["critical_count"],
        "high_priority_count": counts["high_priority_count"],
        "medium_priority_count": counts["medium_priority_count"],
        "unresolved_action_item_ids": counts["unresolved_action_item_ids"],
        "lock_status": lock_status,
        "next_step_class": next_step_class,
        "next_step_ref": next_step_ref,
        "bounded_next_step_available": bool(next_step_ref),
        "evidence_refs": counts["evidence_refs"],
        "source_artifact_refs": source_artifact_refs,
        "final_summary": (
            f"Closure decision '{decision_type}' for scope '{subject_scope}' based on "
            f"blockers={counts['blocker_count']}, critical={counts['critical_count']}, "
            f"high={counts['high_priority_count']}, unresolved_actions={len(counts['unresolved_action_item_ids'])}."
        ),
        "emitted_at": emitted_at,
        "trace_id": trace_id,
        "provenance": {
            "engine": "closure_decision_engine",
            "decision_rules_version": "cde-001-v1",
            "deterministic_hash_basis": "canonical-json-sha256",
            "source_artifact_types": sorted({artifact["artifact_type"] for artifact in source_artifacts}),
            "source_artifact_refs": source_artifact_refs,
        },
    }

    _validate_schema(artifact, "closure_decision_artifact", label="closure_decision_artifact")
    return artifact


def maybe_build_next_step_prompt_artifact(
    *,
    closure_decision_artifact: dict[str, Any],
    required_inputs: list[str],
    stop_conditions: list[str],
    boundedness_notes: list[str],
    emitted_at: str,
) -> dict[str, Any] | None:
    """Build optional deterministic next_step_prompt_artifact when boundedly safe."""
    _validate_schema(closure_decision_artifact, "closure_decision_artifact", label="closure_decision_artifact")

    next_step_class = closure_decision_artifact["next_step_class"]
    if next_step_class == "none" or not closure_decision_artifact.get("next_step_ref"):
        return None

    prompt_class = next_step_class
    artifact_seed = {
        "source_closure_decision_ref": closure_decision_artifact["closure_decision_id"],
        "prompt_class": prompt_class,
        "subject_scope": closure_decision_artifact["subject_scope"],
        "required_inputs": sorted(required_inputs),
        "reason_codes": closure_decision_artifact["decision_reason_codes"],
        "stop_conditions": sorted(stop_conditions),
    }

    prompt_artifact = {
        "artifact_type": "next_step_prompt_artifact",
        "artifact_class": "coordination",
        "schema_version": "1.0.0",
        "prompt_artifact_id": deterministic_id(
            prefix="nsp",
            namespace="next_step_prompt_artifact",
            payload=artifact_seed,
        ),
        "prompt_class": prompt_class,
        "subject_scope": closure_decision_artifact["subject_scope"],
        "required_inputs": sorted(set(required_inputs)),
        "reason_codes": closure_decision_artifact["decision_reason_codes"],
        "source_closure_decision_ref": closure_decision_artifact["closure_decision_id"],
        "source_next_step_ref": closure_decision_artifact["next_step_ref"],
        "stop_conditions": sorted(set(stop_conditions)),
        "boundedness_notes": sorted(set(boundedness_notes)),
        "emitted_at": emitted_at,
        "trace_id": closure_decision_artifact["trace_id"],
        "provenance": {
            "engine": "closure_decision_engine",
            "source_closure_decision_ref": closure_decision_artifact["closure_decision_id"],
            "deterministic_hash_basis": "canonical-json-sha256",
        },
    }
    _validate_schema(prompt_artifact, "next_step_prompt_artifact", label="next_step_prompt_artifact")
    return prompt_artifact


__all__ = [
    "ClosureDecisionEngineError",
    "build_closure_decision_artifact",
    "maybe_build_next_step_prompt_artifact",
]
