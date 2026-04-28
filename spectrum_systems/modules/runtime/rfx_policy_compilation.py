"""RFX policy compilation — RFX-12.

Converts validated judgment candidates into POL-compatible policy candidate
handoffs. This module is a non-owning phase-label support helper. POL owns
policy lifecycle / posture; RFX may not activate policy directly. Canonical
roles are recorded in ``docs/architecture/system_registry.md``.

Output:

  * ``rfx_policy_candidate_handoff``

Reason codes:

  * ``rfx_policy_source_missing``
  * ``rfx_policy_candidate_invalid``
  * ``rfx_policy_eval_requirement_missing``
  * ``rfx_policy_rollout_requirement_missing``
  * ``rfx_pol_handoff_missing``
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


class RFXPolicyCompilationError(ValueError):
    """Raised when policy compilation fails closed."""


def _stable_id(payload: Any, *, prefix: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def build_rfx_policy_candidate_handoff(
    *,
    source_judgment_refs: list[str] | None,
    candidate_text: str | None,
    candidate_structure: dict[str, Any] | None,
    eval_requirements: list[str] | None,
    rollout_requirements: list[str] | None,
    canary_requirements: list[str] | None,
    pol_handoff_target: str | None,
    activation_state: str = "candidate",
) -> dict[str, Any]:
    """Build a deterministic POL handoff envelope.

    Fails closed when judgment refs are missing, the candidate body is
    missing/invalid, eval requirements are absent, rollout/canary
    requirements are absent, or no POL handoff target is supplied.

    ``activation_state`` is forced to a candidate-class value: any attempt
    to pass an active or advanced lifecycle state raises
    ``rfx_policy_candidate_invalid``. POL retains all policy activation
    authority.
    """
    reasons: list[str] = []

    judgment_refs = [j.strip() for j in (source_judgment_refs or []) if isinstance(j, str) and j.strip()]
    if not judgment_refs:
        reasons.append(
            "rfx_policy_source_missing: candidate requires at least one judgment ref"
        )

    has_text = isinstance(candidate_text, str) and candidate_text.strip()
    has_struct = isinstance(candidate_structure, dict) and bool(candidate_structure)
    if not has_text and not has_struct:
        reasons.append(
            "rfx_policy_candidate_invalid: candidate_text or candidate_structure required"
        )

    if not isinstance(eval_requirements, list) or not any(
        isinstance(r, str) and r.strip() for r in eval_requirements
    ):
        reasons.append(
            "rfx_policy_eval_requirement_missing: eval_requirements absent"
        )

    rollout_present = isinstance(rollout_requirements, list) and any(
        isinstance(r, str) and r.strip() for r in rollout_requirements
    )
    canary_present = isinstance(canary_requirements, list) and any(
        isinstance(r, str) and r.strip() for r in canary_requirements
    )
    if not rollout_present and not canary_present:
        reasons.append(
            "rfx_policy_rollout_requirement_missing: rollout_requirements or canary_requirements absent"
        )

    if not isinstance(pol_handoff_target, str) or not pol_handoff_target.strip():
        reasons.append(
            "rfx_pol_handoff_missing: POL handoff target reference absent"
        )

    _ALLOWED_STATES = {"candidate", "proposed", "draft", "pending_pol"}
    if activation_state not in _ALLOWED_STATES:
        reasons.append(
            f"rfx_policy_candidate_invalid: activation_state={activation_state!r} "
            f"not in {sorted(_ALLOWED_STATES)!r} — RFX cannot activate policy"
        )

    if reasons:
        raise RFXPolicyCompilationError("; ".join(reasons))

    fingerprint_payload = {
        "source_judgment_refs": sorted(judgment_refs),
        "candidate_text": candidate_text.strip() if has_text else None,
        "candidate_structure": candidate_structure if has_struct else None,
    }
    handoff_id = _stable_id(fingerprint_payload, prefix="rfx-policy-handoff")
    return {
        "artifact_type": "rfx_policy_candidate_handoff",
        "schema_version": "1.0.0",
        "handoff_id": handoff_id,
        "source_judgment_refs": judgment_refs,
        "candidate_text": candidate_text.strip() if has_text else None,
        "candidate_structure": candidate_structure if has_struct else None,
        "eval_requirements": [r.strip() for r in eval_requirements if isinstance(r, str) and r.strip()],
        "rollout_requirements": [
            r.strip() for r in (rollout_requirements or []) if isinstance(r, str) and r.strip()
        ],
        "canary_requirements": [
            r.strip() for r in (canary_requirements or []) if isinstance(r, str) and r.strip()
        ],
        "pol_handoff_target": pol_handoff_target.strip(),  # type: ignore[union-attr]
        "activation_state": activation_state,
        "ownership_note": (
            "Advisory candidate handoff only; POL retains its canonical "
            "lifecycle and posture roles. RFX may not activate policy."
        ),
    }


__all__ = [
    "RFXPolicyCompilationError",
    "build_rfx_policy_candidate_handoff",
]
