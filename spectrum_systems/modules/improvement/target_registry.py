"""
Target Registry — spectrum_systems/modules/improvement/target_registry.py

Maintains canonical ``target_component`` names used by the AW1 Remediation
Mapping Engine.  All mapping rules must reference a name from this registry;
free-form component strings are not permitted.

Design principles
-----------------
- Single source of truth for component names.
- Deterministic validation: unknown names are rejected with an explicit error.
- No ML or heuristic lookups — the registry is a plain enumeration.

Public API
----------
KNOWN_TARGET_COMPONENTS
    Frozenset of all valid target_component names.

validate_target_component(name)
    Raises ValueError if ``name`` is not in the registry.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

KNOWN_TARGET_COMPONENTS: frozenset[str] = frozenset(
    {
        "decision_extraction_prompt",
        "action_item_extraction_prompt",
        "contradiction_detection_prompt",
        "gap_detection_prompt",
        "adversarial_review_prompt",
        "grounding_verifier",
        "synthesis_grounding_rules",
        "output_schema_contract",
        "transcript_preprocessing_rules",
        "slide_preprocessing_rules",
        "retrieval_selection_rules",
        "observability_emission_rules",
        # sentinel used when no specific component is targeted
        "none",
    }
)


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------


def validate_target_component(name: str) -> str:
    """Return *name* unchanged if it is in the registry; raise ValueError otherwise.

    Parameters
    ----------
    name:
        Component name to validate.

    Returns
    -------
    str
        The validated name (unchanged).

    Raises
    ------
    ValueError
        If *name* is not a recognised target component.
    """
    if name not in KNOWN_TARGET_COMPONENTS:
        raise ValueError(
            f"Unknown target_component {name!r}. "
            f"Valid components: {sorted(KNOWN_TARGET_COMPONENTS)}"
        )
    return name
