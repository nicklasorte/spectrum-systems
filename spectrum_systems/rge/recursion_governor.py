"""RGE Recursion Governor.

Bounds recursive RGE calls so the system cannot accidentally spiral into
self-generating roadmaps. Invariants:

  - MAX_RECURSION_DEPTH = 2          (depth 0 = initial call)
  - RECURSION_BUDGET_PER_WEEK = 5    (per trace root)
  - Circular chain detection        (same name-pattern in ancestor chain)

Emits `rge_recursion_record` for every call (audit trail), including blocks.
Recursion budget exhaustion freezes recursion only, not all of RGE.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from spectrum_systems.contracts import validate_artifact

MAX_RECURSION_DEPTH = 2
RECURSION_BUDGET_PER_WEEK = 5


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"REC-{hashlib.sha256(raw.encode()).hexdigest()[:12].upper()}"


def _phase_signature(phase_name: str) -> str:
    """Normalize a phase name to a coarse-grained signature for cycle detection."""
    tokens = [t for t in phase_name.upper().split() if t and not t.startswith("(")]
    return "-".join(tokens[:3])


def _has_circular_chain(ancestors: list[str], proposed_name: str) -> bool:
    sig = _phase_signature(proposed_name)
    if not sig:
        return False
    return any(_phase_signature(a) == sig for a in ancestors)


def govern_recursion(
    *,
    run_id: str,
    trace_id: str,
    proposed_phase_name: str,
    current_depth: int,
    ancestor_phase_names: list[str] | None = None,
    weekly_budget_used: int = 0,
) -> dict[str, Any]:
    """Decide whether a recursive RGE call may proceed.

    Returns an rge_recursion_record with decision in
    {"allow", "block_depth", "block_budget", "block_cycle"}.

    Never raises - always returns an auditable record.
    """
    ancestors = list(ancestor_phase_names or [])
    reasons: list[str] = []
    decision = "allow"

    if current_depth < 0:
        decision = "block_depth"
        reasons.append(f"current_depth ({current_depth}) must be >= 0")
    elif current_depth > MAX_RECURSION_DEPTH:
        decision = "block_depth"
        reasons.append(
            f"current_depth ({current_depth}) exceeds MAX_RECURSION_DEPTH "
            f"({MAX_RECURSION_DEPTH})"
        )

    if decision == "allow" and weekly_budget_used >= RECURSION_BUDGET_PER_WEEK:
        decision = "block_budget"
        reasons.append(
            f"weekly recursion budget exhausted "
            f"({weekly_budget_used}/{RECURSION_BUDGET_PER_WEEK})"
        )

    if decision == "allow" and _has_circular_chain(ancestors, proposed_phase_name):
        decision = "block_cycle"
        reasons.append(
            f"proposed phase '{proposed_phase_name}' matches an ancestor "
            "phase signature (circular chain)"
        )

    record = {
        "artifact_type": "rge_recursion_record",
        "schema_version": "1.0.0",
        "record_id": _stable_id({
            "run_id": run_id,
            "depth": current_depth,
            "name": proposed_phase_name,
        }),
        "run_id": run_id,
        "trace_id": trace_id,
        "created_at": _utc_now(),
        "proposed_phase_name": proposed_phase_name,
        "proposed_phase_signature": _phase_signature(proposed_phase_name),
        "current_depth": max(current_depth, 0),
        "max_depth": MAX_RECURSION_DEPTH,
        "weekly_budget_used": max(weekly_budget_used, 0),
        "weekly_budget_cap": RECURSION_BUDGET_PER_WEEK,
        "ancestor_phase_names": ancestors,
        "decision": decision,
        "block_reasons": reasons,
        "allowed": decision == "allow",
    }

    validate_artifact(record, "rge_recursion_record")
    return record
