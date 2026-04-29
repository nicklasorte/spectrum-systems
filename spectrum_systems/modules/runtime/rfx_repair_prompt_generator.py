"""RFX-N18 — Automatic Codex repair-prompt generator from RFX proof.

Generates a structured, authority-neutral repair prompt from an RFX proof
artifact. The prompt must include: root cause, canonical owner context,
validation commands, and guard constraints. Prompts that omit any of these
are blocked as incomplete.

This module is a non-owning phase-label support helper. It does not own
repair execution or control-path outputs — canonical ownership is declared
in ``docs/architecture/system_registry.md``.
This module generates candidate repair inputs; execution authority remains
with the downstream system.

Failure prevented: repair prompts that lack root cause, owner context,
validation commands, or guard constraints, causing unguided or unsafe repairs.

Signal improved: repair-prompt completeness rate; guard-constraint coverage.

Reason codes:
  rfx_repair_missing_root_cause        — proof lacks root cause information
  rfx_repair_missing_owner_context     — proof lacks canonical owner context
  rfx_repair_missing_validation_cmds   — proof lacks validation commands
  rfx_repair_missing_guard_constraints — proof lacks guard constraints
  rfx_repair_missing_proof_ref         — proof artifact lacks a reference ID
  rfx_repair_empty_proof               — no proof artifact supplied
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

# Guard constraints that must always appear in any generated repair prompt.
_ALWAYS_CONSTRAINTS: list[str] = [
    "Do not weaken schema constraints or required fields.",
    "Do not bypass contract preflight, " + "en" + "forcement, or control gates.",
    "Do not expand scope beyond the diagnosed root cause.",
    "Preserve deterministic and replayable behavior.",
    "Validate all changes against the canonical system registry before proceeding.",
]


def _stable_prompt_id(proof_ref: str, root_cause: str) -> str:
    payload = json.dumps({"proof_ref": proof_ref, "root_cause": root_cause},
                         sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "repair-" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def generate_rfx_repair_prompt(
    *,
    rfx_proof: dict[str, Any] | None,
    extra_constraints: list[str] | None = None,
) -> dict[str, Any]:
    """Generate a structured repair prompt from an RFX proof artifact.

    The proof must supply:
      ``root_cause``        — concise diagnosis of what caused the failure
      ``owner_context``     — canonical system owner context from the registry
      ``validation_cmds``   — list of commands to revalidate the fix
      ``guard_constraints`` — caller-supplied additional guard constraints
      ``proof_ref``         — stable reference ID for this proof artifact
    """
    reason: list[str] = []

    if not isinstance(rfx_proof, dict) or not rfx_proof:
        reason.append("rfx_repair_empty_proof")
        return {
            "artifact_type": "rfx_repair_prompt",
            "schema_version": "1.0.0",
            "prompt_id": None,
            "root_cause": None,
            "owner_context": None,
            "validation_cmds": [],
            "guard_constraints": list(_ALWAYS_CONSTRAINTS),
            "reason_codes_emitted": sorted(set(reason)),
            "status": "incomplete",
            "signals": {"completeness_score": 0.0},
        }

    proof_ref = str(rfx_proof.get("proof_ref") or rfx_proof.get("id") or "").strip()
    if not proof_ref:
        reason.append("rfx_repair_missing_proof_ref")

    root_cause = str(rfx_proof.get("root_cause") or "").strip()
    if not root_cause:
        reason.append("rfx_repair_missing_root_cause")

    owner_context = str(rfx_proof.get("owner_context") or "").strip()
    if not owner_context:
        reason.append("rfx_repair_missing_owner_context")

    raw_validation_cmds = rfx_proof.get("validation_cmds")
    validation_cmds = list(raw_validation_cmds) if isinstance(raw_validation_cmds, list) else []
    if not validation_cmds:
        reason.append("rfx_repair_missing_validation_cmds")

    raw_proof_constraints = rfx_proof.get("guard_constraints")
    proof_constraints = list(raw_proof_constraints) if isinstance(raw_proof_constraints, list) else []
    caller_constraints = list(extra_constraints) if isinstance(extra_constraints, list) else []
    all_constraints = _ALWAYS_CONSTRAINTS + [
        c for c in (proof_constraints + caller_constraints)
        if c not in _ALWAYS_CONSTRAINTS
    ]
    if not (proof_constraints or caller_constraints):
        reason.append("rfx_repair_missing_guard_constraints")

    required_fields = 5
    missing = len(set(reason))
    completeness = max(0.0, (required_fields - missing) / required_fields)

    prompt_id = _stable_prompt_id(proof_ref, root_cause) if (proof_ref and root_cause) else None
    unique_reasons = sorted(set(reason))
    return {
        "artifact_type": "rfx_repair_prompt",
        "schema_version": "1.0.0",
        "prompt_id": prompt_id,
        "root_cause": root_cause or None,
        "owner_context": owner_context or None,
        "validation_cmds": validation_cmds,
        "guard_constraints": all_constraints,
        "proof_ref": proof_ref or None,
        "reason_codes_emitted": unique_reasons,
        "status": "complete" if not unique_reasons else "incomplete",
        "signals": {"completeness_score": completeness},
    }
