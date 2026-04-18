"""Authority vocabulary rules for fail-closed leak detection."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_FIELDS = [
    "decision",
    "enforcement_action",
    "certification_status",
    "certified",
    "promoted",
    "promotion_ready",
]

FORBIDDEN_VALUES = [
    "allow",
    "block",
    "freeze",
    "promote",
]


def load_authority_registry(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("authority registry must be a JSON object")
    if "categories" not in payload:
        raise ValueError("authority registry missing categories")
    return payload


def _normalize(path: str) -> str:
    raw = path.replace("\\", "/")
    if raw.startswith(str(REPO_ROOT).replace("\\", "/") + "/"):
        raw = raw[len(str(REPO_ROOT).replace("\\", "/")) + 1 :]
    return raw


def _owner_prefixes(registry: dict[str, Any]) -> tuple[str, ...]:
    prefixes: list[str] = []
    categories = registry.get("categories", {})
    if isinstance(categories, dict):
        for row in categories.values():
            owners = row.get("canonical_owners", []) if isinstance(row, dict) else []
            for owner in owners:
                for prefix in owner.get("owner_path_prefixes", []):
                    prefixes.append(str(prefix))
    return tuple(sorted(set(prefixes)))


def _matches_declared_owner_path(normalized_path: str, declared_path: str) -> bool:
    normalized_declared = _normalize(str(declared_path)).strip()
    if not normalized_declared:
        return False
    if normalized_declared.endswith("/"):
        boundary = normalized_declared.strip("/") + "/"
        return normalized_path.startswith(boundary)
    return normalized_path == normalized_declared.strip("/")


def _matches_scope_entry(normalized_path: str, entry: str) -> bool:
    normalized_entry = _normalize(entry).strip()
    if not normalized_entry:
        return False
    if normalized_entry.endswith("/"):
        return normalized_path.startswith(normalized_entry.strip("/") + "/")
    return normalized_path == normalized_entry.strip("/")


def is_owner_path(path: str, registry: dict[str, Any]) -> bool:
    normalized = _normalize(path).strip("/")
    for prefix in _owner_prefixes(registry):
        if _matches_declared_owner_path(normalized, prefix):
            return True
    return False


def _in_forbidden_context_scope(path: str, registry: dict[str, Any]) -> bool:
    normalized = _normalize(path).strip("/")
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


def _get_override_set(registry: dict[str, Any], key: str, path: str) -> set[str]:
    overrides = registry.get("vocabulary_overrides", {})
    if not isinstance(overrides, dict):
        return set()
    table = overrides.get(key, {})
    if not isinstance(table, dict):
        return set()
    allowed: set[str] = set()
    normalized = _normalize(path)
    for prefix, values in table.items():
        if normalized.startswith(str(prefix)):
            allowed.update(str(v).strip().lower() for v in (values or []))
    return allowed


def _extract_py_keys_and_values(path: Path) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    keys: list[tuple[int, str]] = []
    values: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.append((key.lineno, key.value.strip().lower()))
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    values.append((value.lineno, value.value.strip().lower()))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            values.append((node.lineno, node.value.strip().lower()))
    return keys, values


def _extract_json_keys_and_values(payload: Any, lineno: int = 1) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    keys: list[tuple[int, str]] = []
    values: list[tuple[int, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            keys.append((lineno, str(key).strip().lower()))
            child_keys, child_values = _extract_json_keys_and_values(value, lineno)
            keys.extend(child_keys)
            values.extend(child_values)
    elif isinstance(payload, list):
        for value in payload:
            child_keys, child_values = _extract_json_keys_and_values(value, lineno)
            keys.extend(child_keys)
            values.extend(child_values)
    elif isinstance(payload, str):
        values.append((lineno, payload.strip().lower()))
    return keys, values


def find_forbidden_vocabulary(path: Path, registry: dict[str, Any]) -> list[dict[str, Any]]:
    rel_path = _normalize(str(path))
    if not _in_forbidden_context_scope(rel_path, registry):
        return []
    if is_owner_path(rel_path, registry):
        return []

    field_overrides = _get_override_set(registry, "allowed_fields", rel_path)
    value_overrides = _get_override_set(registry, "allowed_values", rel_path)

    keys: list[tuple[int, str]] = []
    values: list[tuple[int, str]] = []

    suffix = path.suffix.lower()
    if suffix == ".py":
        keys, values = _extract_py_keys_and_values(path)
    elif suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        keys, values = _extract_json_keys_and_values(payload)
    else:
        text = path.read_text(encoding="utf-8")
        for idx, line in enumerate(text.splitlines(), start=1):
            for match in re.finditer(r"\b(decision|enforcement_action|certification_status|certified|promoted|promotion_ready)\b", line, flags=re.IGNORECASE):
                keys.append((idx, match.group(1).lower()))
            for match in re.finditer(r"\b(allow|block|freeze|promote)\b", line, flags=re.IGNORECASE):
                values.append((idx, match.group(1).lower()))

    violations: list[dict[str, Any]] = []
    for line, field in keys:
        if field in FORBIDDEN_FIELDS and field not in field_overrides:
            violations.append(
                {
                    "rule": "forbidden_field",
                    "path": rel_path,
                    "line": line,
                    "token": field,
                    "message": f"forbidden authority field '{field}' outside canonical owners",
                }
            )
    for line, value in values:
        if value in FORBIDDEN_VALUES and value not in value_overrides:
            violations.append(
                {
                    "rule": "forbidden_value",
                    "path": rel_path,
                    "line": line,
                    "token": value,
                    "message": f"forbidden authority value '{value}' outside canonical owners",
                }
            )
    return violations
