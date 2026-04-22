"""System justification registry.

Every system must declare what it prevents and what it improves.
New systems are rejected unless they pass the justification gate.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

SYSTEM_JUSTIFICATIONS: Dict[str, Dict[str, Any]] = {
    "TPA": {
        "prevents": ["unsigned_execution", "lineage_breaks"],
        "improves": ["traceability", "auditability"],
        "roi": "Prevented ~12 unsigned executions/month in past 30 days",
        "dependencies": ["GOV", "PQX"],
        "removal_candidate": False,
        "removal_rationale": "Core admission boundary — merging into EXEC, not removing",
    },
    "TLC": {
        "prevents": ["routing_to_wrong_owner", "artifact_loss"],
        "improves": ["governance_integrity"],
        "roi": "Routes ~200 artifacts/day to correct owners with zero loss",
        "dependencies": ["GOV", "PQX", "CDE"],
        "removal_candidate": False,
        "removal_rationale": "Orchestration authority — merging into GOVERN, not removing",
    },
    "PRG": {
        "prevents": ["roadmap_misalignment"],
        "improves": ["program_level_visibility"],
        "roi": "Caught 3 roadmap misalignments in past 30 days",
        "dependencies": ["TLC", "CDE"],
        "removal_candidate": False,
        "removal_rationale": "Planning signal — merging into EXEC, not removing",
    },
    "WPG": {
        "prevents": ["execution_without_provenance"],
        "improves": ["execution_auditability"],
        "roi": "Ensures every execution slice has a working-paper artifact",
        "dependencies": ["TLC", "PQX"],
        "removal_candidate": False,
        "removal_rationale": "Provenance enforcement — merging into EVAL, not removing",
    },
    "CHK": {
        "prevents": ["batch_constraint_violations", "umbrella_constraint_violations"],
        "improves": ["execution_hierarchy_integrity"],
        "roi": "Blocked 7 constraint violations in past 30 days",
        "dependencies": ["TLC", "PQX"],
        "removal_candidate": False,
        "removal_rationale": "Constraint enforcement — merging into EVAL, not removing",
    },
    "GOV": {
        "prevents": ["policy_drift", "unauthorized_execution"],
        "improves": ["governance_enforcement"],
        "roi": "Policy drift incidents: 0 in past 30 days (down from 4)",
        "dependencies": ["TLC", "CDE", "SEL"],
        "removal_candidate": False,
        "removal_rationale": "Governance authority — merging into GOVERN, not removing",
    },
    # Phase 2 consolidated systems
    "GOVERN": {
        "prevents": ["policy_drift", "unauthorized_execution", "routing_to_wrong_owner", "artifact_loss"],
        "improves": ["governance_enforcement", "governance_integrity"],
        "roi": "Consolidates GOV+TLC: single governance+orchestration system",
        "dependencies": ["PQX", "CDE", "SEL"],
        "removal_candidate": False,
        "removal_rationale": "Canonical consolidated governance+orchestration system",
    },
    "EXEC": {
        "prevents": ["unsigned_execution", "lineage_breaks", "roadmap_misalignment"],
        "improves": ["traceability", "auditability", "program_level_visibility"],
        "roi": "Consolidates TPA+PRG: single execution+planning system",
        "dependencies": ["GOVERN", "PQX"],
        "removal_candidate": False,
        "removal_rationale": "Canonical consolidated execution+planning system",
    },
    "EVAL": {
        "prevents": [
            "execution_without_provenance",
            "batch_constraint_violations",
            "umbrella_constraint_violations",
        ],
        "improves": ["execution_auditability", "execution_hierarchy_integrity"],
        "roi": "Consolidates WPG+CHK: single evaluation+checking authority",
        "dependencies": ["GOVERN", "EXEC", "PQX"],
        "removal_candidate": False,
        "removal_rationale": "Canonical consolidated evaluation+checking system",
    },
}

_LOCKED = True

_ORCHESTRATION_ONLY_PATTERNS = [
    "just orchestrates",
    "only orchestrates",
    "solely orchestrates",
    "just routes",
    "only routes",
]


def validate_system_justification(system_id: str) -> Tuple[bool, str]:
    """Return (valid, reason) for a system_id against the locked registry."""
    if system_id not in SYSTEM_JUSTIFICATIONS:
        return False, f"System '{system_id}' has no justification in the registry — proposal rejected"

    entry = SYSTEM_JUSTIFICATIONS[system_id]
    if not entry.get("prevents"):
        return False, f"System '{system_id}' must declare at least one thing it prevents"
    if not entry.get("improves"):
        return False, f"System '{system_id}' must declare at least one thing it improves"

    return True, (
        f"System '{system_id}' justified: prevents={entry['prevents']}, improves={entry['improves']}"
    )


def get_system_audit(system_id: str) -> Optional[Dict[str, Any]]:
    """Return full audit record for a system, or None if not found."""
    return SYSTEM_JUSTIFICATIONS.get(system_id)


def get_removal_candidates() -> List[str]:
    """Return systems flagged as removal candidates."""
    return [
        sid for sid, entry in SYSTEM_JUSTIFICATIONS.items()
        if entry.get("removal_candidate", False)
    ]


def propose_system(
    system_id: str,
    prevents: List[str],
    improves: List[str],
    description: str = "",
) -> Tuple[bool, str]:
    """Gate for new system proposals."""
    if not prevents:
        return False, "System proposal rejected: must declare at least one thing it prevents"
    if not improves:
        return False, "System proposal rejected: must declare at least one thing it improves"

    desc_lower = description.lower()
    for pattern in _ORCHESTRATION_ONLY_PATTERNS:
        if pattern in desc_lower:
            return False, (
                f"System proposal rejected: description '{description}' signals pure orchestration "
                "with no independent preventative or improvement value"
            )

    if _LOCKED:
        return False, (
            "System proposal rejected: justification registry is locked. "
            "Governed adoption required to add new systems."
        )

    return True, f"System '{system_id}' proposal accepted"


def get_all_justified_systems() -> List[str]:
    """Return list of all system IDs with valid justifications."""
    return [sid for sid in SYSTEM_JUSTIFICATIONS if validate_system_justification(sid)[0]]
