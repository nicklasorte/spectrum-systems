"""RGE Red-Teamer.

Runs six classic red-team checks on a candidate roadmap and emits an
`rge_redteam_record`. Each finding is routed to its canonical 3LS owner via
`rqx_redteam_orchestrator.route_finding_owner`.

The six checks:
  1. RED-TEAM-PAIRING      - every ADD phase pairs with a TEST/RED phase
  2. CIRCULAR-FAILURE      - no phase references its own failure_prevented
  3. SAME-LEG-SAME-BATCH   - two phases cannot target the same leg in one batch
  4. COMPLEXITY-ON-FREEZE  - no ADD phases when a complexity budget is frozen
  5. DELETION-GUARD        - deletion phases must cite the module they delete
  6. MG-21-SESSION-REALISM - orchestrator session budget sanity check

Each RGE finding class is mapped to a canonical RQX finding class, then routed
through `rqx_redteam_orchestrator.route_finding_owner` to produce the
governed routing record (owner + routing_ref). Findings whose class has no
RQX mapping fall back to a generic "RGE" owner so nothing is silently dropped.

Findings are bucketed `must_fix | warn`:
  - must_fix: structural defects that block roadmap promotion
  - warn:     advisory signals that do not block (saturation, realism)

`decision` blocks iff at least one `must_fix` finding exists.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.rqx_redteam_orchestrator import (
    RQXRedTeamError,
    build_redteam_finding_record,
    route_finding_owner as rqx_route_finding_owner,
)


# Map RGE finding classes -> canonical RQX finding classes.
# RQX classes are: interpretation, repair_planning, decision_quality,
# enforcement_mismatch, execution_trace, trust_policy.
_RGE_TO_RQX_CLASS: dict[str, str] = {
    "red_team_pairing_missing":  "execution_trace",
    "circular_failure_chain":    "decision_quality",
    "same_leg_same_batch":       "repair_planning",
    "complexity_on_freeze":      "trust_policy",
    "deletion_guard_violation":  "enforcement_mismatch",
    "mg_21_session_violation":   "interpretation",
}

# Canonical RQX-class -> owner mapping (mirrors rqx_redteam_orchestrator._OWNER_BY_CLASS).
_RQX_OWNER_BY_CLASS: dict[str, str] = {
    "interpretation":       "RIL",
    "repair_planning":      "FRE",
    "decision_quality":     "CDE",
    "enforcement_mismatch": "SEL",
    "execution_trace":      "PQX",
    "trust_policy":         "TPA",
}

# Findings that block roadmap promotion (must_fix).
# Anything not listed here is advisory (warn).
_MUST_FIX_CLASSES: frozenset[str] = frozenset({
    "red_team_pairing_missing",
    "circular_failure_chain",
    "complexity_on_freeze",
    "deletion_guard_violation",
})

_FALLBACK_OWNER = "RGE"


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"RTR-{hashlib.sha256(raw.encode()).hexdigest()[:12].upper()}"


def route_finding_owner(finding_class: str) -> str:
    """Return canonical 3LS owner for an RGE finding class.

    Resolves the RGE class to its RQX canonical class, then to the canonical
    3LS owner. Unmapped classes fall back to 'RGE' so nothing is silently
    dropped. (See `_route_via_rqx` for the schema-validated routing record
    used on each finding emitted by `red_team_roadmap`.)
    """
    rqx_class = _RGE_TO_RQX_CLASS.get(finding_class)
    if rqx_class is None:
        return _FALLBACK_OWNER
    return _RQX_OWNER_BY_CLASS.get(rqx_class, _FALLBACK_OWNER)


def _route_via_rqx(
    *,
    rge_class: str,
    statement: str,
    affected_phases: list[Any],
    trace_id: str,
) -> dict[str, Any]:
    """Build a redteam_finding_record and route it through RQX.

    Returns a routing dict with `owner`, `routing_reason`, `routing_ref`,
    `finding_id`, and `rqx_class`. Falls back to a local owner record when
    the RGE class has no canonical RQX mapping or RQX rejects the input,
    so no finding is silently dropped.
    """
    rqx_class = _RGE_TO_RQX_CLASS.get(rge_class)
    if rqx_class is None:
        return {
            "owner": _FALLBACK_OWNER,
            "routing_reason": f"class:{rge_class}",
            "routing_ref": "redteam_finding_record:UNROUTED",
            "finding_id": "",
            "rqx_class": "",
            "rqx_routed": False,
        }

    exploit_refs = [str(p) for p in affected_phases if p] or [f"rge_class:{rge_class}"]
    bounded_scope = f"rge_red_teamer:{rge_class}"

    try:
        finding_record = build_redteam_finding_record(
            trace_id=trace_id,
            finding_class=rqx_class,
            finding_statement=statement or f"RGE {rge_class}",
            exploit_refs=exploit_refs,
            bounded_scope=bounded_scope,
        )
        routing = rqx_route_finding_owner(finding_record=finding_record)
    except RQXRedTeamError:
        return {
            "owner": _RQX_OWNER_BY_CLASS.get(rqx_class, _FALLBACK_OWNER),
            "routing_reason": f"class:{rge_class}",
            "routing_ref": "redteam_finding_record:RQX_REJECTED",
            "finding_id": "",
            "rqx_class": rqx_class,
            "rqx_routed": False,
        }

    return {
        "owner": routing["owner"],
        "routing_reason": f"class:{rge_class}",
        "routing_ref": routing["routing_ref"],
        "finding_id": finding_record["finding_id"],
        "rqx_class": rqx_class,
        "rqx_routed": True,
    }


def _check_red_team_pairing(phases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every 'add' phase should pair with a red-team / test / eval phase."""
    has_redteam = any(
        "red" in str(p.get("name", "")).lower()
        or "test" in str(p.get("name", "")).lower()
        or str(p.get("phase_type", "")).lower() in {"test", "redteam"}
        for p in phases
    )
    findings: list[dict[str, Any]] = []
    if not has_redteam and phases:
        findings.append({
            "finding_class": "red_team_pairing_missing",
            "statement": "Roadmap contains no red-team or test phase paired with admitted ADD phases.",
            "affected_phases": [p.get("phase_id") for p in phases],
        })
    return findings


