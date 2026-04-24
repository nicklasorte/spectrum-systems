"""RGE Roadmap Generator.

Consumes an `rge_analysis_record`, synthesizes candidate phases, routes each
through the three-principle filter, and emits an `rge_roadmap_record` that
only contains admitted phases. Blocked proposals are retained for audit.

Behaviour:
  - If complexity is exceeded for a module -> generate a DELETE phase.
  - If a loop leg is in active drift -> generate a STRENGTHEN-<leg> phase.
  - Additional candidates may be supplied via `extra_candidates`.

The generator never mutates anything; it only produces records.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.roadmap_stop_reasons import (
    CANONICAL_STOP_REASONS,
    STOP_REASON_DIMINISHING_RETURNS,
    STOP_REASON_INVALID_ROADMAP_STATE,
    STOP_REASON_PROGRAM_DRIFT_DETECTED,
    STOP_REASON_RISK_ACCUMULATION_EXCEEDED,
)
from spectrum_systems.rge.three_principle_filter import (
    FilterResult,
    apply_three_principle_filter,
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
    return f"RMR-{hashlib.sha256(raw.encode()).hexdigest()[:12].upper()}"


def _content_hash(phases: list[dict[str, Any]]) -> str:
    raw = json.dumps(phases, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _build_delete_phase(module: str, budget: dict[str, Any]) -> dict[str, Any]:
    current = budget.get("current_complexity", 0)
    baseline = budget.get("baseline_complexity", 0)
    drop = max(1, int(current) - int(baseline))
    return {
        "phase_id": f"DEL-{module.replace('/', '-').upper()}",
        "name": f"Delete dead-weight under {module}",
        "phase_type": "delete",
        "failure_prevented": (
            f"Complexity budget exceeded in {module} - sustained regressions "
            "drive abstraction_growth above threshold"
        ),
        "signal_improved": (
            f"complexity_score drops by {drop} points in {module}, returning to baseline"
        ),
        "loop_leg": "TPA",
        "evidence_refs": [
            f"complexity_budget:{module}",
            f"module_fragility:{module}",
        ],
        "runbook": "docs/runbooks/rge_justification_gate_failures.md",
        "stop_reason": STOP_REASON_RISK_ACCUMULATION_EXCEEDED,
    }


def _build_strengthen_phase(leg: str) -> dict[str, Any]:
    return {
        "phase_id": f"STR-{leg}",
        "name": f"STRENGTHEN-{leg} resolve active drift",
        "phase_type": "strengthen",
        "failure_prevented": (
            f"Loop leg {leg} is in active drift - downstream decisions lose evidence "
            "when drift signals are stale"
        ),
        "signal_improved": (
            f"drift severity on leg {leg} drops to 0 warnings per day over the "
            "next 7 days"
        ),
        "loop_leg": leg,
        "evidence_refs": [
            f"drift_signal_record:{leg}",
            f"roadmap_signal_bundle:{leg}",
        ],
        "runbook": "docs/runbooks/rge_loop_contribution_failures.md",
        "stop_reason": STOP_REASON_PROGRAM_DRIFT_DETECTED,
    }


def _improvement_fingerprint(phase: dict[str, Any]) -> bool:
    """Require that the phase declares at least one governance-relevant signal.

    Blocks phases with no governance/eval/provenance/control keyword in either
    failure_prevented or signal_improved. This is a cheap last-mile sanity
    check before the filter.
    """
    haystack = " ".join(
        str(phase.get(k, "")) for k in ("failure_prevented", "signal_improved")
    ).lower()
    signals = (
        "govern", "eval", "provenance", "control", "lineage",
        "complexity", "drift", "coverage", "budget", "reliab",
    )
    return any(s in haystack for s in signals)


def generate_roadmap(
    *,
    analysis: dict[str, Any],
    run_id: str,
    trace_id: str,
    extra_candidates: list[dict[str, Any]] | None = None,
    current_leg_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Generate a candidate roadmap from an rge_analysis_record.

    Returns a schema-validated rge_roadmap_record.
    """
    candidates: list[dict[str, Any]] = []

    for module, budget in (analysis.get("complexity_budget_by_module") or {}).items():
        if str(budget.get("budget_status", "")).lower() == "exceeded":
            candidates.append(_build_delete_phase(module, budget))

    for leg in analysis.get("active_drift_legs") or []:
        candidates.append(_build_strengthen_phase(leg))

    for extra in extra_candidates or []:
        candidates.append(dict(extra))

    leg_counts = (
        current_leg_counts
        if current_leg_counts is not None
        else analysis.get("leg_saturation") or {}
    )
    drift_legs = analysis.get("active_drift_legs") or []

    admitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for phase in candidates:
        if not _improvement_fingerprint(phase):
            blocked.append({
                "phase_id": phase.get("phase_id"),
                "phase_name": phase.get("name"),
                "block_gate": "improvement_fingerprint",
                "block_reason": (
                    "Phase does not reference a governance/eval/provenance/control/"
                    "lineage/complexity/drift/coverage/budget/reliability signal."
                ),
            })
            continue

        result: FilterResult = apply_three_principle_filter(
            phase,
            run_id=run_id,
            trace_id=trace_id,
            active_drift_legs=drift_legs,
            current_leg_counts=leg_counts,
        )

        if result.admitted:
            entry = dict(phase)
            entry["filter_result"] = result.to_dict()
            entry["needs_rewrite"] = result.needs_rewrite
            entry["rewrite_gaps"] = list(result.rewrite_gaps)
            admitted.append(entry)
        else:
            blocked.append(asdict(result) | {
                "justification_record": None,
                "loop_record": None,
                "debuggability_record": None,
            })

    phase_hash = _content_hash(admitted)

    record = {
        "artifact_type": "rge_roadmap_record",
        "schema_version": "1.0.0",
        "record_id": _stable_id({"run_id": run_id, "hash": phase_hash}),
        "run_id": run_id,
        "trace_id": trace_id,
        "created_at": _utc_now(),
        "analysis_record_id": str(analysis.get("record_id", "")),
        "admitted_phases": admitted,
        "blocked_proposals": blocked,
        "candidate_count": len(candidates),
        "admitted_count": len(admitted),
        "blocked_count": len(blocked),
        "content_hash": phase_hash,
        "stop_reason_catalog": list(CANONICAL_STOP_REASONS),
        "diminishing_returns_sentinel": STOP_REASON_DIMINISHING_RETURNS,
        "invalid_state_sentinel": STOP_REASON_INVALID_ROADMAP_STATE,
    }

    validate_artifact(record, "rge_roadmap_record")
    return record
