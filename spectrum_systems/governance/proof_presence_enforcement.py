"""GOV: proof_presence_enforcement — require core_loop_proof for PRs on governed surfaces (CLX-ALL-01 Phase 2).

Validates that any PR modifying governed surfaces (runtime modules, governance
modules, contracts) includes a valid ``loop_proof_bundle`` or equivalent proof
artifact. Emits ``proof_presence_enforcement_result``.

Gate logic (exact):
  - stage_count == 6  (AEX→PQX→EVL→TPA→CDE→SEL)  [from bundle refs]
  - transition_count == 5
  - primary_reason_present == True
  - trace_continuity == True

Gate result is block when any condition fails. Non-decisioning: the result artifact is consumed by CDE.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

# Governed surface path prefixes that require proof.
_GOVERNED_PREFIXES = (
    "spectrum_systems/modules/runtime/",
    "spectrum_systems/modules/governance/",
    "spectrum_systems/governance/",
    "contracts/",
    "docs/governance/",
    ".github/workflows/",
)

# Required canonical stages in the loop proof.
_REQUIRED_STAGES = ("AEX", "PQX", "EVL", "TPA", "CDE", "SEL")
_REQUIRED_STAGE_COUNT = 6
_REQUIRED_TRANSITION_COUNT = 5

# Proof artifact types accepted as evidence.
_ACCEPTED_PROOF_TYPES = frozenset([
    "loop_proof_bundle",
    "core_loop_alignment_record",
    "rfx_loop_proof",
])


class ProofPresenceEnforcementError(ValueError):
    """Raised when enforcement gate cannot complete deterministically."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _result_id(trace_id: str) -> str:
    digest = hashlib.sha256(f"pper-{trace_id}-{_now()}".encode()).hexdigest()[:12]
    return f"pper-{digest}"


def _is_governed_surface(path: str) -> bool:
    return any(path.startswith(pfx) for pfx in _GOVERNED_PREFIXES)


def _validate_loop_proof_bundle(proof: dict[str, Any]) -> dict[str, Any]:
    """Validate a loop_proof_bundle against required gate conditions.

    Returns a validation_detail dict with stage_count, transition_count,
    primary_reason_present, trace_continuity, and failure_reasons.
    """
    failure_reasons: list[str] = []

    # Derive stage count from the canonical reference fields.
    canonical_refs = [
        proof.get("execution_record_ref"),
        proof.get("eval_summary_ref"),
        proof.get("control_decision_ref"),
        proof.get("enforcement_action_ref"),
        proof.get("replay_record_ref"),
        proof.get("lineage_chain_ref"),
    ]
    # AEX (admission) → PQX (execution) → EVL (eval) → TPA (trust) → CDE (control) → SEL (enforcement)
    # The bundle references: execution + eval + control + enforcement + replay + lineage = 6 stage artifacts
    stage_count = sum(1 for r in canonical_refs if r)

    if stage_count < _REQUIRED_STAGE_COUNT:
        failure_reasons.append(
            f"proof_stage_count_insufficient: got {stage_count}, need {_REQUIRED_STAGE_COUNT}"
        )

    # Transition count = stage_count - 1 (each sequential handoff).
    transition_count = max(0, stage_count - 1)
    if transition_count < _REQUIRED_TRANSITION_COUNT:
        failure_reasons.append(
            f"proof_transition_count_insufficient: got {transition_count}, need {_REQUIRED_TRANSITION_COUNT}"
        )

    # primary_reason_present: trace_summary must have an owning_system or one_page_summary.
    trace_summary = proof.get("trace_summary") or {}
    one_page = str(trace_summary.get("one_page_summary") or "").strip()
    owning_system = trace_summary.get("owning_system")
    primary_reason_present = bool(one_page or owning_system)
    if not primary_reason_present:
        failure_reasons.append("proof_primary_reason_missing")

    # trace_continuity: overall_status must be present.
    overall_status = trace_summary.get("overall_status")
    trace_continuity = bool(overall_status)
    if not trace_continuity:
        failure_reasons.append("proof_trace_continuity_broken")

    return {
        "stage_count": stage_count,
        "transition_count": transition_count,
        "primary_reason_present": primary_reason_present,
        "trace_continuity": trace_continuity,
        "failure_reasons": failure_reasons,
    }


def _validate_core_loop_alignment_record(proof: dict[str, Any]) -> dict[str, Any]:
    """Validate a core_loop_alignment_record as proof presence evidence."""
    failure_reasons: list[str] = []
    stages = proof.get("maps_to_stages")
    if not isinstance(stages, list):
        stages = []
    stage_count = len(stages)
    transition_count = max(0, stage_count - 1)

    if stage_count < 4:
        failure_reasons.append(f"proof_stage_count_insufficient: got {stage_count}, need 4+ mapped stages")
    if transition_count < 3:
        failure_reasons.append(f"proof_transition_count_insufficient: got {transition_count}")

    justification = str(proof.get("loop_justification") or "").strip()
    primary_reason_present = bool(justification)
    if not primary_reason_present:
        failure_reasons.append("proof_primary_reason_missing: loop_justification absent")

    trace_continuity = bool(proof.get("strengthens_existing_loop"))
    if not trace_continuity:
        failure_reasons.append("proof_trace_continuity_broken: strengthens_existing_loop is false/missing")

    return {
        "stage_count": stage_count,
        "transition_count": transition_count,
        "primary_reason_present": primary_reason_present,
        "trace_continuity": trace_continuity,
        "failure_reasons": failure_reasons,
    }


