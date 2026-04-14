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
        violations.append("unknown_source_system")
    if not target_exists:
        violations.append("unknown_target_system")

    owners = owners_by_action.get(action, [])
    if len(owners) > 1:
        violations.append("duplicate_action_ownership")
    if source_system is not None:
        if action not in source_system.get("owns", []):
            violations.append("action_not_owned_by_system")
        if action in source_system.get("prohibited_behaviors", []):
            violations.append("prohibited_behavior")

    allowed_interaction = (source, target) in allowed_edges or (source, target) in _CANONICAL_HANDOFF_PATH
    if source_system is not None and target_exists and not allowed_interaction:
        violations.append("interaction_not_allowed")

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
        violations.append("missing_schema_name")
    else:
        try:
            validate_artifact(payload, schema_name.strip())
        except (ValidationError, FileNotFoundError, TypeError, ValueError):
            violations.append("artifact_schema_validation_failed")

    missing_required = [
        str(field) for field in required_fields if isinstance(field, str) and field.strip() and not _is_present(payload.get(field))
    ]
    if missing_required:
        violations.append("missing_required_fields")

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
        violations.append("missing_trace_continuity")
    elif expected_trace_refs:
        expected = {str(item).strip() for item in expected_trace_refs if str(item).strip()}
        if expected and expected.isdisjoint(set(normalized_trace_refs)):
            violations.append("broken_trace_continuity")

    return {
        "allow": len(set(violations)) == 0,
        "block": len(set(violations)) > 0,
        "violation_codes": sorted(set(violations)),
        "from_system": str(from_system or "").strip().upper(),
        "to_system": str(to_system or "").strip().upper(),
        "schema_name": schema_name,
    }