def _check_circular_failures(phases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A phase should not cite itself as the failure it prevents."""
    findings: list[dict[str, Any]] = []
    for p in phases:
        name = str(p.get("name", "")).lower()
        failure = str(p.get("failure_prevented", "")).lower()
        if name and name in failure:
            findings.append({
                "finding_class": "circular_failure_chain",
                "statement": f"Phase '{p.get('phase_id')}' references its own name in failure_prevented.",
                "affected_phases": [p.get("phase_id")],
            })
    return findings


def _check_same_leg_same_batch(phases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Two non-strengthen/delete phases should not target the same leg."""
    findings: list[dict[str, Any]] = []
    leg_to_phase: dict[str, list[str]] = {}
    for p in phases:
        if str(p.get("phase_type", "")).lower() in {"delete", "deletion", "strengthen"}:
            continue
        leg = str(p.get("loop_leg", "")).upper()
        if not leg:
            continue
        leg_to_phase.setdefault(leg, []).append(p.get("phase_id", ""))
    for leg, pids in leg_to_phase.items():
        if len(pids) > 1:
            findings.append({
                "finding_class": "same_leg_same_batch",
                "statement": (
                    f"Leg {leg} has {len(pids)} ADD phases in one batch. "
                    "Stagger across batches to preserve loop health."
                ),
                "affected_phases": pids,
            })
    return findings


def _check_complexity_on_freeze(
    phases: list[dict[str, Any]],
    analysis: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """No new ADD phases should be proposed while a module is budget-frozen."""
    findings: list[dict[str, Any]] = []
    if not analysis:
        return findings
    frozen = {
        module
        for module, b in (analysis.get("complexity_budget_by_module") or {}).items()
        if str(b.get("budget_status", "")).lower() == "exceeded"
    }
    if not frozen:
        return findings
    for p in phases:
        if str(p.get("phase_type", "")).lower() in {"delete", "deletion", "strengthen"}:
            continue
        findings.append({
            "finding_class": "complexity_on_freeze",
            "statement": (
                f"ADD phase '{p.get('phase_id')}' proposed while "
                f"{sorted(frozen)} exceed complexity budget."
            ),
            "affected_phases": [p.get("phase_id")],
        })
    return findings


def _check_deletion_guard(phases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deletion phases must cite the module they delete in evidence_refs."""
    findings: list[dict[str, Any]] = []
    for p in phases:
        phase_type = str(p.get("phase_type", "")).lower()
        if phase_type not in {"delete", "deletion"}:
            continue
        refs = [str(r) for r in (p.get("evidence_refs") or [])]
        cites_module = any("module" in r.lower() or "/" in r or ":" in r for r in refs)
        if not cites_module or not refs:
            findings.append({
                "finding_class": "deletion_guard_violation",
                "statement": (
                    f"Deletion phase '{p.get('phase_id')}' does not cite the "
                    "module under evidence_refs."
                ),
                "affected_phases": [p.get("phase_id")],
            })
    return findings


def _check_mg_21_session_realism(
    phases: list[dict[str, Any]],
    session_budget_hours: float | None,
) -> list[dict[str, Any]]:
    """MG-21: session must not exceed 8h of wall clock for typical phase count."""
    findings: list[dict[str, Any]] = []
    if session_budget_hours is None:
        return findings
    if session_budget_hours > 8.0 and len(phases) >= 1:
        findings.append({
            "finding_class": "mg_21_session_violation",
            "statement": (
                f"Session budget {session_budget_hours}h exceeds MG-21 realism "
                "ceiling (8h). Split the roadmap into smaller sessions."
            ),
            "affected_phases": [p.get("phase_id") for p in phases],
        })
    return findings


def red_team_roadmap(
    *,
    roadmap: dict[str, Any],
    run_id: str,
    trace_id: str,
    analysis: dict[str, Any] | None = None,
    session_budget_hours: float | None = None,
) -> dict[str, Any]:
    """Run all six red-team checks against an `rge_roadmap_record`.

    Returns a schema-validated `rge_redteam_record`. Findings are routed to
    their canonical 3LS owner; no finding is silently dropped.
    """
    phases: list[dict[str, Any]] = list(roadmap.get("admitted_phases") or [])

    raw_findings: list[dict[str, Any]] = []
    raw_findings.extend(_check_red_team_pairing(phases))
    raw_findings.extend(_check_circular_failures(phases))
    raw_findings.extend(_check_same_leg_same_batch(phases))
    raw_findings.extend(_check_complexity_on_freeze(phases, analysis))
    raw_findings.extend(_check_deletion_guard(phases))
    raw_findings.extend(_check_mg_21_session_realism(phases, session_budget_hours))

    routed: list[dict[str, Any]] = []
    must_fix_count = 0
    warn_count = 0
    for f in raw_findings:
        rge_class = f["finding_class"]
        routing = _route_via_rqx(
            rge_class=rge_class,
            statement=f["statement"],
            affected_phases=f["affected_phases"],
            trace_id=trace_id,
        )
        is_must_fix = rge_class in _MUST_FIX_CLASSES
        if is_must_fix:
            must_fix_count += 1
        else:
            warn_count += 1
        routed.append({
            "finding_class": rge_class,
            "statement": f["statement"],
            "affected_phases": f["affected_phases"],
            "owner": routing["owner"],
            "routing_reason": routing["routing_reason"],
            "rqx_routing": {
                "rqx_class": routing["rqx_class"],
                "routing_ref": routing["routing_ref"],
                "finding_id": routing["finding_id"],
                "rqx_routed": routing["rqx_routed"],
            },
            "must_fix": is_must_fix,
        })

    decision = "block" if must_fix_count > 0 else "pass"

    record = {
        "artifact_type": "rge_redteam_record",
        "schema_version": "1.1.0",
        "record_id": _stable_id({"run_id": run_id, "findings": len(routed)}),
        "run_id": run_id,
        "trace_id": trace_id,
        "created_at": _utc_now(),
        "roadmap_record_id": str(roadmap.get("record_id", "")),
        "decision": decision,
        "finding_count": len(routed),
        "must_fix_count": must_fix_count,
        "warn_count": warn_count,
        "roadmap_approved": must_fix_count == 0,
        "findings": routed,
        "checks_run": [
            "red_team_pairing",
            "circular_failures",
            "same_leg_same_batch",
            "complexity_on_freeze",
            "deletion_guard",
            "mg_21_session_realism",
        ],
    }

    validate_artifact(record, "rge_redteam_record")
    return record
