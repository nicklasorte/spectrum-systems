"""SLO Policy Registry (BN.2).

Centralised, governed registry of enforcement policy profiles and
stage-to-policy bindings for the TI Enforcement Layer.

This module owns:
- policy definitions
- stage bindings
- validation of legal policy names and stages
- override resolution rules
- access helpers for downstream consumers

It does **not** depend on CLI behaviour.

Registry contract
-----------------
The canonical registry is stored at:
    data/policy/slo_policy_registry.json

and validated against:
    contracts/schemas/slo_policy_registry.schema.json

Policy profiles
---------------
permissive
    TI 1.0 → allow  /  TI 0.5 → allow_with_warning  /  TI 0.0 → fail
    Warnings permitted.  Degraded lineage allowed.

decision_grade
    TI 1.0 → allow  /  TI 0.5 → fail  /  TI 0.0 → fail
    Warnings not permitted.  Degraded lineage not allowed.

exploratory
    TI 1.0 → allow  /  TI 0.5 → allow_with_warning  /  TI 0.0 → fail
    Warnings permitted.  Degraded lineage allowed.

Stage bindings (defaults)
-------------------------
observe    → permissive
interpret  → permissive
recommend  → decision_grade
synthesis  → decision_grade
export     → decision_grade

Override resolution order
-------------------------
1. Explicit caller-provided policy (beats everything)
2. Stage-bound default (if stage is provided and has a binding)
3. No implicit fallback. If neither explicit policy nor valid stage
   binding resolve a policy, raise ``PolicyResolutionError``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator, FormatChecker

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REGISTRY_PATH = _REPO_ROOT / "data" / "policy" / "slo_policy_registry.json"
_REGISTRY_SCHEMA_PATH = _REPO_ROOT / "contracts" / "schemas" / "slo_policy_registry.schema.json"

# ---------------------------------------------------------------------------
# Registry version / contract version
# ---------------------------------------------------------------------------

REGISTRY_VERSION: str = "1.0.0"
CONTRACT_VERSION: str = "1.0.0"

# ---------------------------------------------------------------------------
# Policy profile name constants
# ---------------------------------------------------------------------------

POLICY_PERMISSIVE: str = "permissive"
POLICY_DECISION_GRADE: str = "decision_grade"
POLICY_EXPLORATORY: str = "exploratory"

#: System-wide default policy when no explicit policy or stage is given.
DEFAULT_POLICY: str = POLICY_PERMISSIVE

#: All recognised policy profile names.
KNOWN_POLICIES: frozenset = frozenset({
    POLICY_PERMISSIVE,
    POLICY_DECISION_GRADE,
    POLICY_EXPLORATORY,
})

# ---------------------------------------------------------------------------
# Stage name constants
# ---------------------------------------------------------------------------

STAGE_OBSERVE: str = "observe"
STAGE_INTERPRET: str = "interpret"
STAGE_RECOMMEND: str = "recommend"
STAGE_SYNTHESIS: str = "synthesis"
STAGE_EXPORT: str = "export"

#: All recognised pipeline stage identifiers.
KNOWN_STAGES: frozenset = frozenset({
    STAGE_OBSERVE,
    STAGE_INTERPRET,
    STAGE_RECOMMEND,
    STAGE_SYNTHESIS,
    STAGE_EXPORT,
})

# ---------------------------------------------------------------------------
# Stage default policy bindings
# (derived from the canonical registry file at module load time)
# ---------------------------------------------------------------------------

STAGE_DEFAULT_POLICIES: Dict[str, str] = {
    STAGE_OBSERVE: POLICY_PERMISSIVE,
    STAGE_INTERPRET: POLICY_PERMISSIVE,
    STAGE_RECOMMEND: POLICY_DECISION_GRADE,
    STAGE_SYNTHESIS: POLICY_DECISION_GRADE,
    STAGE_EXPORT: POLICY_DECISION_GRADE,
}

# ---------------------------------------------------------------------------
# Decision status constants (mirrors slo_enforcement for registry consumers)
# ---------------------------------------------------------------------------

DECISION_ALLOW: str = "allow"
DECISION_ALLOW_WITH_WARNING: str = "allow_with_warning"
DECISION_FAIL: str = "fail"

# ---------------------------------------------------------------------------
# Recommended action constants
# ---------------------------------------------------------------------------

ACTION_PROCEED: str = "proceed"
ACTION_PROCEED_WITH_CAUTION: str = "proceed_with_caution"
ACTION_HALT_AND_REVIEW: str = "halt_and_review"
ACTION_HALT_INVALID_LINEAGE: str = "halt_invalid_lineage"
ACTION_HALT_DEGRADED_LINEAGE: str = "halt_degraded_lineage"
ACTION_INVESTIGATE_INCONSISTENCY: str = "investigate_inconsistency"
ACTION_FIX_INPUT: str = "fix_input"

KNOWN_RECOMMENDED_ACTIONS: frozenset = frozenset({
    ACTION_PROCEED,
    ACTION_PROCEED_WITH_CAUTION,
    ACTION_HALT_AND_REVIEW,
    ACTION_HALT_INVALID_LINEAGE,
    ACTION_HALT_DEGRADED_LINEAGE,
    ACTION_INVESTIGATE_INCONSISTENCY,
    ACTION_FIX_INPUT,
})

# ---------------------------------------------------------------------------
# Governed error types
# ---------------------------------------------------------------------------


class PolicyRegistryError(ValueError):
    """Raised for governed validation failures in the policy registry."""


class UnknownPolicyError(PolicyRegistryError):
    """Raised when an unknown policy name is requested."""


class UnknownStageError(PolicyRegistryError):
    """Raised when an unknown stage name is requested."""


class MalformedRegistryError(PolicyRegistryError):
    """Raised when the registry data is structurally invalid."""


class PolicyResolutionError(PolicyRegistryError):
    """Raised when no explicit or stage-bound policy can be resolved."""


# ---------------------------------------------------------------------------
# Registry loading and validation
# ---------------------------------------------------------------------------


def load_slo_policy_registry(
    registry_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Load the canonical SLO policy registry from disk.

    Parameters
    ----------
    registry_path:
        Optional override path.  Defaults to the canonical location
        ``data/policy/slo_policy_registry.json``.

    Returns
    -------
    The parsed registry dict.

    Raises
    ------
    MalformedRegistryError
        If the file cannot be read or parsed.
    """
    path = registry_path or _REGISTRY_PATH
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MalformedRegistryError(
            f"Registry file not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise MalformedRegistryError(
            f"Registry file is not valid JSON: {exc}"
        ) from exc
    except OSError as exc:
        # Permission errors, device errors, or other OS-level file issues.
        raise MalformedRegistryError(
            f"Failed to read registry file {path}: {exc}"
        ) from exc


