"""Structural authority-shape detection outside canonical owners."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from scripts.authority_leak_rules import FORBIDDEN_FIELDS, FORBIDDEN_VALUES, _matches_scope_entry, is_owner_path

REPO_ROOT = Path(__file__).resolve().parents[1]

_DECISION_FIELDS = {"decision", "certification_status", "certified", "promoted", "promotion_ready"}
_ACTION_FIELDS = {"enforcement_action", "action", "next_action", "control_action"}
_ARTIFACT_AUTHORITY_PATTERN = re.compile(r"(decision|certification|promotion|enforcement)", re.IGNORECASE)


def _in_forbidden_context_scope(path: str, registry: dict[str, Any]) -> bool:
    normalized = path.replace("\\", "/").strip("/")
    contexts = registry.get("forbidden_contexts", {})
    if not isinstance(contexts, dict):
        return True
    scope_prefixes = tuple(str(item) for item in contexts.get("default_scope_prefixes", []) if str(item).strip())
    excluded_prefixes = tuple(str(item) for item in contexts.get("excluded_path_prefixes", []) if str(item).strip())
    if scope_prefixes and not any(_matches_scope_entry(normalized, item) for item in scope_prefixes):
        return False
    if excluded_prefixes and any(_matches_scope_entry(normalized, item) for item in excluded_prefixes):
        return False
    return True


def _to_literal(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Dict):
        result: dict[str, Any] = {}
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                result[key.value] = _to_literal(value)
        return result
    if isinstance(node, ast.List):
        return [_to_literal(item) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return [_to_literal(item) for item in node.elts]
    return None


def _collect_python_objects(path: Path) -> list[dict[str, Any]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    objects: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            lit = _to_literal(node)
            if isinstance(lit, dict):
                objects.append(lit)
    return objects


def _collect_json_objects(payload: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        out.append(payload)
        for value in payload.values():
            out.extend(_collect_json_objects(value))
    elif isinstance(payload, list):
        for value in payload:
            out.extend(_collect_json_objects(value))
    return out


def _normalize_keys(payload: dict[str, Any]) -> set[str]:
    return {str(key).strip().lower() for key in payload.keys()}


_GOVERNED_SUBSTANTIVE_SCHEMA_CACHE: dict[str, dict[str, Any] | None] = {}


def _load_contract_schema(artifact_type: str) -> dict[str, Any] | None:
    """Load contracts/schemas/{artifact_type}.schema.json (cached)."""
    if artifact_type in _GOVERNED_SUBSTANTIVE_SCHEMA_CACHE:
        return _GOVERNED_SUBSTANTIVE_SCHEMA_CACHE[artifact_type]
    schema_path = REPO_ROOT / "contracts" / "schemas" / f"{artifact_type}.schema.json"
    schema: dict[str, Any] | None = None
    if schema_path.is_file():
        try:
            payload = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            schema = payload
    _GOVERNED_SUBSTANTIVE_SCHEMA_CACHE[artifact_type] = schema
    return schema


def _is_governed_substantive_artifact(obj: dict[str, Any]) -> bool:
    """Return True only when the inspected object is a contract-registered
    substantive governed artifact.

    All four conditions must hold:
      1. ``producer_authority`` is a non-empty string.
      2. ``artifact_type`` is a non-empty string.
      3. A schema exists at ``contracts/schemas/{artifact_type}.schema.json``.
      4. That schema constrains ``producer_authority`` to a ``const`` value
         that matches the inspected object's ``producer_authority``.

    A non-owner cannot bypass the preparatory_only rules merely by setting
    ``producer_authority`` — they must also register a contract schema that
    binds the producer_authority value, which is itself reviewed governance.
    """
    artifact_type = obj.get("artifact_type")
    producer_authority = obj.get("producer_authority")
    if not isinstance(artifact_type, str) or not artifact_type.strip():
        return False
    if not isinstance(producer_authority, str) or not producer_authority.strip():
        return False
    schema = _load_contract_schema(artifact_type.strip())
    if schema is None:
        return False
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return False
    producer_authority_schema = properties.get("producer_authority")
    if not isinstance(producer_authority_schema, dict):
        return False
    if "const" not in producer_authority_schema:
        return False
    return producer_authority_schema.get("const") == producer_authority


def detect_authority_shapes(path: Path, registry: dict[str, Any]) -> list[dict[str, Any]]:
    rel_path = str(path).replace("\\", "/")
    repo_prefix = str(REPO_ROOT).replace("\\", "/") + "/"
    if rel_path.startswith(repo_prefix):
        rel_path = rel_path[len(repo_prefix) :]
    if not _in_forbidden_context_scope(rel_path, registry):
        return []
    if is_owner_path(rel_path, registry):
        return []

    objects: list[dict[str, Any]] = []
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        objects = _collect_json_objects(payload)
    elif path.suffix.lower() == ".py":
        objects = _collect_python_objects(path)
    else:
        return []

    required_assertions = set(
        str(item).strip().lower()
        for item in registry.get("preparatory_only", {}).get("required_non_authority_assertions", [])
    )
    allowed_preparatory_fields = set(
        str(item).strip().lower()
        for item in registry.get("preparatory_only", {}).get("allowed_fields", [])
    )

    violations: list[dict[str, Any]] = []
    for index, obj in enumerate(objects, start=1):
        keys = _normalize_keys(obj)

        if keys & _DECISION_FIELDS and keys & _ACTION_FIELDS:
            violations.append(
                {
                    "rule": "authority_shape_outcome_action",
                    "path": rel_path,
                    "object_index": index,
                    "fields": sorted(keys & (_DECISION_FIELDS | _ACTION_FIELDS)),
                    "message": "object combines outcome semantics with action semantics outside canonical owners",
                }
            )

        if ({"certification_status", "certified"} & keys) and ({"promoted", "promotion_ready"} & keys):
            violations.append(
                {
                    "rule": "authority_shape_certification_promotion_verdict",
                    "path": rel_path,
                    "object_index": index,
                    "fields": sorted(keys & {"certification_status", "certified", "promoted", "promotion_ready"}),
                    "message": "object resembles certification/promotion verdict outside canonical owners",
                }
            )

        artifact_type = str(obj.get("artifact_type", "")).strip().lower()
        schema_ref = str(obj.get("schema_ref", "")).strip().lower()
        if artifact_type and _ARTIFACT_AUTHORITY_PATTERN.search(artifact_type):
            violations.append(
                {
                    "rule": "authority_shape_artifact_type",
                    "path": rel_path,
                    "object_index": index,
                    "artifact_type": artifact_type,
                    "message": "authority-shaped artifact_type found outside canonical owners",
                }
            )
        if schema_ref and _ARTIFACT_AUTHORITY_PATTERN.search(schema_ref):
            violations.append(
                {
                    "rule": "authority_shape_schema_ref",
                    "path": rel_path,
                    "object_index": index,
                    "schema_ref": schema_ref,
                    "message": "authority-shaped schema_ref found outside canonical owners",
                }
            )

        assertions = obj.get("non_authority_assertions")
        if isinstance(assertions, list):
            # Substantive governed artifacts are contract-registered: they
            # carry an ``artifact_type`` whose schema in
            # ``contracts/schemas/`` constrains ``producer_authority`` to a
            # const value that matches the inspected object. Setting
            # ``producer_authority`` alone is not sufficient — the schema
            # must exist and bind the value, which is itself reviewed
            # governance. Substantive artifacts skip the preparatory-only
            # subtree (which is meant for un-owned placeholder blobs) but
            # still flag at the identifier and forbidden-field levels.
            is_substantive = _is_governed_substantive_artifact(obj)
            assertion_set = {str(item).strip().lower() for item in assertions}
            if not is_substantive:
                if required_assertions and not required_assertions.issubset(assertion_set):
                    violations.append(
                        {
                            "rule": "preparatory_assertions_missing",
                            "path": rel_path,
                            "object_index": index,
                            "expected": sorted(required_assertions),
                            "actual": sorted(assertion_set),
                            "message": "preparatory artifact missing required non_authority_assertions",
                        }
                    )
                undeclared_fields = sorted(key for key in keys if key not in allowed_preparatory_fields)
                if undeclared_fields:
                    violations.append(
                        {
                            "rule": "preparatory_fields_not_allowlisted",
                            "path": rel_path,
                            "object_index": index,
                            "allowed_fields": sorted(allowed_preparatory_fields),
                            "undeclared_fields": undeclared_fields,
                            "message": "preparatory-only artifact contains fields outside preparatory_only.allowed_fields",
                        }
                    )

            forbidden_found = sorted(
                key for key in keys if key in set(FORBIDDEN_FIELDS)
            )
            forbidden_values = sorted(
                value
                for value in FORBIDDEN_VALUES
                if json.dumps(obj, sort_keys=True).lower().find(f'"{value}"') != -1
            )
            if forbidden_found or forbidden_values:
                violations.append(
                    {
                        "rule": "preparatory_contains_authority",
                        "path": rel_path,
                        "object_index": index,
                        "fields": forbidden_found,
                        "values": forbidden_values,
                        "message": "preparatory-only artifact contains authority semantics",
                    }
                )

    return violations
