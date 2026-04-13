"""Deterministic fail-closed standards manifest completeness validator."""

from __future__ import annotations

from typing import Any

from spectrum_systems.contracts.artifact_class_taxonomy import load_allowed_artifact_classes

REQUIRED_CONTRACT_FIELDS = (
    "artifact_type",
    "artifact_class",
    "schema_path",
    "example_path",
    "intended_consumers",
)

ALLOWED_ARTIFACT_CLASSES = load_allowed_artifact_classes()


def _entry_path(index: int, field: str) -> str:
    return f"contracts[{index}].{field}"


def validate_manifest_completeness(manifest: dict) -> dict:
    """Validate standards-manifest contract entry completeness with strict keys.

    Fail-closed semantics: any structure, type, missing/null, enum, or extra-key issue marks invalid.
    """

    errors: list[str] = []
    missing_fields: list[str] = []
    invalid_entries: list[dict[str, Any]] = []

    if not isinstance(manifest, dict):
        errors.append("manifest must be a JSON object")
        return {
            "valid": False,
            "errors": errors,
            "missing_fields": missing_fields,
            "invalid_entries": invalid_entries,
        }

    contracts = manifest.get("contracts")
    if not isinstance(contracts, list):
        errors.append("contracts must be a list")
        return {
            "valid": False,
            "errors": errors,
            "missing_fields": missing_fields,
            "invalid_entries": invalid_entries,
        }

    for index, entry in enumerate(contracts):
        if not isinstance(entry, dict):
            message = "contract entry must be an object"
            errors.append(f"contracts[{index}] {message}")
            invalid_entries.append({"index": index, "field": "<entry>", "reason": message})
            continue

        extra_keys = sorted(set(entry.keys()) - set(REQUIRED_CONTRACT_FIELDS))
        for key in extra_keys:
            message = f"extra field not allowed: {key}"
            errors.append(f"contracts[{index}] {message}")
            invalid_entries.append({"index": index, "field": key, "reason": message})

        for field in REQUIRED_CONTRACT_FIELDS:
            if field not in entry:
                path = _entry_path(index, field)
                missing_fields.append(path)
                message = f"missing required field: {field}"
                errors.append(f"contracts[{index}] {message}")
                invalid_entries.append({"index": index, "field": field, "reason": message})
                continue

            value = entry[field]
            if value is None:
                path = _entry_path(index, field)
                missing_fields.append(path)
                message = f"field is null: {field}"
                errors.append(f"contracts[{index}] {message}")
                invalid_entries.append({"index": index, "field": field, "reason": message})
                continue

            if field in {"artifact_type", "artifact_class", "schema_path", "example_path"} and not isinstance(value, str):
                message = f"{field} must be a string"
                errors.append(f"contracts[{index}] {message}")
                invalid_entries.append({"index": index, "field": field, "reason": message, "value": value})
                continue

            if field == "artifact_class":
                if value not in ALLOWED_ARTIFACT_CLASSES:
                    message = (
                        f"artifact_class must be one of {list(ALLOWED_ARTIFACT_CLASSES)}"
                    )
                    errors.append(f"contracts[{index}] {message}")
                    invalid_entries.append({"index": index, "field": field, "reason": message, "value": value})

            if field == "intended_consumers":
                if not isinstance(value, list):
                    message = "intended_consumers must be a list"
                    errors.append(f"contracts[{index}] {message}")
                    invalid_entries.append({"index": index, "field": field, "reason": message, "value": value})
                elif not value:
                    message = "intended_consumers must be non-empty"
                    errors.append(f"contracts[{index}] {message}")
                    invalid_entries.append({"index": index, "field": field, "reason": message, "value": value})

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "missing_fields": missing_fields,
        "invalid_entries": invalid_entries,
    }
