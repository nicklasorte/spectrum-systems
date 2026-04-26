"""RFX freeze propagation — Part 3 of LOOP-07.

Emits a deterministic ``rfx_freeze_record`` artifact whose payload signals
to canonical owners that a reliability-freeze condition has fired
fail-closed across the RFX path. The record carries propagation flags
that downstream owners read; this module does not perform any of the
listed effects itself.

The freeze record signals (canonical owners listed in
``docs/architecture/system_registry.md``):

  * execution-blocked flag (read by the execution authority)
  * ready-blocked flag (read by the closure authority)
  * certification-blocked flag (read by the certification authority)
  * enforcement-action signal (read by the enforcement authority)

This module is a non-owning phase-label support helper. Canonical roles
remain in ``docs/architecture/system_registry.md`` — the freeze record
propagates a freeze decision but does not redefine ownership and does
not perform the enforcement itself.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


class RFXFreezePropagationError(ValueError):
    """Raised when freeze propagation inputs are malformed."""


# Canonical downstream targets that a reliability freeze MUST disable. Any
# caller-supplied set is unioned with these so a partial caller list cannot
# silently exempt a critical surface.
_REQUIRED_TARGETS: frozenset[str] = frozenset({"PQX", "CDE", "GOV", "SEL"})


_TARGET_EFFECT: dict[str, str] = {
    "PQX": "execution_blocked",
    "CDE": "ready_blocked",
    "GOV": "certification_blocked",
    "SEL": "halt_signal_emitted",
}


def _hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_reason_codes(reason_codes: list[str] | None) -> list[str]:
    if not isinstance(reason_codes, list) or not reason_codes:
        raise RFXFreezePropagationError(
            "rfx_freeze_propagation_invalid: reason_codes must be a non-empty list"
        )
    cleaned: list[str] = []
    for code in reason_codes:
        if not isinstance(code, str) or not code.strip():
            raise RFXFreezePropagationError(
                "rfx_freeze_propagation_invalid: reason_codes must contain non-empty strings"
            )
        cleaned.append(code.strip())
    # Preserve order, deduplicate.
    seen: set[str] = set()
    deduped: list[str] = []
    for c in cleaned:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped


def _normalize_targets(downstream_targets: list[str] | None) -> list[str]:
    union: set[str] = set(_REQUIRED_TARGETS)
    for t in downstream_targets or []:
        if not isinstance(t, str) or not t.strip():
            raise RFXFreezePropagationError(
                "rfx_freeze_propagation_invalid: downstream_targets must contain non-empty strings"
            )
        union.add(t.strip())
    # Deterministic ordering for the artifact.
    return sorted(union)


def propagate_rfx_freeze(
    *,
    reason_codes: list[str] | None,
    downstream_targets: list[str] | None,
    trace_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Emit a ``rfx_freeze_record`` propagating the freeze fail-closed.

    The record is deterministic given the same inputs and contains the
    explicit propagation effect for each downstream target. PQX, CDE, GOV,
    and SEL are always included — callers cannot omit them.
    """
    codes = _normalize_reason_codes(reason_codes)
    targets = _normalize_targets(downstream_targets)

    propagation: dict[str, str] = {}
    for t in targets:
        # Recognized canonical targets get their canonical effect; unknown
        # targets are still recorded with a deterministic generic effect so
        # propagation cannot silently drop them.
        propagation[t] = _TARGET_EFFECT.get(t, "freeze_propagated")

    freeze_id = f"rfx-freeze-{_hash([codes, targets, trace_id, created_at])[:16]}"

    return {
        "artifact_type": "rfx_freeze_record",
        "schema_version": "1.0.0",
        "freeze_id": freeze_id,
        "trace_id": trace_id,
        "created_at": created_at,
        "reason_codes": codes,
        "downstream_targets": targets,
        "propagation": propagation,
        "pqx_execution_blocked": True,
        "cde_ready_blocked": True,
        "gov_certification_blocked": True,
        "sel_enforcement_signal": "halt_requested",
    }


__all__ = [
    "RFXFreezePropagationError",
    "propagate_rfx_freeze",
]
