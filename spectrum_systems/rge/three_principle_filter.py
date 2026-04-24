"""Three-Principle Filter - sequential gate for all RGE roadmap phases.

Applies in order:
  [1] Phase Justification Gate   (Kill Complexity Early)        -> fail-closed
  [2] Loop Contribution Check    (Build Fewer, Stronger Loops)  -> fail-closed
  [3] Debuggability Gate         (Optimize for Debuggability)   -> return for rewrite

Only phases passing all three gates enter the roadmap. Gates 1+2 block.
Gate 3 returns specific gaps for correction.

Every admitted phase carries all three gate artifacts for audit trail.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from spectrum_systems.rge.debuggability_gate import assess_debuggability
from spectrum_systems.rge.loop_contribution_checker import (
    LoopContributionError,
    check_loop_contribution,
)
from spectrum_systems.rge.phase_justification_gate import (
    PhaseJustificationError,
    validate_phase_justification,
)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"FLT-{hashlib.sha256(raw.encode()).hexdigest()[:12].upper()}"


@dataclass
class FilterResult:
    phase_id: str
    phase_name: str
    admitted: bool
    block_gate: str | None
    block_reason: str | None
    justification_record: dict[str, Any] | None
    loop_record: dict[str, Any] | None
    debuggability_record: dict[str, Any] | None
    needs_rewrite: bool = False
    rewrite_gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "filter_result",
            "record_id": _stable_id({"phase_id": self.phase_id}),
            "created_at": _utc_now(),
            "phase_id": self.phase_id,
            "phase_name": self.phase_name,
            "admitted": self.admitted,
            "block_gate": self.block_gate,
            "block_reason": self.block_reason,
            "needs_rewrite": self.needs_rewrite,
            "rewrite_gaps": list(self.rewrite_gaps),
        }


def apply_three_principle_filter(
    phase: dict[str, Any],
    *,
    run_id: str,
    trace_id: str,
    active_drift_legs: list[str] | None = None,
    current_leg_counts: dict[str, int] | None = None,
) -> FilterResult:
    """Apply all three principles sequentially to a proposed phase.

    Short-circuits on first blocking gate. Gate 3 never blocks - returns
    rewrite gaps alongside admission.
    """
    phase_id = str(phase.get("phase_id", ""))
    name = str(phase.get("name", ""))

    try:
        j_record = validate_phase_justification(phase, run_id=run_id, trace_id=trace_id)
    except PhaseJustificationError as exc:
        return FilterResult(
            phase_id=phase_id,
            phase_name=name,
            admitted=False,
            block_gate="justification",
            block_reason=str(exc),
            justification_record=None,
            loop_record=None,
            debuggability_record=None,
        )

    try:
        l_record = check_loop_contribution(
            phase,
            run_id=run_id,
            trace_id=trace_id,
            active_drift_legs=active_drift_legs,
            current_leg_counts=current_leg_counts,
        )
    except LoopContributionError as exc:
        return FilterResult(
            phase_id=phase_id,
            phase_name=name,
            admitted=False,
            block_gate="loop",
            block_reason=str(exc),
            justification_record=j_record,
            loop_record=None,
            debuggability_record=None,
        )

    d_record = assess_debuggability(phase, run_id=run_id, trace_id=trace_id)
    needs_rewrite = d_record["decision"] != "pass"

    return FilterResult(
        phase_id=phase_id,
        phase_name=name,
        admitted=True,
        block_gate=None,
        block_reason=None,
        justification_record=j_record,
        loop_record=l_record,
        debuggability_record=d_record,
        needs_rewrite=needs_rewrite,
        rewrite_gaps=list(d_record.get("gaps", [])),
    )