def validate_slo_policy_registry(
    registry: Dict[str, Any],
    schema_path: Optional[Path] = None,
) -> List[str]:
    """Validate *registry* against the governed JSON Schema.

    Parameters
    ----------
    registry:
        The parsed registry dict.
    schema_path:
        Optional override for the schema path.

    Returns
    -------
    List of validation error strings.  Empty list means the registry is valid.
    """
    errors: List[str] = []
    path = schema_path or _REGISTRY_SCHEMA_PATH
    try:
        schema_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"Registry schema file could not be read: {exc}")
        return errors
    try:
        schema = json.loads(schema_text)
    except json.JSONDecodeError as exc:
        errors.append(f"Registry schema file is not valid JSON: {exc}")
        return errors
    try:
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for err in sorted(validator.iter_errors(registry), key=lambda e: e.path):
            errors.append(f"slo_policy_registry schema error: {err.message}")
    except Exception as exc:  # noqa: BLE001
        # Catches unexpected jsonschema internal errors.
        errors.append(f"Registry schema validation error: {exc}")
    return errors


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_policy_name(policy: str) -> None:
    """Assert that *policy* is a known policy name.

    Raises
    ------
    UnknownPolicyError
        If *policy* is not in :data:`KNOWN_POLICIES`.
    """
    if policy not in KNOWN_POLICIES:
        raise UnknownPolicyError(
            f"Unknown policy name: {policy!r}. "
            f"Expected one of: {sorted(KNOWN_POLICIES)}"
        )


def validate_stage_name(stage: str) -> None:
    """Assert that *stage* is a known stage name.

    Raises
    ------
    UnknownStageError
        If *stage* is not in :data:`KNOWN_STAGES`.
    """
    if stage not in KNOWN_STAGES:
        raise UnknownStageError(
            f"Unknown stage name: {stage!r}. "
            f"Expected one of: {sorted(KNOWN_STAGES)}"
        )


# ---------------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------------


