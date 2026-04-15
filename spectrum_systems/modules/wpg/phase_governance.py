from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.wpg.common import WPGError, ensure_contract, stable_hash


DEFAULT_PHASE_SEQUENCE = [
    "PHASE_A",
    "PHASE_B",
    "PHASE_C",
    "PHASE_D",
    "PHASE_E",
    "PHASE_F",
    "PHASE_G",
    "PHASE_H",
]


@dataclass(frozen=True)
class PhaseDecision:
    status: str
    current_phase: str
    next_phase: str | None
    reason_codes: List[str]


def _phase_index(phase: str, sequence: List[str]) -> int:
    try:
        return sequence.index(phase)
    except ValueError as exc:  # fail-closed
        raise WPGError(f"unknown phase_id: {phase}") from exc


def default_phase_registry(trace_id: str = "wpg-trace-001") -> Dict[str, Any]:
    example = load_example("phase_registry")
    example["trace_id"] = trace_id
    return ensure_contract(example, "phase_registry")


def next_phase_for(current_phase: str, sequence: List[str]) -> str | None:
    idx = _phase_index(current_phase, sequence)
    return sequence[idx + 1] if idx + 1 < len(sequence) else None


def build_phase_checkpoint_record(
    *,
    phase_id: str,
    phase_label: str,
    status: str,
    trace_id: str,
    completed_step_refs: List[str],
    required_review_refs: List[str] | None = None,
    required_fix_refs: List[str] | None = None,
    blocking_reason_codes: List[str] | None = None,
    policy_version: str = "1.0.0",
    phase_sequence: List[str] | None = None,
) -> Dict[str, Any]:
    sequence = phase_sequence or DEFAULT_PHASE_SEQUENCE
    next_phase = next_phase_for(phase_id, sequence)
    checkpoint = {
        "artifact_type": "phase_checkpoint_record",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "phase_id": phase_id,
        "phase_label": phase_label,
        "status": status,
        "blocking_reason_codes": blocking_reason_codes or [],
        "required_fix_refs": required_fix_refs or [],
        "required_review_refs": required_review_refs or [],
        "completed_step_refs": completed_step_refs,
        "next_phase": next_phase,
        "resume_ready": status == "COMPLETE",
        "policy_version": policy_version,
        "replay_signature_refs": [f"sig:{stable_hash([phase_id, status, completed_step_refs])}"],
    }
    return ensure_contract(checkpoint, "phase_checkpoint_record")


def evaluate_phase_transition(
    *,
    phase_checkpoint_record: Dict[str, Any],
    phase_registry: Dict[str, Any],
    requested_action: str,
    redteam_open_high: int = 0,
    validation_passed: bool = True,
) -> Dict[str, Any]:
    checkpoint = ensure_contract(phase_checkpoint_record, "phase_checkpoint_record")
    registry = ensure_contract(phase_registry, "phase_registry")

    allowed_actions = {"start", "continue", "resume"}
    if requested_action not in allowed_actions:
        raise WPGError(f"unsupported transition action: {requested_action}")

    sequence = [phase["phase_id"] for phase in registry["phases"]]
    phase_id = checkpoint["phase_id"]
    _phase_index(phase_id, sequence)

    status = checkpoint["status"]
    reasons: List[str] = []
    decision = "ALLOW"

    if status in {"BLOCKED", "FIX_REQUIRED"}:
        decision = "BLOCK"
        reasons.append("checkpoint_not_complete")

    if checkpoint["required_review_refs"] and status != "COMPLETE":
        decision = "BLOCK"
        reasons.append("required_reviews_open")

    if checkpoint["required_fix_refs"] and status != "COMPLETE":
        decision = "BLOCK"
        reasons.append("required_fixes_open")

    if redteam_open_high > 0:
        decision = "BLOCK"
        reasons.append("high_severity_redteam_open")

    if not validation_passed:
        decision = "BLOCK"
        reasons.append("phase_validation_failed")

    current_index = _phase_index(phase_id, sequence)
    next_phase = sequence[current_index + 1] if current_index + 1 < len(sequence) else None
    may_advance = decision == "ALLOW" and status == "COMPLETE"

    result = {
        "artifact_type": "phase_transition_policy_result",
        "schema_version": "1.0.0",
        "trace_id": checkpoint["trace_id"],
        "phase_id": phase_id,
        "requested_action": requested_action,
        "decision": decision,
        "reason_codes": sorted(set(reasons)) if reasons else ["none"],
        "next_phase": next_phase if may_advance else phase_id,
        "may_advance": may_advance,
    }
    return ensure_contract(result, "phase_transition_policy_result")


def build_phase_resume_record(
    *,
    checkpoint: Dict[str, Any],
    next_executable_slice: str,
    remaining_required_slices: List[str],
) -> Dict[str, Any]:
    payload = {
        "artifact_type": "phase_resume_record",
        "schema_version": "1.0.0",
        "trace_id": checkpoint["trace_id"],
        "phase_id": checkpoint["phase_id"],
        "next_executable_slice": next_executable_slice,
        "remaining_required_slices": remaining_required_slices,
    }
    return ensure_contract(payload, "phase_resume_record")


def build_phase_handoff_record(
    *,
    checkpoint: Dict[str, Any],
    resume_record: Dict[str, Any],
    handoff_notes: List[str],
) -> Dict[str, Any]:
    payload = {
        "artifact_type": "phase_handoff_record",
        "schema_version": "1.0.0",
        "trace_id": checkpoint["trace_id"],
        "phase_id": checkpoint["phase_id"],
        "checkpoint_status": checkpoint["status"],
        "next_executable_slice": resume_record["next_executable_slice"],
        "blockers": checkpoint.get("blocking_reason_codes", []),
        "handoff_notes": handoff_notes,
    }
    return ensure_contract(payload, "phase_handoff_record")
