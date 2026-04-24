"""RGE Loop Contribution Checker - Principle 2: Build Fewer, Stronger Loops.

Before a phase is added to a loop leg, verifies:
  1. The leg is canonical (AEX/PQX/EVL/TPA/CDE/SEL/REP/LIN/OBS/SLO)
  2. The leg is not in active drift - fix drift first, then add
  3. The leg is not saturated (max 8 contributors - strengthen existing before adding)

Wires into: roadmap_signal_steering.py (active drift signals)
Emits: loop_contribution_record
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from spectrum_systems.contracts import validate_artifact

CANONICAL_LOOP_LEGS = frozenset({
    "AEX", "PQX", "EVL", "TPA", "CDE", "SEL",
    "REP", "LIN", "OBS", "SLO",
})

MAX_SYSTEMS_PER_LEG = 8


class LoopContributionError(ValueError):
    """Raised when a phase fails the loop contribution check (fail-closed)."""


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"LCR-{hashlib.sha256(raw.encode()).hexdigest()[:12].upper()}"


def get_active_drift_legs(
    roadmap_signal_bundle: dict[str, Any] | None = None,
) -> list[str]:
    """Extract active drift legs from a roadmap signal bundle.

    When the bundle is missing, returns []. When present, maps drift findings
    to their affected loop legs (best-effort via the component name).
    """
    if not roadmap_signal_bundle:
        return []
    findings = roadmap_signal_bundle.get("drift_findings") or roadmap_signal_bundle.get("findings") or []
    legs: set[str] = set()
    for f in findings:
        severity = str(f.get("severity", "")).lower()
        if severity in {"none", ""}:
            continue
        component = str(f.get("affected_component", "")).upper()
        for leg in CANONICAL_LOOP_LEGS:
            if leg in component:
                legs.add(leg)
    return sorted(legs)


def check_loop_contribution(
    phase: dict[str, Any],
    *,
    run_id: str,
    trace_id: str,
    active_drift_legs: list[str] | None = None,
    current_leg_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Gate a proposed phase against Principle 2.

    Args:
        phase: must contain phase_id, name, loop_leg; may contain phase_type
        run_id, trace_id: for artifact lineage
        active_drift_legs: legs currently in drift (from roadmap_signal_steering)
        current_leg_counts: systems currently feeding each leg

    Returns:
        loop_contribution_record (schema-validated)

    Raises:
        LoopContributionError: on any loop check failure (fail-closed)
    """
    loop_leg = str(phase.get("loop_leg", "")).strip().upper()
    phase_id = str(phase.get("phase_id", "")).strip()
    name = str(phase.get("name", "")).strip()
    phase_type = str(phase.get("phase_type", "")).lower()
    is_deletion = phase_type == "delete" or phase_type == "deletion"
    is_strengthen = phase_type == "strengthen" or name.upper().startswith("STRENGTHEN-")

    drift_legs = {str(x).upper() for x in (active_drift_legs or [])}
    leg_counts = {str(k).upper(): int(v) for k, v in (current_leg_counts or {}).items()}

    errors: list[str] = []
    warnings: list[str] = []

    if loop_leg not in CANONICAL_LOOP_LEGS:
        errors.append(
            f"'{loop_leg}' is not a canonical loop leg - "
            f"must be one of: {sorted(CANONICAL_LOOP_LEGS)}"
        )
    else:
        if loop_leg in drift_legs and not is_strengthen and not is_deletion:
            errors.append(
                f"Loop leg '{loop_leg}' is in active drift. "
                f"Resolve drift before adding phases to this leg. "
                f"Propose a STRENGTHEN-{loop_leg} phase first."
            )

        if not is_deletion and not is_strengthen:
            count = leg_counts.get(loop_leg, 0)
            if count >= MAX_SYSTEMS_PER_LEG:
                errors.append(
                    f"Loop leg '{loop_leg}' is saturated "
                    f"({count}/{MAX_SYSTEMS_PER_LEG} contributors). "
                    f"Strengthen an existing contributor instead of adding a new one."
                )
            elif count >= MAX_SYSTEMS_PER_LEG - 2:
                warnings.append(
                    f"Loop leg '{loop_leg}' approaching saturation "
                    f"({count}/{MAX_SYSTEMS_PER_LEG}). Consider strengthening existing."
                )

    decision = "block" if errors else "allow"

    record = {
        "artifact_type": "loop_contribution_record",
        "schema_version": "1.0.0",
        "record_id": _stable_id({"phase_id": phase_id, "run_id": run_id}),
        "run_id": run_id,
        "trace_id": trace_id,
        "created_at": _utc_now(),
        "phase_id": phase_id,
        "phase_name": name,
        "loop_leg": loop_leg,
        "decision": decision,
        "errors": errors,
        "warnings": warnings,
        "active_drift_legs": sorted(drift_legs),
        "leg_saturation": {k: v for k, v in leg_counts.items() if k in CANONICAL_LOOP_LEGS},
        "principle": "build_fewer_stronger_loops",
    }

    validate_artifact(record, "loop_contribution_record")

    if errors:
        bullets = "\n".join(f"  - {e}" for e in errors)
        raise LoopContributionError(
            f"Phase '{name}' ({phase_id}) blocked by Principle 2 - "
            f"loop contribution check:\n{bullets}"
        )

    return record
