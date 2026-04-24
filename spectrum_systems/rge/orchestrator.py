"""RGE Orchestrator - end-to-end composition of the pipeline.

Pipeline:
  analyze_repository  -> rge_analysis_record
  generate_roadmap    -> rge_roadmap_record           (filter applied per phase)
  red_team_roadmap    -> rge_redteam_record
  amend_roadmap       -> rge_amendment_record
  assess_trust        -> rge_trust_record             (gates execution)
  govern_recursion    -> rge_recursion_record         (per proposed phase)

Emits a top-level `rge_run_record` that references every child record.

Shadow trust mode queues the roadmap for human review and does NOT execute.
Warn-gated and autonomous modes pass execute=True; actual execution is the
caller's responsibility (RGE never mutates the repo directly).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.rge.analysis_engine import analyze_repository
from spectrum_systems.rge.rge_amender import amend_roadmap
from spectrum_systems.rge.rge_red_teamer import red_team_roadmap
from spectrum_systems.rge.recursion_governor import govern_recursion
from spectrum_systems.rge.roadmap_generator import generate_roadmap
from spectrum_systems.rge.trust_bootstrapper import assess_trust


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"RUN-{hashlib.sha256(raw.encode()).hexdigest()[:12].upper()}"


def run_rge(
    *,
    repo_root: str | Path,
    run_id: str,
    trace_id: str,
    roadmap_signal_bundle: dict[str, Any] | None = None,
    complexity_budgets: list[dict[str, Any]] | None = None,
    fragile_points: list[str] | None = None,
    mg_slices_present: list[str] | None = None,
    extra_candidates: list[dict[str, Any]] | None = None,
    current_leg_counts: dict[str, int] | None = None,
    session_budget_hours: float | None = None,
    oscillation_count: int = 0,
    additional_edges: list[tuple[str, str]] | None = None,
    confidence: float = 0.5,
    decision_history: list[dict[str, Any]] | None = None,
    adjudication_bundle: dict[str, Any] | None = None,
    prior_trust_mode: str = "shadow",
    current_recursion_depth: int = 0,
    ancestor_phase_names: list[str] | None = None,
    weekly_recursion_budget_used: int = 0,
) -> dict[str, Any]:
    """Run the full RGE pipeline end-to-end.

    The orchestrator never mutates the repo. It emits records; execution
    belongs to the governed promotion surface (PR gate).
    """
    analysis = analyze_repository(
        repo_root=repo_root,
        run_id=run_id,
        trace_id=trace_id,
        roadmap_signal_bundle=roadmap_signal_bundle,
        complexity_budgets=complexity_budgets,
        fragile_points=fragile_points,
        mg_slices_present=mg_slices_present,
    )

    roadmap = generate_roadmap(
        analysis=analysis,
        run_id=run_id,
        trace_id=trace_id,
        extra_candidates=extra_candidates,
        current_leg_counts=current_leg_counts,
    )

    redteam = red_team_roadmap(
        roadmap=roadmap,
        run_id=run_id,
        trace_id=trace_id,
        analysis=analysis,
        session_budget_hours=session_budget_hours,
    )

    amendment = amend_roadmap(
        roadmap=roadmap,
        redteam=redteam,
        run_id=run_id,
        trace_id=trace_id,
        oscillation_count=oscillation_count,
        additional_edges=additional_edges,
    )

    recommendation_id = str(roadmap.get("record_id", ""))
    trust = assess_trust(
        run_id=run_id,
        trace_id=trace_id,
        recommendation_id=recommendation_id,
        confidence=confidence,
        decision_history=decision_history,
        adjudication_bundle=adjudication_bundle,
        prior_mode=prior_trust_mode,
    )

    recursion_records: list[dict[str, Any]] = []
    for phase in roadmap.get("admitted_phases", []):
        rec = govern_recursion(
            run_id=run_id,
            trace_id=trace_id,
            proposed_phase_name=str(phase.get("name", "")),
            current_depth=current_recursion_depth,
            ancestor_phase_names=ancestor_phase_names,
            weekly_budget_used=weekly_recursion_budget_used,
        )
        recursion_records.append(rec)

    any_blocked = any(not r["allowed"] for r in recursion_records)
    any_admitted = len(roadmap.get("admitted_phases", [])) > 0

    execute = bool(trust["execute"] and not any_blocked and any_admitted)
    queued_for_human = trust["resolved_mode"] == "shadow" and any_admitted

    terminal_state: str
    if any_blocked or amendment["decision"] == "block":
        terminal_state = "blocked"
    elif queued_for_human:
        terminal_state = "queued_for_human"
    elif execute:
        terminal_state = "ready_for_merge"
    else:
        terminal_state = "no_action"

    record = {
        "artifact_type": "rge_run_record",
        "schema_version": "1.0.0",
        "record_id": _stable_id({
            "run_id": run_id,
            "roadmap": roadmap["record_id"],
            "trust": trust["record_id"],
        }),
        "run_id": run_id,
        "trace_id": trace_id,
        "created_at": _utc_now(),
        "analysis_record_id": analysis["record_id"],
        "roadmap_record_id": roadmap["record_id"],
        "redteam_record_id": redteam["record_id"],
        "amendment_record_id": amendment["record_id"],
        "trust_record_id": trust["record_id"],
        "recursion_record_ids": [r["record_id"] for r in recursion_records],
        "admitted_phase_count": len(roadmap.get("admitted_phases", [])),
        "blocked_proposal_count": len(roadmap.get("blocked_proposals", [])),
        "finding_count": redteam["finding_count"],
        "amendment_count": len(amendment["amendments"]),
        "resolved_trust_mode": trust["resolved_mode"],
        "execute": execute,
        "queued_for_human": queued_for_human,
        "terminal_state": terminal_state,
        "branch_update_allowed": terminal_state == "ready_for_merge",
    }

    validate_artifact(record, "rge_run_record")
    return {
        "run_record": record,
        "analysis_record": analysis,
        "roadmap_record": roadmap,
        "redteam_record": redteam,
        "amendment_record": amendment,
        "trust_record": trust,
        "recursion_records": recursion_records,
    }
