"""Runtime enforcement helpers for system registry ownership and handoff integrity."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import validate_artifact


class SystemRegistryEnforcerError(ValueError):
    """Raised when runtime registry-backed enforcement cannot be completed."""


_REPO_ROOT = Path(__file__).resolve().parents[3]
_REGISTRY_EXAMPLE_PATH = _REPO_ROOT / "contracts" / "examples" / "system_registry_artifact.json"
_OWNERSHIP_MAP_PATH = _REPO_ROOT / "docs" / "governance" / "governed_runtime_ownership_map.json"
_CANONICAL_HANDOFF_PATH: set[tuple[str, str]] = {
    ("PQX", "TPA"),
    ("TPA", "FRE"),
    ("FRE", "RIL"),
    ("RIL", "CDE"),
    ("TPA", "BAX"),
    ("BAX", "TAX"),
    ("TAX", "CAX"),
    ("CAX", "CDE"),
    ("CDE", "TLC"),
}


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


@lru_cache(maxsize=1)
def _load_registry() -> dict[str, Any]:
    if not _REGISTRY_EXAMPLE_PATH.is_file():
        raise SystemRegistryEnforcerError(f"registry example missing: {_REGISTRY_EXAMPLE_PATH}")
    try:
        registry = json.loads(_REGISTRY_EXAMPLE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemRegistryEnforcerError(
            f"registry artifact JSON invalid at {_REGISTRY_EXAMPLE_PATH}: {exc.msg} (line {exc.lineno}, col {exc.colno})"
        ) from exc
    try:
        validate_artifact(registry, "system_registry_artifact")
    except ValidationError as exc:
        path = "/".join(str(part) for part in exc.path) or "<root>"
        raise SystemRegistryEnforcerError(
            "registry artifact schema validation failed at "
            f"{path}: {exc.message}. Rebuild with scripts/build_system_registry_artifact.py."
        ) from exc
    return registry


@lru_cache(maxsize=1)
def _load_ownership_map() -> dict[str, Any]:
    if not _OWNERSHIP_MAP_PATH.is_file():
        return {}
    try:
        payload = json.loads(_OWNERSHIP_MAP_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemRegistryEnforcerError(f"governed runtime ownership map invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemRegistryEnforcerError("governed runtime ownership map must be JSON object")
    return payload


def clear_registry_enforcer_caches() -> None:
    _load_registry.cache_clear()
    _registry_indexes.cache_clear()
    _load_ownership_map.cache_clear()


@lru_cache(maxsize=1)
def _registry_indexes() -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], set[tuple[str, str]]]:
    registry = _load_registry()
    systems = registry.get("systems", [])
    if not isinstance(systems, list):
        raise SystemRegistryEnforcerError("system_registry_artifact.systems must be a list")

    systems_by_name: dict[str, dict[str, Any]] = {}
    owners_by_action: dict[str, list[str]] = {}
    for raw_system in systems:
        if not isinstance(raw_system, dict):
            raise SystemRegistryEnforcerError("system_registry_artifact.systems entries must be objects")
        acronym = str(raw_system.get("acronym") or "").strip().upper()
        if not acronym:
            raise SystemRegistryEnforcerError("system_registry_artifact system acronym is required")
        systems_by_name[acronym] = raw_system
        downstream = raw_system.get("downstream_consumers", [])
        if isinstance(downstream, list) and len(downstream) != len(set(str(item) for item in downstream)):
            raise SystemRegistryEnforcerError(
                f"registry malformed: duplicate downstream_consumers for {acronym}. "
                "Rebuild with scripts/build_system_registry_artifact.py."
            )
        owns = raw_system.get("owns", [])
        if isinstance(owns, list):
            for action in owns:
                normalized_action = str(action or "").strip()
                if normalized_action:
                    owners_by_action.setdefault(normalized_action, []).append(acronym)

    interaction_edges = registry.get("interaction_edges", [])
    allowed_edges: set[tuple[str, str]] = set()
    if not isinstance(interaction_edges, list):
        raise SystemRegistryEnforcerError("system_registry_artifact.interaction_edges must be a list")
    for edge in interaction_edges:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("from") or "").strip().upper()
        target = str(edge.get("to") or "").strip().upper()
        if source and target:
            allowed_edges.add((source, target))
    return systems_by_name, owners_by_action, allowed_edges


def validate_system_action(system_name: str, action_type: str, target_system: str) -> dict[str, Any]:
    """Fail-closed registry enforcement for runtime action ownership and interactions."""
    systems, owners_by_action, allowed_edges = _registry_indexes()

    source = str(system_name or "").strip().upper()
    target = str(target_system or "").strip().upper()
    action = str(action_type or "").strip()

    violations: list[str] = []

    source_system = systems.get(source)
    target_exists = target in systems
    if source_system is None:
        violations.append("E_UNKNOWN_SOURCE_SYSTEM")
    if not target_exists:
        violations.append("E_UNKNOWN_TARGET_SYSTEM")
    if not action:
        violations.append("E_EMPTY_ACTION_TYPE")

    owners = owners_by_action.get(action, [])
    if len(owners) > 1:
        violations.append("E_DUPLICATE_ACTION_OWNERSHIP")
    if source_system is not None:
        if action not in source_system.get("owns", []):
            violations.append("E_ACTION_NOT_OWNED_BY_SYSTEM")
        if action in source_system.get("prohibited_behaviors", []):
            violations.append("E_PROHIBITED_BEHAVIOR")
    for system, entry in systems.items():
        classification = str(entry.get("classification") or "")
        if classification == "support_only" and action in entry.get("owns", []):
            violations.append(f"E_SUPPORT_ONLY_OWNS_ACTION:{system}:{action}")

    allowed_interaction = (source, target) in allowed_edges or (source, target) in _CANONICAL_HANDOFF_PATH
    if source_system is not None and target_exists and not allowed_interaction:
        violations.append("E_INTERACTION_NOT_ALLOWED")

    legacy_aliases = {
        "E_UNKNOWN_SOURCE_SYSTEM": "unknown_source_system",
        "E_UNKNOWN_TARGET_SYSTEM": "unknown_target_system",
        "E_DUPLICATE_ACTION_OWNERSHIP": "duplicate_action_ownership",
        "E_ACTION_NOT_OWNED_BY_SYSTEM": "action_not_owned_by_system",
        "E_PROHIBITED_BEHAVIOR": "prohibited_behavior",
        "E_INTERACTION_NOT_ALLOWED": "interaction_not_allowed",
    }
    for code in list(violations):
        alias = legacy_aliases.get(code)
        if alias:
            violations.append(alias)

    return {
        "allow": len(violations) == 0,
        "block": len(violations) > 0,
        "violation_codes": sorted(set(violations)),
        "system": source,
        "target_system": target,
        "action_type": action,
    }


def validate_system_handoff(from_system: str, to_system: str, artifact: dict[str, Any]) -> dict[str, Any]:
    """Validate a cross-system handoff using registry rules + schema + trace continuity."""
    if not isinstance(artifact, dict):
        return {
            "allow": False,
            "block": True,
            "violation_codes": ["invalid_handoff_artifact"],
            "from_system": str(from_system or "").strip().upper(),
            "to_system": str(to_system or "").strip().upper(),
            "schema_name": None,
        }

    payload = artifact.get("payload") if isinstance(artifact.get("payload"), dict) else artifact
    schema_name = artifact.get("schema_name") if isinstance(artifact.get("schema_name"), str) else artifact.get("artifact_type")
    action_type = artifact.get("action_type") if isinstance(artifact.get("action_type"), str) else "orchestration"
    required_fields = artifact.get("required_fields") if isinstance(artifact.get("required_fields"), list) else []
    expected_trace_refs = artifact.get("expected_trace_refs") if isinstance(artifact.get("expected_trace_refs"), list) else []

    violations: list[str] = []

    action_check = validate_system_action(from_system, action_type, to_system)
    violations.extend(action_check["violation_codes"])

    if not isinstance(schema_name, str) or not schema_name.strip():
            violations.append("E_MISSING_SCHEMA_NAME")
    else:
        try:
            validate_artifact(payload, schema_name.strip())
        except (ValidationError, FileNotFoundError, TypeError, ValueError):
            violations.append("E_ARTIFACT_SCHEMA_VALIDATION_FAILED")

    missing_required = [
        str(field) for field in required_fields if isinstance(field, str) and field.strip() and not _is_present(payload.get(field))
    ]
    if missing_required:
        violations.append("E_MISSING_REQUIRED_FIELDS")

    trace_refs = payload.get("trace_refs", [])
    artifact_level_trace_refs = artifact.get("trace_refs", [])
    if isinstance(artifact_level_trace_refs, list):
        trace_refs = list(trace_refs) + artifact_level_trace_refs
    if isinstance(trace_refs, str):
        trace_refs = [trace_refs]
    if not isinstance(trace_refs, list):
        trace_refs = []
    normalized_trace_refs = [str(item).strip() for item in trace_refs if str(item).strip()]

    trace_id = payload.get("trace_id")
    if isinstance(trace_id, str) and trace_id.strip():
        normalized_trace_refs.append(trace_id.strip())

    if not normalized_trace_refs:
        violations.append("E_MISSING_TRACE_CONTINUITY")
    elif expected_trace_refs:
        expected = {str(item).strip() for item in expected_trace_refs if str(item).strip()}
        if expected and expected.isdisjoint(set(normalized_trace_refs)):
            violations.append("E_BROKEN_TRACE_CONTINUITY")

    legacy_aliases = {
        "E_MISSING_SCHEMA_NAME": "missing_schema_name",
        "E_ARTIFACT_SCHEMA_VALIDATION_FAILED": "artifact_schema_validation_failed",
        "E_MISSING_REQUIRED_FIELDS": "missing_required_fields",
        "E_MISSING_TRACE_CONTINUITY": "missing_trace_continuity",
        "E_BROKEN_TRACE_CONTINUITY": "broken_trace_continuity",
    }
    for code in list(violations):
        alias = legacy_aliases.get(code)
        if alias:
            violations.append(alias)

    return {
        "allow": len(set(violations)) == 0,
        "block": len(set(violations)) > 0,
        "violation_codes": sorted(set(violations)),
        "from_system": str(from_system or "").strip().upper(),
        "to_system": str(to_system or "").strip().upper(),
        "schema_name": schema_name,
    }


def validate_artifact_authority(*, emitting_system: str, artifact_type: str) -> dict[str, Any]:
    source = str(emitting_system or "").strip().upper()
    artifact = str(artifact_type or "").strip()
    violations: list[str] = []
    if not source:
        violations.append("E_UNKNOWN_SOURCE_SYSTEM")
    if not artifact:
        violations.append("E_EMPTY_ARTIFACT_TYPE")
    if artifact == "closure_decision_artifact" and source != "CDE":
        violations.append("E_ARTIFACT_AUTHORITY_VIOLATION_CLOSURE_DECISION_CDE_ONLY")
    if artifact in {"system_registry_artifact", "preflight_block_diagnosis_record"} and source not in {"SEL", "TPA"}:
        violations.append("E_ARTIFACT_AUTHORITY_VIOLATION_REGISTRY_PREFLIGHT_PATH")
    return {
        "allow": len(violations) == 0,
        "block": len(violations) > 0,
        "violation_codes": sorted(set(violations)),
        "system": source,
        "artifact_type": artifact,
    }
