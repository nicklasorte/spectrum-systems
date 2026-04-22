"""System justification registry.

Every system must declare what it prevents and what it improves.
New systems are rejected unless they pass the justification gate.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

SYSTEM_JUSTIFICATIONS: Dict[str, Dict[str, List[str]]] = {
    "TPA": {
        "prevents": ["unsigned_execution", "lineage_breaks"],
        "improves": ["traceability", "auditability"],
    },
    "TLC": {
        "prevents": ["routing_to_wrong_owner", "artifact_loss"],
        "improves": ["governance_integrity"],
    },
    "PRG": {
        "prevents": ["roadmap_misalignment"],
        "improves": ["program_level_visibility"],
    },
    "WPG": {
        "prevents": ["execution_without_provenance"],
        "improves": ["execution_auditability"],
    },
    "CHK": {
        "prevents": ["batch_constraint_violations", "umbrella_constraint_violations"],
        "improves": ["execution_hierarchy_integrity"],
    },
    "GOV": {
        "prevents": ["policy_drift", "unauthorized_execution"],
        "improves": ["governance_enforcement"],
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
    """Return (valid, reason) for a system_id against the locked registry.

    A system is valid if it has at least one entry in 'prevents' and at least
    one entry in 'improves' in the SYSTEM_JUSTIFICATIONS registry.
    """
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


def propose_system(
    system_id: str,
    prevents: List[str],
    improves: List[str],
    description: str = "",
) -> Tuple[bool, str]:
    """Gate for new system proposals.

    Rejects if:
    - No prevents entries
    - No improves entries
    - Description signals pure orchestration (no independent value)
    - Registry is locked (default: True)
    """
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
