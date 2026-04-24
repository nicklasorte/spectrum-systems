"""RGE Self-Amender.

Consumes an `rge_redteam_record` and produces an `rge_amendment_record`
describing judgment-based amendments to the original roadmap. Amendments are
returned as records; the caller applies them (via governed promotion) after
review.

Behaviour:
  - Large amendments (>3 phases touched) -> recommend canary (10% first).
  - DAG validation: the amender never proposes edges that create cycles.
  - Oscillation guard: if the oscillation cycle count is >= 3, escalate.
  - A fresh phase is never added; only drops, reorder, or defer are suggested.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from spectrum_systems.contracts import validate_artifact

MAX_OSCILLATION_CYCLES = 3
CANARY_THRESHOLD = 3
CANARY_PERCENT = 10


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"RAM-{hashlib.sha256(raw.encode()).hexdigest()[:12].upper()}"


def _has_cycle(edges: list[tuple[str, str]]) -> bool:
    """Return True iff the directed graph defined by `edges` has a cycle."""
    graph: dict[str, list[str]] = {}
    nodes: set[str] = set()
    for src, dst in edges:
        graph.setdefault(src, []).append(dst)
        nodes.update({src, dst})

    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(n: str) -> bool:
        if n in visiting:
            return True
        if n in visited:
            return False
        visiting.add(n)
        for nxt in graph.get(n, []):
            if dfs(nxt):
                return True
        visiting.discard(n)
        visited.add(n)
        return False

    return any(dfs(n) for n in nodes)


def _derive_amendments(
    roadmap: dict[str, Any],
    redteam: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Derive amendments from a red-team record.

    Returns (amendments, touched_phase_ids).
    """
    amendments: list[dict[str, Any]] = []
    touched: set[str] = set()
    findings = redteam.get("findings") or []

    if not findings:
        return amendments, []

    for f in findings:
        fc = str(f.get("finding_class", ""))
        affected = [pid for pid in (f.get("affected_phases") or []) if pid]

        if fc == "same_leg_same_batch":
            for pid in affected[1:]:
                amendments.append({
                    "amendment_type": "defer",
                    "phase_id": pid,
                    "reason": f.get("statement", ""),
                    "owner": f.get("owner"),
                })
                touched.add(pid)
        elif fc == "complexity_on_freeze":
            for pid in affected:
                amendments.append({
                    "amendment_type": "drop",
                    "phase_id": pid,
                    "reason": f.get("statement", ""),
                    "owner": f.get("owner"),
                })
                touched.add(pid)
        elif fc == "deletion_guard_violation":
            for pid in affected:
                amendments.append({
                    "amendment_type": "revise",
                    "phase_id": pid,
                    "reason": "Add module citation in evidence_refs",
                    "owner": f.get("owner"),
                })
                touched.add(pid)
        elif fc == "circular_failure_chain":
            for pid in affected:
                amendments.append({
                    "amendment_type": "revise",
                    "phase_id": pid,
                    "reason": "Rewrite failure_prevented to avoid self-reference",
                    "owner": f.get("owner"),
                })
                touched.add(pid)
        elif fc == "red_team_pairing_missing":
            amendments.append({
                "amendment_type": "add_pair",
                "phase_id": "ALL",
                "reason": "Add a paired red-team or test phase to satisfy pairing",
                "owner": f.get("owner"),
            })
        elif fc == "mg_21_session_violation":
            amendments.append({
                "amendment_type": "split_session",
                "phase_id": "SESSION",
                "reason": f.get("statement", ""),
                "owner": f.get("owner"),
            })

    return amendments, sorted(touched)


def amend_roadmap(
    *,
    roadmap: dict[str, Any],
    redteam: dict[str, Any],
    run_id: str,
    trace_id: str,
    oscillation_count: int = 0,
    additional_edges: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Produce an rge_amendment_record from a roadmap + redteam record.

    Args:
        roadmap: rge_roadmap_record
        redteam: rge_redteam_record
        oscillation_count: how many amend cycles have already fired for this
            roadmap; 3+ triggers escalation
        additional_edges: any dependency edges the caller wants validated for
            cycle freedom

    Returns:
        schema-validated rge_amendment_record
    """
    amendments, touched = _derive_amendments(roadmap, redteam)
    escalate = oscillation_count >= MAX_OSCILLATION_CYCLES

    edges = list(additional_edges or [])
    dag_ok = not _has_cycle(edges)

    rollout = "full"
    if len(touched) > CANARY_THRESHOLD:
        rollout = f"canary_{CANARY_PERCENT}pct"

    if escalate:
        decision = "escalate"
    elif not dag_ok:
        decision = "block"
    elif not amendments:
        decision = "no_amendment"
    else:
        decision = "apply"

    record = {
        "artifact_type": "rge_amendment_record",
        "schema_version": "1.0.0",
        "record_id": _stable_id({"run_id": run_id, "count": len(amendments)}),
        "run_id": run_id,
        "trace_id": trace_id,
        "created_at": _utc_now(),
        "roadmap_record_id": str(roadmap.get("record_id", "")),
        "redteam_record_id": str(redteam.get("record_id", "")),
        "decision": decision,
        "amendments": amendments,
        "touched_phase_ids": touched,
        "rollout": rollout,
        "oscillation_count": oscillation_count,
        "oscillation_ceiling": MAX_OSCILLATION_CYCLES,
        "dag_ok": dag_ok,
        "escalated": escalate,
    }

    validate_artifact(record, "rge_amendment_record")
    return record
