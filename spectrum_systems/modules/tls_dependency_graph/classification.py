"""TLS-02 — Candidate system classification.

Inputs:
  * Phase 0 dependency graph (registry truth)
  * Phase 1 evidence attachment (repo truth)

Output classes per system_id:

* ``active_system``      — registry says active AND repo evidence exists.
* ``h_slice``            — H01 / horizontal-slice systems (special case).
* ``support_capability`` — registry says merged/demoted (artifact families,
  review labels, support layers).
* ``deprecated``         — registry says demoted/deprecated.
* ``future``             — registry future/placeholder.
* ``unknown``            — appears only in the repo (or only in registry
  with no evidence) and cannot be safely classified.

Special cases per spec:

* H01 → h_slice
* RFX → repo-detected candidate if not in registry
* MET / METS → unknown unless proven (proven = appears in active_systems
  with evidence)

Fail-closed: a candidate cannot be marked ``active_system`` without registry
evidence. Ambiguous candidates are listed under ``ambiguous_systems`` so the
ranker can apply penalties or skip.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set


SCHEMA_VERSION = "tls-02.v1"

# Repo-detected candidates that the spec calls out explicitly.
REPO_DETECTION_CANDIDATES = ("RFX", "MET", "METS", "H01")
H_SLICE_FORCED = {"H01"}
UNKNOWN_UNLESS_PROVEN = {"MET", "METS"}


def _build_registry_index(graph: Dict) -> Dict[str, str]:
    """Map system_id -> registry classification token."""

    idx: Dict[str, str] = {}
    for node in graph.get("active_systems") or []:
        idx[node["system_id"]] = "active_registry"
    for row in graph.get("merged_or_demoted") or []:
        sid = row["system_id"]
        status = (row.get("status") or "").lower()
        if status == "merged":
            idx[sid] = "support_capability"
        elif status in ("demoted", "deprecated"):
            idx[sid] = "deprecated"
        else:
            idx[sid] = "support_capability"
    for row in graph.get("future_systems") or []:
        idx[row["system_id"]] = "future"
    return idx


def _evidence_index(evidence: Dict) -> Dict[str, Dict]:
    return {row["system_id"]: row for row in evidence.get("systems") or []}


def classify_systems(
    dependency_graph: Dict,
    evidence_attachment: Dict,
    repo_detected_candidates: Optional[Sequence[str]] = None,
) -> Dict:
    """Build the system_candidate_classification artifact dictionary."""

    if not dependency_graph.get("active_systems"):
        raise ValueError("dependency_graph missing active_systems; cannot classify")
    if not evidence_attachment.get("systems"):
        raise ValueError("evidence_attachment missing systems; cannot classify")

    registry_idx = _build_registry_index(dependency_graph)
    evidence_idx = _evidence_index(evidence_attachment)
    candidates: Set[str] = set(registry_idx) | set(evidence_idx)
    if repo_detected_candidates:
        candidates.update(repo_detected_candidates)
    candidates.update(REPO_DETECTION_CANDIDATES)

    rows: List[Dict] = []
    ambiguous: List[Dict] = []

    for sid in sorted(candidates):
        registry_class = registry_idx.get(sid)
        ev_row = evidence_idx.get(sid)
        ev_count = ev_row["evidence_count"] if ev_row else 0
        in_registry = registry_class is not None

        # Spec-mandated overrides first.
        if sid in H_SLICE_FORCED:
            classification = "h_slice"
            reason = "spec_override:H01_is_h_slice"
        elif sid in UNKNOWN_UNLESS_PROVEN:
            classification = "active_system" if registry_class == "active_registry" and ev_count > 0 else "unknown"
            reason = (
                "spec_override:proven_via_active_registry_plus_evidence"
                if classification == "active_system"
                else "spec_override:MET_unknown_unless_proven"
            )
        elif registry_class == "active_registry":
            if ev_count > 0:
                classification = "active_system"
                reason = "active_in_registry_with_repo_evidence"
            else:
                classification = "unknown"
                reason = "active_in_registry_but_no_repo_evidence"
        elif registry_class == "deprecated":
            classification = "deprecated"
            reason = "registry_deprecated"
        elif registry_class == "support_capability":
            classification = "support_capability"
            reason = "registry_merged_or_demoted"
        elif registry_class == "future":
            classification = "future"
            reason = "registry_future_placeholder"
        else:
            # Repo-only candidate.
            classification = "unknown"
            reason = "repo_only_candidate_no_registry_record"

        row = {
            "system_id": sid,
            "classification": classification,
            "reason": reason,
            "in_registry": in_registry,
            "registry_class": registry_class,
            "evidence_count": ev_count,
        }
        rows.append(row)
        if classification == "unknown":
            ambiguous.append(row)

    summary = {
        c: sum(1 for r in rows if r["classification"] == c)
        for c in (
            "active_system",
            "h_slice",
            "support_capability",
            "deprecated",
            "future",
            "unknown",
        )
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "TLS-02",
        "summary": summary,
        "candidates": rows,
        "ambiguous_systems": ambiguous,
    }


def write_artifact(
    output_path: Path,
    dependency_graph: Dict,
    evidence_attachment: Dict,
    repo_detected_candidates: Optional[Sequence[str]] = None,
) -> Dict:
    payload = classify_systems(dependency_graph, evidence_attachment, repo_detected_candidates)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