def _validate_rfx_loop_proof(proof: dict[str, Any]) -> dict[str, Any]:
    """Validate an rfx_loop_proof as proof presence evidence."""
    failure_reasons: list[str] = []
    stage_map = proof.get("stage_map")
    if not isinstance(stage_map, dict):
        stage_map = {}
    stage_count = len([v for v in stage_map.values() if v and v != "Unknown"])
    transition_count = max(0, stage_count - 1)

    if stage_count < 4:
        failure_reasons.append(f"proof_stage_count_insufficient: got {stage_count}")
    if transition_count < 3:
        failure_reasons.append(f"proof_transition_count_insufficient: got {transition_count}")

    primary_reason = str(proof.get("primary_reason_code") or "").strip()
    primary_reason_present = bool(primary_reason and primary_reason != "rfx_loop_proof_reason_missing")
    if not primary_reason_present:
        failure_reasons.append("proof_primary_reason_missing")

    trace_continuity = proof.get("status") == "valid"
    if not trace_continuity:
        failure_reasons.append("proof_trace_continuity_broken: rfx_loop_proof status is not valid")

    return {
        "stage_count": stage_count,
        "transition_count": transition_count,
        "primary_reason_present": primary_reason_present,
        "trace_continuity": trace_continuity,
        "failure_reasons": failure_reasons,
    }


def enforce_proof_presence(
    *,
    changed_files: list[str],
    proof_artifact: dict[str, Any] | None,
    trace_id: str,
    run_id: str = "",
    pr_ref: str = "",
) -> dict[str, Any]:
    """Enforce core_loop_proof presence for PRs touching governed surfaces.

    Returns a ``proof_presence_enforcement_result``.

    BLOCK if:
      - Any changed file is a governed surface AND
      - proof_artifact is None, wrong type, or fails validation gates.

    PASS if:
      - No governed surfaces changed, OR
      - All validation gates pass.
    """
    if not isinstance(changed_files, list):
        raise ProofPresenceEnforcementError("changed_files must be a list")

    governed_surfaces = [f for f in changed_files if isinstance(f, str) and _is_governed_surface(f)]
    proof_required = len(governed_surfaces) > 0

    proof_found = False
    proof_artifact_id: str | None = None
    proof_valid = False
    validation_detail: dict[str, Any] = {
        "stage_count": None,
        "transition_count": None,
        "primary_reason_present": None,
        "trace_continuity": None,
        "failure_reasons": [],
    }
    block_reason: str | None = None

    if not proof_required:
        gate_status = "pass"
    else:
        if proof_artifact is None:
            block_reason = "proof_presence_required_but_missing"
            gate_status = "block"
        else:
            artifact_type = str(proof_artifact.get("artifact_type") or "")
            if artifact_type not in _ACCEPTED_PROOF_TYPES:
                block_reason = f"proof_artifact_type_not_accepted: '{artifact_type}'"
                gate_status = "block"
            else:
                proof_found = True
                proof_artifact_id = (
                    proof_artifact.get("bundle_id")
                    or proof_artifact.get("artifact_id")
                    or proof_artifact.get("proof_id")
                )

                if artifact_type == "loop_proof_bundle":
                    validation_detail = _validate_loop_proof_bundle(proof_artifact)
                elif artifact_type == "core_loop_alignment_record":
                    validation_detail = _validate_core_loop_alignment_record(proof_artifact)
                elif artifact_type == "rfx_loop_proof":
                    validation_detail = _validate_rfx_loop_proof(proof_artifact)
                else:
                    validation_detail["failure_reasons"] = ["unknown_proof_type"]

                failure_reasons = validation_detail.get("failure_reasons") or []
                proof_valid = len(failure_reasons) == 0

                if proof_valid:
                    gate_status = "pass"
                else:
                    block_reason = "; ".join(failure_reasons)
                    gate_status = "block"

    return {
        "artifact_type": "proof_presence_enforcement_result",
        "schema_version": "1.0.0",
        "result_id": _result_id(trace_id),
        "trace_id": trace_id,
        "run_id": run_id,
        "pr_ref": pr_ref,
        "governed_surfaces_changed": governed_surfaces,
        "proof_required": proof_required,
        "proof_found": proof_found,
        "proof_artifact_id": proof_artifact_id,
        "proof_valid": proof_valid,
        "validation_detail": validation_detail,
        "gate_status": gate_status,
        "block_reason": block_reason,
        "emitted_at": _now(),
    }


__all__ = [
    "ProofPresenceEnforcementError",
    "enforce_proof_presence",
]
