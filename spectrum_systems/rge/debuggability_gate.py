"""RGE Debuggability Gate - Principle 3: Optimize for Debuggability.

Scores a phase on explainability (0.0 to 1.0). Unlike Gates 1 and 2, this gate
does NOT raise on failure - it returns the assessment with decision set to
'return_for_rewrite' and specific gaps to address.

No silent failures. Every gap is named. Every output includes a 3LS glossary
so engineers never need to look up what TPA or EVL means.

Wires into: structured_failures.py (RUNBOOK_INDEX)
            roadmap_stop_reasons.py (CANONICAL_STOP_REASONS)
Emits: debuggability_assessment_record
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.debugging.structured_failures import RUNBOOK_INDEX
from spectrum_systems.modules.runtime.roadmap_stop_reasons import CANONICAL_STOP_REASONS

EXPLAINABILITY_THRESHOLD = 0.7

THREE_LS_GLOSSARY: dict[str, str] = {
    "AEX": "Admission boundary - gates what enters the runtime",
    "PQX": "Execution engine - runs governed slices",
    "EVL": "Eval authority - gates on evidence before closure",
    "TPA": "Trust/policy adjudication - interprets policy for execution",
    "CDE": "Control decision engine - sole authority on allow/warn/freeze/block",
    "SEL": "Enforcement - executes CDE decisions, records actions before acting",
    "REP": "Replay integrity - every decision must be reproducible",
    "LIN": "Lineage - full provenance chain for every artifact",
    "OBS": "Observability - metrics, traces, alerts",
    "SLO": "Error budget - reliability targets with freeze-on-exhaust",
    "RIL": "Input structuring - validates context admission",
    "FRE": "Failure diagnosis - root cause and repair planning",
    "RAX": "Candidate intelligence - non-decisioning signals",
    "RQX": "Red-team orchestrator - bounded, fail-closed red-teaming",
    "RDX": "Roadmap exchange - execution contracts for roadmap",
    "MAP": "System topology - metadata and topology authority",
    "GOV": "Certification gate - governs promotion readiness",
    "MG":  "Meta-governance kernel - 24 slices across 4 umbrellas",
}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"DAR-{hashlib.sha256(raw.encode()).hexdigest()[:12].upper()}"


def _score(phase: dict[str, Any]) -> tuple[float, list[str]]:
    gaps: list[str] = []
    passed = 0
    total = 5

    refs = phase.get("evidence_refs", [])
    if (
        isinstance(refs, list)
        and refs
        and all(isinstance(r, str) for r in refs)
        and any((":" in r or r.startswith("schema://") or "-" in r) for r in refs)
    ):
        passed += 1
    else:
        gaps.append(
            "evidence_refs: missing or prose-only - link specific artifact IDs "
            "(e.g. 'drift_signal_record:DS-0041', 'complexity_budget:CB-0012')"
        )

    runbook = str(phase.get("runbook", ""))
    if runbook and (".md" in runbook or runbook.startswith("docs/")):
        passed += 1
    else:
        gaps.append(
            "runbook: missing - add a docs/runbooks/*.md path "
            "so engineers know where to look on failure"
        )

    stop_reason = str(phase.get("stop_reason", ""))
    if stop_reason in CANONICAL_STOP_REASONS:
        passed += 1
    else:
        gaps.append(
            f"stop_reason: '{stop_reason}' not in CANONICAL_STOP_REASONS - "
            "pick from roadmap_stop_reasons.CANONICAL_STOP_REASONS"
        )

    failure = str(phase.get("failure_prevented", ""))
    if failure and len(failure) >= 20:
        passed += 1
    else:
        gaps.append(
            "failure_prevented: needs >=20 chars to be specific enough for a new engineer "
            f"(current: {len(failure)} chars)"
        )

    signal = str(phase.get("signal_improved", ""))
    if signal and any(ch.isdigit() for ch in signal):
        passed += 1
    else:
        gaps.append(
            "signal_improved: needs a specific number or threshold "
            "(e.g. 'from 62% to 90%', 'drops by 12 points')"
        )

    return passed / total, gaps


def assess_debuggability(
    phase: dict[str, Any],
    *,
    run_id: str,
    trace_id: str,
) -> dict[str, Any]:
    """Assess a phase for Principle 3 compliance.

    Returns a debuggability_assessment_record. decision is 'pass' or
    'return_for_rewrite'. Never raises - always returns actionable feedback.
    """
    phase_id = str(phase.get("phase_id", "")).strip()
    name = str(phase.get("name", "")).strip()

    score, gaps = _score(phase)
    decision = "pass" if score >= EXPLAINABILITY_THRESHOLD else "return_for_rewrite"

    phase_text = json.dumps(phase)
    glossary = [
        {"system": sys_id, "definition": defn}
        for sys_id, defn in THREE_LS_GLOSSARY.items()
        if sys_id in phase_text
    ]

    record = {
        "artifact_type": "debuggability_assessment_record",
        "schema_version": "1.0.0",
        "record_id": _stable_id({"phase_id": phase_id, "run_id": run_id}),
        "run_id": run_id,
        "trace_id": trace_id,
        "created_at": _utc_now(),
        "phase_id": phase_id,
        "phase_name": name,
        "explainability_score": round(score, 3),
        "threshold": EXPLAINABILITY_THRESHOLD,
        "decision": decision,
        "gaps": gaps,
        "glossary": glossary,
        "runbook": RUNBOOK_INDEX.get(
            "rge_debuggability_gate",
            "docs/runbooks/rge_debuggability_gate_failures.md",
        ),
        "principle": "optimize_for_debuggability",
    }

    validate_artifact(record, "debuggability_assessment_record")
    return record
