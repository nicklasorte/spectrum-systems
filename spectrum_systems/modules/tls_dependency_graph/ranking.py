"""TLS-04 — Dependency-aware priority recommendation_signal builder.

This module is **observer-only**: it emits a ranked recommendation_signal
artifact. It owns no closure, advancement, or compliance authority. CDE,
GOV, SEL, and PRA retain those responsibilities. The artifact produced here
is an input to canonical owners, never a substitute for them.

Inputs (all governed artifacts):

* Phase 0 dependency graph
* Phase 1 evidence attachment
* Phase 2 classification
* Phase 3 trust-gap signal report

Output: ``system_dependency_priority_report`` artifact, including the top 5
systems with rank, action, why_now, trust_gap_signals, dependencies, unlocks,
finish definition, and next prompt.

Determinism contract:
* Score is computed from explicit, weighted signals (no model, no random).
* Tie-break: higher MVP-spine rank first, then lower system_id alphabetically.
* No ``unknown`` candidate appears in the top 5 unless every other candidate
  was already exhausted — in which case the row carries an explicit
  ``unknown_justification`` string.
* Hardening (active systems with gap signals) is ranked before expansion
  (h_slice or unknown).

Priority order (descending):
1. MVP spine dependency
2. Trust-boundary importance
3. Downstream unlock value
4. Partial completion
5. Risk-if-deferred signal

Penalties:
* New capability without trust gain
* Deprecated systems
* Unknown systems
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


SCHEMA_VERSION = "tls-04.v1"


def _generated_at_iso() -> str:
    """Return a UTC ISO-8601 timestamp for the priority artifact.

    D3L-DATA-REGISTRY-01: the dashboard freshness gate must be able to
    assert the artifact was produced recently. The TLS pipeline owns the
    timestamp so the dashboard never has to fall back to file mtime.

    Tests can pin the value via ``TLS_GENERATED_AT_OVERRIDE`` to keep
    fixtures deterministic.
    """
    override = os.environ.get("TLS_GENERATED_AT_OVERRIDE")
    if override:
        return override
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# MVP spine — systems on the canonical loop carry max spine weight; overlays
# carry second-tier weight; everything else is non-spine.
SPINE_WEIGHT = 100
OVERLAY_WEIGHT = 60
NON_SPINE_WEIGHT = 0

# Trust-boundary importance — systems whose role is a control/compliance
# boundary score higher because their gap signals stall advancement_signal
# evaluation downstream.
TRUST_BOUNDARY_HIGH = {"EVL", "TPA", "CDE", "SEL", "GOV", "PRA"}
TRUST_BOUNDARY_MED = {"REP", "LIN", "OBS", "SLO", "SEC"}

PENALTY_DEPRECATED = -200
PENALTY_UNKNOWN = -150
PENALTY_NEW_CAP_NO_TRUST_GAIN = -50

WEIGHT_TRUST_GAP = 8  # per failing signal on an active system
WEIGHT_PARTIAL_COMPLETION = 5
WEIGHT_DOWNSTREAM_UNLOCK = 4

ACTIVE_CLASSES = {"active_system", "h_slice"}
SAFE_SIGNAL_VALUES = {
    "ready_signal",
    "caution_signal",
    "blocked_signal",
    "unknown_signal",
    "prerequisite_signal",
    "recommendation",
    "prioritization",
    "finding",
    "observation",
}


def _index(rows: List[Dict], key: str) -> Dict[str, Dict]:
    return {r[key]: r for r in rows}


def _spine_position(canonical_loop: List[str], canonical_overlays: List[str], sid: str) -> Tuple[int, int]:
    """Return (spine_weight, position_index) — lower position_index = earlier on loop."""

    if sid in canonical_loop:
        return SPINE_WEIGHT, canonical_loop.index(sid)
    if sid in canonical_overlays:
        return OVERLAY_WEIGHT, len(canonical_loop) + canonical_overlays.index(sid)
    return NON_SPINE_WEIGHT, len(canonical_loop) + len(canonical_overlays) + 100


def _trust_boundary_score(sid: str) -> int:
    if sid in TRUST_BOUNDARY_HIGH:
        return 80
    if sid in TRUST_BOUNDARY_MED:
        return 50
    return 0


def _downstream_unlock_score(graph: Dict, sid: str) -> Tuple[int, List[str]]:
    """Count active systems that list `sid` as upstream — those are unlocked once
    `sid` is healthy. Returns (count, list_of_unlocked_ids)."""

    unlocks: List[str] = []
    for node in graph.get("active_systems") or []:
        if node["system_id"] == sid:
            continue
        if sid in (node.get("upstream") or []):
            unlocks.append(node["system_id"])
    return len(unlocks), sorted(unlocks)


def _partial_completion_score(evidence_row: Dict, gap_row: Dict) -> int:
    """Higher score = more partial (worth finishing) but not zero (worth starting)."""

    if not evidence_row or not gap_row:
        return 0
    has_modules = len(evidence_row.get("evidence", {}).get("modules", [])) > 0
    has_tests = len(evidence_row.get("evidence", {}).get("tests", [])) > 0
    has_schemas = len(evidence_row.get("evidence", {}).get("schemas", [])) > 0
    if has_modules and not (has_tests and has_schemas):
        return 1
    return 0


def _risk_if_deferred_score(gap_row: Dict) -> int:
    failing = gap_row.get("failing_signals") or []
    weight = 0
    if "missing_eval" in failing:
        weight += 3
    if "missing_control" in failing:
        weight += 3
    if "missing_enforcement_signal" in failing:
        weight += 3
    if "missing_lineage" in failing:
        weight += 2
    if "missing_replay" in failing:
        weight += 2
    if "missing_observability" in failing:
        weight += 1
    if "missing_readiness_evidence" in failing:
        weight += 1
    return weight


def _action_for(classification: str, gap_row: Dict, partial: int) -> str:
    failing = gap_row.get("failing_signals") or []
    if classification == "deprecated":
        return "skip:deprecated"
    if classification == "future":
        return "defer:future_placeholder"
    if classification == "unknown":
        return "investigate:classify_or_reject"
    if classification == "support_capability":
        return "stabilize_support" if failing else "no_action"
    if not failing:
        return "no_action"
    if partial:
        return "finish_hardening"
    return "harden_authority"


def _why_now(
    sid: str,
    gap_row: Dict,
    spine_weight: int,
    boundary_score: int,
    unlocks: List[str],
) -> str:
    parts: List[str] = []
    if spine_weight == SPINE_WEIGHT:
        parts.append("on canonical loop")
    elif spine_weight == OVERLAY_WEIGHT:
        parts.append("canonical overlay")
    if boundary_score >= 80:
        parts.append("trust-boundary authority")
    elif boundary_score >= 50:
        parts.append("trust supporting authority")
    failing = gap_row.get("failing_signals") or []
    if failing:
        parts.append(f"{len(failing)} trust-gap signals: {', '.join(failing[:3])}")
    if unlocks:
        parts.append(f"unlocks {len(unlocks)} downstream system(s)")
    return "; ".join(parts) or "no immediate priority signal"


def _finish_definition(gap_row: Dict, classification: str) -> str:
    if classification == "deprecated":
        return "leave deprecated; no finish work"
    failing = gap_row.get("failing_signals") or []
    if not failing:
        return "evidence-backed: no gap signals; verify by re-running TLS pipeline"
    return "all of: " + ", ".join(f"resolve signal({s})" for s in failing)


def _next_prompt(sid: str, classification: str, gap_row: Dict) -> str:
    failing = gap_row.get("failing_signals") or []
    if classification == "deprecated":
        return f"NO-OP — {sid} is deprecated."
    if not failing:
        return f"NO-OP — {sid} has no detected trust-gap signals."
    return (
        f"Run TLS-FIX-{sid}: resolve observed trust-gap signals {failing} on system "
        f"{sid} (class={classification}). Produce a fail-closed schema-bound "
        f"artifact for each resolved signal. Update tests."
    )


def _format_system_list(system_ids: List[str]) -> str:
    return ", ".join(system_ids) if system_ids else "none"


def _requested_explanations(
    sid: str,
    classification: str,
    global_rank: Optional[int],
    global_row: Optional[Dict],
    prereqs: List[str],
    canonical_loop: List[str],
    in_registry: bool,
    reason: str,
) -> Dict[str, str]:
    trust_signals = list((global_row or {}).get("trust_gap_signals") or [])
    if global_row is None:
        return {
            "rank_explanation": (
                f"{sid} is unknown_signal because registry and evidence are insufficient; "
                "the candidate is not present in TLS candidate rows."
            ),
            "prerequisite_explanation": "Unknown prerequisites: retrieve registry/evidence rows first.",
            "safe_next_action": "finding: retrieve registry + evidence and re-run TLS pipeline.",
            "build_now_assessment": "blocked_signal",
            "why_not_higher": "unknown_signal: unresolved candidate evidence prevents higher confidence ranking.",
            "why_not_lower": "prioritization: included because it was explicitly requested.",
            "minimum_safe_prompt_scope": "finding: classify candidate only; avoid build changes.",
            "dependency_warning_level": "unknown_signal",
            "evidence_summary": "observation: no classification/evidence row found for this candidate.",
        }

    evidence_count = global_row.get("score_components", {}).get("gap_score", 0)
    is_build_now_safe = len(prereqs) == 0 and classification != "unknown"
    if classification == "unknown":
        build_now_assessment = "blocked_signal"
        warning_level = "unknown_signal"
        safe_scope = "finding: retrieve registry/evidence only."
    elif prereqs:
        build_now_assessment = "prerequisite_signal"
        warning_level = "prerequisite_signal"
        safe_scope = f"prerequisite_signal: harden prerequisite systems only ({_format_system_list(prereqs)})."
    elif trust_signals:
        build_now_assessment = "caution_signal"
        warning_level = "caution_signal"
        safe_scope = f"recommendation: single-system hardening for {sid} trust-gap signals."
    else:
        build_now_assessment = "ready_signal"
        warning_level = "ready_signal"
        safe_scope = f"recommendation: minimal single-system scope for {sid}."

    rank_reason_parts: List[str] = [
        f"prioritization: {sid} has global_rank={global_rank} in deterministic TLS ranking."
    ]
    if classification == "unknown":
        rank_reason_parts.append("unknown_signal: registry/evidence is insufficient for active classification.")
    if prereqs:
        rank_reason_parts.append(
            f"prerequisite_signal: higher-ranked prerequisites detected ({_format_system_list(prereqs)})."
        )
    if sid == "H01":
        h_slice_state = "h_slice" if classification == "h_slice" else "non_h_slice"
        rank_reason_parts.append(
            f"observation: H01 is {h_slice_state}; canonical dependencies include {_format_system_list(prereqs)}."
        )
    if sid == "HOP":
        rank_reason_parts.append(
            "caution_signal: HOP cannot bypass EVL/TPA/CDE/SEL trust pathways."
        )
    if sid == "RFX":
        registry_state = "registry-active" if in_registry else "repo-detected-only"
        rank_reason_parts.append(f"observation: RFX is {registry_state}.")
    if sid in {"MET", "METS"} and classification != "active_system":
        rank_reason_parts.append("unknown_signal: MET/METS remains ambiguous unless proven active.")

    prereq_explanation = (
        f"prerequisite_signal: finish {_format_system_list(prereqs)} first."
        if prereqs
        else "ready_signal: no higher-ranked active upstream prerequisites detected."
    )
    if sid in {"MET", "METS"} and classification != "active_system":
        prereq_explanation += " unknown_signal: ambiguous candidate state must be hardened first."

    if is_build_now_safe:
        safe_next_action = f"recommendation: build {sid} now with {safe_scope}"
    else:
        harden_targets = _format_system_list(prereqs) if prereqs else "registry/evidence classification"
        safe_next_action = f"recommendation: harden {harden_targets} before build scope on {sid}."

    why_not_higher_parts: List[str] = []
    if prereqs:
        why_not_higher_parts.append(f"prerequisite_signal: ranked behind prerequisites {_format_system_list(prereqs)}")
    if classification == "unknown":
        why_not_higher_parts.append("unknown_signal: candidate lacks proven registry/evidence activity")
    if sid in {"MET", "METS"} and classification != "active_system":
        why_not_higher_parts.append("observation: MET/METS ambiguity penalty applies")
    if sid == "RFX" and not in_registry:
        why_not_higher_parts.append("observation: repo-detected-only candidate carries uncertainty")
    if not why_not_higher_parts:
        why_not_higher_parts.append("observation: no stronger upstream score signal identified")

    why_not_lower = (
        "prioritization: requested candidate remains in ranked set with explicit signals."
        if global_rank is not None
        else "finding: unresolved candidate retained for operator visibility."
    )
    evidence_summary = (
        f"observation: classification={classification}; reason={reason}; trust_signals={_format_system_list(trust_signals)}; "
        f"canonical_loop_member={'yes' if sid in canonical_loop else 'no'}; gap_score={evidence_count}."
    )

    payload = {
        "rank_explanation": " ".join(rank_reason_parts),
        "prerequisite_explanation": prereq_explanation,
        "safe_next_action": safe_next_action,
        "build_now_assessment": build_now_assessment,
        "why_not_higher": "; ".join(why_not_higher_parts),
        "why_not_lower": why_not_lower,
        "minimum_safe_prompt_scope": safe_scope,
        "dependency_warning_level": warning_level,
        "evidence_summary": evidence_summary,
    }
    for field in ("build_now_assessment", "dependency_warning_level"):
        if payload[field] not in SAFE_SIGNAL_VALUES:
            raise ValueError(f"{field} must use observer-safe values only")
    return payload


def rank_systems(
    dependency_graph: Dict,
    evidence_attachment: Dict,
    classification: Dict,
    trust_gaps: Dict,
    top_n: int = 5,
    requested_candidates: Optional[Sequence[str]] = None,
) -> Dict:
    canonical_loop = list(dependency_graph.get("canonical_loop") or [])
    canonical_overlays = list(dependency_graph.get("canonical_overlays") or [])
    candidates_idx = _index(classification.get("candidates") or [], "system_id")
    evidence_idx = _index(evidence_attachment.get("systems") or [], "system_id")
    gaps_idx = _index(trust_gaps.get("systems") or [], "system_id")

    if not candidates_idx:
        raise ValueError("classification has no candidates; cannot rank")
    if not gaps_idx:
        raise ValueError("trust_gaps has no systems; cannot rank")

    rows: List[Dict] = []
    for sid in sorted(candidates_idx):
        cand = candidates_idx[sid]
        gap_row = gaps_idx.get(sid) or {"failing_signals": [], "gap_count": 0, "gaps_evaluated": 0, "trust_state": "unknown"}
        ev_row = evidence_idx.get(sid) or {}

        spine_weight, position_index = _spine_position(canonical_loop, canonical_overlays, sid)
        boundary_score = _trust_boundary_score(sid)
        unlock_count, unlocks = _downstream_unlock_score(dependency_graph, sid)
        partial_score = _partial_completion_score(ev_row, gap_row)
        risk_score = _risk_if_deferred_score(gap_row)
        gap_score = (gap_row.get("gap_count") or 0) * WEIGHT_TRUST_GAP if cand["classification"] in ACTIVE_CLASSES else 0
        unlock_score = unlock_count * WEIGHT_DOWNSTREAM_UNLOCK
        partial_pts = partial_score * WEIGHT_PARTIAL_COMPLETION

        score = spine_weight + boundary_score + gap_score + unlock_score + partial_pts + risk_score

        # Penalties
        penalties: List[str] = []
        if cand["classification"] == "deprecated":
            score += PENALTY_DEPRECATED
            penalties.append("deprecated")
        if cand["classification"] == "unknown":
            score += PENALTY_UNKNOWN
            penalties.append("unknown")
        if cand["classification"] in ACTIVE_CLASSES and gap_row.get("gap_count", 0) == 0 and unlock_count == 0:
            # New capability without trust gain
            score += PENALTY_NEW_CAP_NO_TRUST_GAIN
            penalties.append("new_capability_without_trust_gain")

        action = _action_for(cand["classification"], gap_row, partial_score)

        rows.append(
            {
                "system_id": sid,
                "classification": cand["classification"],
                "score": score,
                "score_components": {
                    "spine_weight": spine_weight,
                    "boundary_score": boundary_score,
                    "gap_score": gap_score,
                    "unlock_score": unlock_score,
                    "partial_score": partial_pts,
                    "risk_score": risk_score,
                },
                "penalties": penalties,
                "spine_position_index": position_index,
                "action": action,
                "why_now": _why_now(sid, gap_row, spine_weight, boundary_score, unlocks),
                "trust_gap_signals": list(gap_row.get("failing_signals") or []),
                "dependencies": {
                    "upstream": list((next((n for n in dependency_graph.get("active_systems") or [] if n["system_id"] == sid), {}) or {}).get("upstream", [])),
                    "downstream": list((next((n for n in dependency_graph.get("active_systems") or [] if n["system_id"] == sid), {}) or {}).get("downstream", [])),
                },
                "unlocks": unlocks,
                "finish_definition": _finish_definition(gap_row, cand["classification"]),
                "next_prompt": _next_prompt(sid, cand["classification"], gap_row),
                "trust_state": gap_row.get("trust_state", "unknown"),
            }
        )

    # Deterministic sort. Active hardening always before expansion within the
    # same score band: when tied on score, active_system / h_slice with gaps
    # outrank others.
    def sort_key(r: Dict) -> Tuple:
        is_active_with_gaps = (
            r["classification"] in ACTIVE_CLASSES and len(r["trust_gap_signals"]) > 0
        )
        return (
            -r["score"],
            0 if is_active_with_gaps else 1,
            r["spine_position_index"],
            r["system_id"],
        )

    rows.sort(key=sort_key)
    for idx, r in enumerate(rows, start=1):
        r["rank"] = idx

    # Build the top-N list, applying the no-unknown-without-justification rule.
    top: List[Dict] = []
    for r in rows:
        if len(top) >= top_n:
            break
        if r["classification"] == "unknown":
            r = {
                **r,
                "unknown_justification": (
                    "Top-5 slot used by an unknown candidate because higher-priority "
                    "candidates were exhausted; classify or reject before action."
                ),
            }
        top.append(r)

    global_ranked_systems = rows
    requested_candidate_set = [c for c in (requested_candidates or []) if c]
    requested_rows: List[Dict] = []
    ambiguous_requested_candidates: List[Dict] = []

    global_rank_by_id = {r["system_id"]: r["rank"] for r in global_ranked_systems}
    global_row_by_id = {r["system_id"]: r for r in global_ranked_systems}
    candidate_reason_by_id = {
        c["system_id"]: c.get("reason", "unknown_reason")
        for c in (classification.get("candidates") or [])
    }
    candidate_registry_by_id = {
        c["system_id"]: bool(c.get("in_registry"))
        for c in (classification.get("candidates") or [])
    }

    def _prerequisites_for(sid: str) -> List[str]:
        row = global_row_by_id.get(sid)
        if not row:
            return []
        upstream = row.get("dependencies", {}).get("upstream", [])
        sid_rank = global_rank_by_id.get(sid, 10**9)
        prereqs: List[str] = []
        for upstream_sid in upstream:
            upstream_row = global_row_by_id.get(upstream_sid)
            if not upstream_row:
                continue
            if global_rank_by_id.get(upstream_sid, 10**9) < sid_rank and upstream_row.get("classification") in ACTIVE_CLASSES:
                prereqs.append(upstream_sid)
        return prereqs

    for requested in requested_candidate_set:
        global_row = global_row_by_id.get(requested)
        if global_row:
            prereqs = _prerequisites_for(requested)
            risk_text = (
                "higher risk: upstream trust systems are ranked ahead and should be finished first"
                if prereqs
                else "no higher-priority upstream trust prerequisite detected in TLS ranking"
            )
            explanations = _requested_explanations(
                requested,
                global_row["classification"],
                global_rank_by_id.get(requested),
                global_row,
                prereqs,
                canonical_loop,
                candidate_registry_by_id.get(requested, False),
                candidate_reason_by_id.get(requested, "unknown_reason"),
            )
            requested_rows.append(
                {
                    "system_id": requested,
                    "global_rank": global_rank_by_id.get(requested),
                    "classification": global_row["classification"],
                    "score": global_row["score"],
                    "recommended_action": global_row["action"],
                    "why_now": global_row["why_now"],
                    "prerequisite_systems": prereqs,
                    "trust_gap_signals": global_row["trust_gap_signals"],
                    "finish_definition": global_row["finish_definition"],
                    "risk_if_built_before_prerequisites": risk_text,
                    **explanations,
                }
            )
            if global_row["classification"] == "unknown":
                ambiguous_requested_candidates.append(
                    {
                        "system_id": requested,
                        "ambiguity_reason": candidate_reason_by_id.get(requested, "classification_unknown"),
                    }
                )
            continue

        ambiguity_reason = "not_found_in_classification_or_registry_evidence"
        requested_rows.append(
            {
                "system_id": requested,
                "global_rank": None,
                "classification": "unknown",
                "score": None,
                "recommended_action": "investigate:classify_or_reject",
                "why_now": "requested candidate is not present in current TLS candidate index",
                "prerequisite_systems": [],
                "trust_gap_signals": [],
                "finish_definition": "retrieve registry and evidence before build prioritization",
                "risk_if_built_before_prerequisites": "unknown risk until candidate is classified",
                "ambiguity_reason": ambiguity_reason,
                **_requested_explanations(
                    requested,
                    "unknown",
                    None,
                    None,
                    [],
                    canonical_loop,
                    False,
                    ambiguity_reason,
                ),
            }
        )
        ambiguous_requested_candidates.append(
            {
                "system_id": requested,
                "ambiguity_reason": ambiguity_reason,
            }
        )

    requested_rows.sort(key=lambda r: (r["global_rank"] is None, r["global_rank"] or 10**9, r["system_id"]))
    for idx, row in enumerate(requested_rows, start=1):
        row["requested_rank"] = idx
        if row["classification"] == "unknown" and "ambiguity_reason" not in row:
            row["ambiguity_reason"] = candidate_reason_by_id.get(row["system_id"], "classification_unknown")

    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "TLS-04",
        "generated_at": _generated_at_iso(),
        "priority_order": [
            "mvp_spine_dependency",
            "trust_boundary_importance",
            "downstream_unlock_value",
            "partial_completion",
            "risk_if_deferred",
        ],
        "penalties": [
            "new_capability_without_trust_gain",
            "deprecated",
            "unknown",
        ],
        "ranked_systems": global_ranked_systems,
        "global_ranked_systems": global_ranked_systems,
        "top_5": top,
        "requested_candidate_set": requested_candidate_set,
        "requested_candidate_ranking": requested_rows,
        "ambiguous_requested_candidates": ambiguous_requested_candidates,
    }


def write_artifact(
    output_path: Path,
    dependency_graph: Dict,
    evidence_attachment: Dict,
    classification: Dict,
    trust_gaps: Dict,
    top_n: int = 5,
    requested_candidates: Optional[Sequence[str]] = None,
) -> Dict:
    payload = rank_systems(
        dependency_graph,
        evidence_attachment,
        classification,
        trust_gaps,
        top_n=top_n,
        requested_candidates=requested_candidates,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
