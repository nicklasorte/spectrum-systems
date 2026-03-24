"""HS-01 Prompt Registry + Versioning System.

Deterministic, fail-closed prompt registry loading and alias resolution.
No fallback-to-latest behavior is permitted.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class PromptRegistryError(RuntimeError):
    """Raised when prompt registry artifacts are malformed or non-resolvable."""


def _validate(instance: Dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PromptRegistryError(f"missing prompt artifact file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PromptRegistryError(f"malformed prompt artifact JSON at {path}: {exc}") from exc


def _entry_key(entry: Dict[str, Any]) -> Tuple[str, str]:
    return (str(entry["prompt_id"]), str(entry["prompt_version"]))


def _assert_entry_semantics(entry: Dict[str, Any]) -> None:
    prompt_id = str(entry["prompt_id"])
    prompt_version = str(entry["prompt_version"])
    expected_selection_key = f"{prompt_id}@{prompt_version}"
    actual_selection_key = str(entry["runtime_metadata"]["selection_key"])
    if actual_selection_key != expected_selection_key:
        raise PromptRegistryError(
            "prompt registry entry selection_key mismatch: "
            f"expected '{expected_selection_key}', got '{actual_selection_key}'"
        )

    prompt_text = str(entry["prompt_text"])
    expected_hash = "sha256:" + hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    actual_hash = str(entry["runtime_metadata"]["immutability_hash"])
    if actual_hash != expected_hash:
        raise PromptRegistryError(
            "prompt registry entry immutability_hash mismatch: "
            f"expected '{expected_hash}', got '{actual_hash}'"
        )


def load_prompt_registry_entries(paths: Iterable[Path]) -> List[Dict[str, Any]]:
    """Load and validate immutable prompt registry entries from explicit paths."""
    entries: List[Dict[str, Any]] = []
    for path in paths:
        entry = _load_json(Path(path))
        _validate(entry, "prompt_registry_entry")
        _assert_entry_semantics(entry)
        entries.append(entry)

    if not entries:
        raise PromptRegistryError("prompt registry is empty")

    seen: Dict[Tuple[str, str], Path] = {}
    for path, entry in zip(paths, entries):
        key = _entry_key(entry)
        if key in seen:
            raise PromptRegistryError(
                "duplicate immutable prompt entry detected for "
                f"{key[0]}@{key[1]} in {seen[key]} and {path}"
            )
        seen[key] = Path(path)

    return sorted(entries, key=lambda e: (str(e["prompt_id"]), str(e["prompt_version"])))


def load_prompt_alias_map(path: Path) -> Dict[str, Any]:
    """Load and validate prompt alias map artifact."""
    alias_map = _load_json(Path(path))
    _validate(alias_map, "prompt_alias_map")
    return alias_map


def resolve_prompt_version(
    *,
    prompt_id: str,
    alias: str,
    entries: List[Dict[str, Any]],
    alias_map: Dict[str, Any],
) -> Dict[str, Any]:
    """Resolve (prompt_id, alias) to one immutable prompt entry.

    Fail-closed conditions:
    - missing alias binding
    - ambiguous alias binding
    - missing prompt entry for resolved version
    - draft target status
    - deprecated target without explicit allow_deprecated=true
    """
    if not prompt_id or not alias:
        raise PromptRegistryError("prompt_id and alias are required for resolution")

    bindings = [
        item
        for item in alias_map.get("aliases", [])
        if item.get("prompt_id") == prompt_id and item.get("alias") == alias
    ]

    if not bindings:
        raise PromptRegistryError(f"no alias resolution found for prompt_id='{prompt_id}', alias='{alias}'")
    if len(bindings) != 1:
        raise PromptRegistryError(
            f"ambiguous alias resolution for prompt_id='{prompt_id}', alias='{alias}': {len(bindings)} matches"
        )

    binding = bindings[0]
    resolved_version = str(binding["prompt_version"])
    matching_entries = [e for e in entries if e.get("prompt_id") == prompt_id and e.get("prompt_version") == resolved_version]
    if len(matching_entries) != 1:
        raise PromptRegistryError(
            "alias map points to missing or ambiguous immutable entry for "
            f"{prompt_id}@{resolved_version}"
        )

    entry = matching_entries[0]
    status = str(entry["status"])
    allow_deprecated = bool(binding.get("allow_deprecated"))
    if status == "draft":
        raise PromptRegistryError(f"prompt {prompt_id}@{resolved_version} is draft and cannot be selected at runtime")
    if status == "deprecated" and not allow_deprecated:
        raise PromptRegistryError(
            f"prompt {prompt_id}@{resolved_version} is deprecated and alias '{alias}' does not allow deprecated"
        )
    if status not in {"approved", "deprecated"}:
        raise PromptRegistryError(f"prompt {prompt_id}@{resolved_version} has unsupported status '{status}'")

    return {
        "prompt_id": prompt_id,
        "prompt_version": resolved_version,
        "requested_alias": alias,
        "status": "resolved",
        "resolution_source": "prompt_alias_map",
        "prompt_created_at": entry["created_at"],
        "prompt_status": status,
        "entry": entry,
    }