def list_slo_policies(
    registry: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Return a sorted list of all registered policy profile names.

    Parameters
    ----------
    registry:
        Optional pre-loaded registry dict.  If ``None``, the canonical
        registry is loaded from disk.
    """
    reg = registry or load_slo_policy_registry()
    return sorted(reg.get("policies", {}).keys())


def list_slo_stages(
    registry: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Return a sorted list of all registered stage names.

    Parameters
    ----------
    registry:
        Optional pre-loaded registry dict.  If ``None``, the canonical
        registry is loaded from disk.
    """
    reg = registry or load_slo_policy_registry()
    return sorted(reg.get("stage_bindings", {}).keys())


def get_stage_bound_policy(
    stage: str,
    registry: Optional[Dict[str, Any]] = None,
) -> str:
    """Return the default policy name bound to *stage*.

    Parameters
    ----------
    stage:
        Pipeline stage identifier.
    registry:
        Optional pre-loaded registry dict.

    Returns
    -------
    The policy profile name bound to *stage*.

    Raises
    ------
    UnknownStageError
        If *stage* has no binding in the registry.
    """
    reg = registry or load_slo_policy_registry()
    bindings: Dict[str, str] = reg.get("stage_bindings", {})
    if stage not in bindings:
        raise UnknownStageError(
            f"No stage binding found for stage: {stage!r}. "
            f"Known stages: {sorted(bindings.keys())}"
        )
    return bindings[stage]


def get_policy_profile(
    policy: str,
    registry: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return the full profile dict for *policy*.

    Parameters
    ----------
    policy:
        Policy profile name.
    registry:
        Optional pre-loaded registry dict.

    Returns
    -------
    The profile dict.

    Raises
    ------
    UnknownPolicyError
        If *policy* is not in the registry.
    """
    reg = registry or load_slo_policy_registry()
    profiles: Dict[str, Any] = reg.get("policies", {})
    if policy not in profiles:
        raise UnknownPolicyError(
            f"Unknown policy: {policy!r}. "
            f"Known policies: {sorted(profiles.keys())}"
        )
    return profiles[policy]


# ---------------------------------------------------------------------------
# Override resolution
# ---------------------------------------------------------------------------


def resolve_effective_slo_policy(
    requested_policy: Optional[str],
    stage: Optional[str],
    registry: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Resolve the effective policy using the governed override rules.

    Resolution order:
    1. Explicit caller-provided policy (beats everything)
    2. Stage-bound default (if stage is provided and has a binding)
    3. No implicit fallback; resolution fails closed when no policy can be
       resolved from explicit policy or stage binding.

    Parameters
    ----------
    requested_policy:
        Explicit policy name provided by the caller, or ``None``.
    stage:
        Pipeline stage identifier, or ``None``.
    registry:
        Optional pre-loaded registry dict.

    Returns
    -------
    (effective_policy, resolution_source)
        effective_policy   – the resolved policy name
        resolution_source  – one of ``"explicit"``, ``"stage_binding"``

    Raises
    ------
    UnknownPolicyError
        If *requested_policy* is provided but unknown.
    UnknownStageError
        If *stage* is provided but unknown.
    PolicyResolutionError
        If neither an explicit policy nor a valid stage binding is provided.
    """
    reg = registry or load_slo_policy_registry()

    if requested_policy is not None:
        validate_policy_name(requested_policy)
        return requested_policy, "explicit"

    if stage is not None:
        validate_stage_name(stage)
        bound_policy = get_stage_bound_policy(stage, reg)
        return bound_policy, "stage_binding"

    raise PolicyResolutionError(
        "Policy resolution failed closed: explicit policy_id is required when "
        "no stage binding is provided."
    )


# ---------------------------------------------------------------------------
# Diagnostics helpers
# ---------------------------------------------------------------------------


def describe_effective_policy(
    requested_policy: Optional[str] = None,
    stage: Optional[str] = None,
    registry: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a diagnostics dict describing the effective policy resolution.

    Useful for CLI ``--show-effective-policy`` and for observability.

    Parameters
    ----------
    requested_policy:
        Explicit policy override, or ``None``.
    stage:
        Pipeline stage, or ``None``.
    registry:
        Optional pre-loaded registry dict.

    Returns
    -------
    Dict with keys:
        ``effective_policy``   – resolved policy name
        ``resolution_source``  – how the policy was chosen
        ``stage``              – stage provided (or null)
        ``requested_policy``   – explicit policy provided (or null)
        ``profile``            – the full policy profile dict
        ``stage_binding``      – the stage's bound policy (or null)
        ``error``              – error message string if resolution failed (or null)
    """
    reg = registry or load_slo_policy_registry()
    result: Dict[str, Any] = {
        "effective_policy": None,
        "resolution_source": None,
        "stage": stage,
        "requested_policy": requested_policy,
        "profile": None,
        "stage_binding": None,
        "error": None,
    }
    try:
        effective_policy, resolution_source = resolve_effective_slo_policy(
            requested_policy, stage, reg
        )
        result["effective_policy"] = effective_policy
        result["resolution_source"] = resolution_source
        result["profile"] = get_policy_profile(effective_policy, reg)
        if stage is not None and stage in (reg.get("stage_bindings") or {}):
            result["stage_binding"] = reg["stage_bindings"][stage]
    except PolicyRegistryError as exc:
        result["error"] = str(exc)
    return result


def list_stage_bindings(
    registry: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Return the full stage → policy bindings dict.

    Parameters
    ----------
    registry:
        Optional pre-loaded registry dict.
    """
    reg = registry or load_slo_policy_registry()
    return dict(reg.get("stage_bindings", {}))
