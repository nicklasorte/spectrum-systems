"""TLS-03 — Trust-gap signal detection (observer-only).

This module emits ``trust_gap_signal`` observations only. It owns no closure,
advancement, or compliance authority. Canonical owners (CDE for closure, GOV
for readiness/compliance evidence packaging, SEL for compliance, PRA for
advancement) read these observations as inputs.

For every classified candidate, evaluate trust-gap signals deterministically
from Phase 1 evidence and registry metadata:

* missing_eval                 — no evidence under tests/ AND no schema reference.
* missing_control              — system not in canonical_loop AND no link to CDE.
* missing_enforcement_signal   — no SEL reference in registry downstream chain
                                 (observation only; SEL retains compliance
                                 authority).
* missing_replay               — no evidence under tests/replay or REP downstream tie.
* missing_lineage              — no LIN downstream tie or no artifact lineage record.
* missing_observability        — no OBS downstream tie or empty OBS evidence.
* missing_readiness_evidence   — no GOV downstream tie or empty readiness
                                 evidence record (observation only; GOV retains
                                 readiness/compliance authority).
* missing_tests                — evidence.tests is empty.
* schema_weakness              — evidence.schemas is empty (no contract surface).

Rules:
* Active systems are evaluated against ALL signals.
* Support / deprecated / future systems are evaluated only against signals
  that are meaningful for them (typically just missing_tests / schema_weakness).
* No system is allowed to be marked "safe" (zero gap signals) without an
  explicit source-of-truth: gaps_evaluated > 0 always.
* A gap signal can only flip false (i.e. NOT a gap) when explicit evidence is
  found.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Set


SCHEMA_VERSION = "tls-03.v1"

ALL_SIGNALS = [
    "missing_eval",
    "missing_control",
    "missing_enforcement_signal",
    "missing_replay",
    "missing_lineage",
    "missing_observability",
    "missing_readiness_evidence",
    "missing_tests",
    "schema_weakness",
]

ACTIVE_CLASSES = {"active_system", "h_slice"}
SUPPORT_CLASSES = {"support_capability", "deprecated", "future", "unknown"}


def _index(rows: List[Dict], key: str) -> Dict[str, Dict]:
    return {r[key]: r for r in rows}


def _evidence_for(evidence_idx: Dict[str, Dict], sid: str) -> Dict:
    row = evidence_idx.get(sid) or {}
    return row.get("evidence") or {
        "modules": [],
        "tests": [],
        "schemas": [],
        "docs": [],
        "reviews": [],
        "review_actions": [],
        "scripts": [],
        "artifacts": [],
    }


def _registry_node(graph: Dict, sid: str) -> Optional[Dict]:
    for node in graph.get("active_systems") or []:
        if node["system_id"] == sid:
            return node
    return None


def _has_path_token(paths: List[str], token: str) -> bool:
    token_lower = token.lower()
    return any(token_lower in p.lower() for p in paths)


def _detect_signals(
    sid: str,
    classification: str,
    graph: Dict,
    evidence_idx: Dict[str, Dict],
    canonical_loop: Set[str],
) -> Dict:
    ev = _evidence_for(evidence_idx, sid)
    node = _registry_node(graph, sid)
    upstream = (node or {}).get("upstream") or []
    downstream = (node or {}).get("downstream") or []

    signals: Dict[str, bool] = {}

    if classification in ACTIVE_CLASSES:
        # Active systems are subject to the full battery.
        signals["missing_eval"] = (
            len(ev.get("tests", [])) == 0
            and "EVL" not in upstream + downstream
            and not _has_path_token(ev.get("schemas", []), "eval")
        )
        signals["missing_control"] = sid not in canonical_loop and "CDE" not in downstream and sid != "CDE"
        # missing_enforcement_signal: surface a non-owning observation when the
        # registry-canonical compliance system is absent from this row's
        # upstream/downstream and no compliance-owner module appears in
        # evidence. Observation only — TLS does not own compliance.
        signals["missing_enforcement_signal"] = (
            sid != "SEL"
            and "SEL" not in downstream
            and not _has_path_token(ev.get("modules", []), "sel_")
        )
        signals["missing_replay"] = (
            sid != "REP"
            and "REP" not in downstream
            and not _has_path_token(ev.get("tests", []), "replay")
        )
        signals["missing_lineage"] = (
            sid != "LIN"
            and "LIN" not in downstream
            and not _has_path_token(ev.get("artifacts", []), "lineage")
            and not _has_path_token(ev.get("modules", []), "lineage")
        )
        signals["missing_observability"] = (
            sid != "OBS"
            and "OBS" not in downstream
            and not _has_path_token(ev.get("modules", []), "observability")
        )
        # missing_readiness_evidence: surface a non-owning observation when the
        # registry-canonical readiness system is absent from this row's
        # downstream chain and no readiness-owner artifact/module appears in
        # evidence. Observation only — TLS does not own readiness.
        signals["missing_readiness_evidence"] = (
            sid != "GOV"
            and "GOV" not in downstream
            and not _has_path_token(ev.get("artifacts", []), "gov_")
            and not _has_path_token(ev.get("modules", []), "/governance/")
        )
        signals["missing_tests"] = len(ev.get("tests", [])) == 0
        signals["schema_weakness"] = len(ev.get("schemas", [])) == 0
    else:
        # Support / deprecated / future / unknown systems get a narrow battery.
        signals["missing_tests"] = len(ev.get("tests", [])) == 0
        signals["schema_weakness"] = len(ev.get("schemas", [])) == 0

    return signals


def detect_trust_gaps(
    dependency_graph: Dict,
    evidence_attachment: Dict,
    classification: Dict,
) -> Dict:
    if not classification.get("candidates"):
        raise ValueError("classification artifact has no candidates; cannot detect trust gaps")

    evidence_idx = _index(evidence_attachment.get("systems") or [], "system_id")
    canonical_loop = set(dependency_graph.get("canonical_loop") or [])

    rows: List[Dict] = []
    for cand in sorted(classification["candidates"], key=lambda c: c["system_id"]):
        sid = cand["system_id"]
        signals = _detect_signals(sid, cand["classification"], dependency_graph, evidence_idx, canonical_loop)
        gaps_evaluated = len(signals)
        gap_count = sum(1 for v in signals.values() if v)
        if gaps_evaluated == 0:
            # Fail-closed: no system may pass with zero signals evaluated.
            raise RuntimeError(f"trust gap detection produced zero signals for {sid}")

        # Sorted list of currently-failing signals.
        failing = sorted(name for name, present in signals.items() if present)
        passing = sorted(name for name, present in signals.items() if not present)
        rows.append(
            {
                "system_id": sid,
                "classification": cand["classification"],
                "gaps_evaluated": gaps_evaluated,
                "gap_count": gap_count,
                "failing_signals": failing,
                "passing_signals": passing,
                "trust_state": _trust_state(gap_count, gaps_evaluated),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "TLS-03",
        "signal_taxonomy": ALL_SIGNALS,
        "systems": rows,
    }


def _trust_state(gap_count: int, gaps_evaluated: int) -> str:
    if gaps_evaluated == 0:
        return "unknown"
    if gap_count == 0:
        return "ok"
    ratio = gap_count / gaps_evaluated
    if ratio >= 0.5:
        return "blocked_signal"
    if ratio >= 0.25:
        return "freeze_signal"
    return "warn"


def write_artifact(
    output_path: Path,
    dependency_graph: Dict,
    evidence_attachment: Dict,
    classification: Dict,
) -> Dict:
    payload = detect_trust_gaps(dependency_graph, evidence_attachment, classification)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
