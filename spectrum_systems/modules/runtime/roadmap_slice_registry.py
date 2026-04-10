"""Canonical roadmap slice registry loader + fail-closed consistency validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spectrum_systems.modules.runtime.execution_hierarchy import (
    ExecutionHierarchyError,
    validate_execution_hierarchy,
)


class RoadmapSliceRegistryError(ValueError):
    """Raised when canonical roadmap registry artifacts are invalid."""


_REQUIRED_SLICE_FIELDS = (
    "slice_id",
    "what_it_does",
    "purpose",
    "why_it_matters",
    "execution_type",
    "commands",
    "success_criteria",
    "implementation_notes",
    "likely_entrypoints",
    "likely_tests",
    "invariants",
)

_ALLOWED_EXECUTION_TYPES = {"code", "validation", "repair", "governance"}


def _load_json_object(path: Path | str, *, label: str) -> dict[str, Any]:
    file_path = Path(path)
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RoadmapSliceRegistryError(f"{label} artifact not found: {file_path}") from exc
    except json.JSONDecodeError as exc:
        raise RoadmapSliceRegistryError(f"{label} artifact is not valid JSON: {file_path}") from exc

    if not isinstance(payload, dict):
        raise RoadmapSliceRegistryError(f"{label} artifact root must be an object")
    return payload


def _as_non_empty_string(value: Any, *, field: str, slice_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RoadmapSliceRegistryError(f"slice {slice_id} has invalid {field}: expected non-empty string")
    return value.strip()


def _as_string_list(value: Any, *, field: str, slice_id: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise RoadmapSliceRegistryError(f"slice {slice_id} has invalid {field}: expected non-empty list")
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise RoadmapSliceRegistryError(f"slice {slice_id} has invalid {field}: entries must be non-empty strings")
        cleaned.append(item.strip())
    return cleaned


def _validate_command_determinism(command: str, *, slice_id: str) -> None:
    risky_tokens = (
        "$RANDOM",
        "uuidgen",
        "$(date",
        "`date`",
        " time ",
        " sleep ",
    )
    lowered = f" {command.lower()} "
    if command.startswith("/"):
        raise RoadmapSliceRegistryError(
            f"slice {slice_id} has invalid commands: command must be repo-relative, got absolute path"
        )
    if "http://" in lowered or "https://" in lowered:
        raise RoadmapSliceRegistryError(
            f"slice {slice_id} has invalid commands: network-dependent command is not deterministic"
        )
    if " date " in lowered or " random " in lowered:
        raise RoadmapSliceRegistryError(
            f"slice {slice_id} has invalid commands: time/random dependent command is not deterministic"
        )
    for token in risky_tokens:
        if token.lower() in lowered:
            raise RoadmapSliceRegistryError(
                f"slice {slice_id} has invalid commands: contains non-deterministic token {token!r}"
            )


def validate_pqx_slice_execution_compatibility(slices: list[dict[str, Any]]) -> None:
    for row in slices:
        slice_id = _as_non_empty_string(row.get("slice_id"), field="slice_id", slice_id="<unknown>")
        execution_type = _as_non_empty_string(row.get("execution_type"), field="execution_type", slice_id=slice_id)
        if execution_type not in _ALLOWED_EXECUTION_TYPES:
            raise RoadmapSliceRegistryError(
                f"slice {slice_id} has invalid execution_type: {execution_type!r} not in {sorted(_ALLOWED_EXECUTION_TYPES)}"
            )
        commands = _as_string_list(row.get("commands"), field="commands", slice_id=slice_id)
        success_criteria = _as_string_list(row.get("success_criteria"), field="success_criteria", slice_id=slice_id)
        for command in commands:
            _validate_command_determinism(command, slice_id=slice_id)
        if any(not criterion.strip() for criterion in success_criteria):
            raise RoadmapSliceRegistryError(
                f"slice {slice_id} has invalid success_criteria: entries must be non-empty strings"
            )


def validate_slice_registry(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("artifact_type") != "slice_registry":
        raise RoadmapSliceRegistryError("slice registry artifact_type must be 'slice_registry'")

    raw_slices = payload.get("slices")
    if not isinstance(raw_slices, list) or not raw_slices:
        raise RoadmapSliceRegistryError("slice registry must include a non-empty slices list")

    normalized: list[dict[str, Any]] = []
    seen_slice_ids: set[str] = set()
    for row in raw_slices:
        if not isinstance(row, dict):
            raise RoadmapSliceRegistryError("slice registry entries must be objects")

        slice_id = _as_non_empty_string(row.get("slice_id"), field="slice_id", slice_id="<unknown>")
        if slice_id in seen_slice_ids:
            raise RoadmapSliceRegistryError(f"duplicate slice_id in registry: {slice_id}")
        seen_slice_ids.add(slice_id)

        for field in _REQUIRED_SLICE_FIELDS:
            if field not in row:
                raise RoadmapSliceRegistryError(f"slice {slice_id} missing required field: {field}")

        normalized.append(
            {
                "slice_id": slice_id,
                "what_it_does": _as_non_empty_string(row.get("what_it_does"), field="what_it_does", slice_id=slice_id),
                "purpose": _as_non_empty_string(row.get("purpose"), field="purpose", slice_id=slice_id),
                "why_it_matters": _as_non_empty_string(
                    row.get("why_it_matters"), field="why_it_matters", slice_id=slice_id
                ),
                "execution_type": _as_non_empty_string(
                    row.get("execution_type"), field="execution_type", slice_id=slice_id
                ),
                "commands": _as_string_list(row.get("commands"), field="commands", slice_id=slice_id),
                "success_criteria": _as_string_list(
                    row.get("success_criteria"), field="success_criteria", slice_id=slice_id
                ),
                "implementation_notes": _as_non_empty_string(
                    row.get("implementation_notes"), field="implementation_notes", slice_id=slice_id
                ),
                "likely_entrypoints": _as_string_list(
                    row.get("likely_entrypoints"), field="likely_entrypoints", slice_id=slice_id
                ),
                "likely_tests": _as_string_list(row.get("likely_tests"), field="likely_tests", slice_id=slice_id),
                "invariants": _as_string_list(row.get("invariants"), field="invariants", slice_id=slice_id),
                "status": _as_non_empty_string(row.get("status", "planned"), field="status", slice_id=slice_id),
                "source_basis": _as_string_list(
                    row.get("source_basis", ["inferred"]), field="source_basis", slice_id=slice_id
                ),
            }
        )

    validate_pqx_slice_execution_compatibility(normalized)
    return sorted(normalized, key=lambda item: item["slice_id"])


def validate_roadmap_structure(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("artifact_type") != "roadmap_structure":
        raise RoadmapSliceRegistryError("roadmap structure artifact_type must be 'roadmap_structure'")

    umbrellas = payload.get("umbrellas")
    if not isinstance(umbrellas, list) or not umbrellas:
        raise RoadmapSliceRegistryError("roadmap structure must include a non-empty umbrellas list")

    try:
        validate_execution_hierarchy(payload, label="roadmap_structure")
    except ExecutionHierarchyError as exc:
        raise RoadmapSliceRegistryError(str(exc)) from exc

    normalized_umbrellas: list[dict[str, Any]] = []
    for umbrella in umbrellas:
        if not isinstance(umbrella, dict):
            raise RoadmapSliceRegistryError("umbrella entries must be objects")
        umbrella_id = _as_non_empty_string(umbrella.get("umbrella_id"), field="umbrella_id", slice_id="<umbrella>")
        batches = umbrella.get("batches")
        if not isinstance(batches, list) or not batches:
            raise RoadmapSliceRegistryError(f"umbrella {umbrella_id} must include non-empty batches")
        normalized_batches: list[dict[str, Any]] = []
        for batch in batches:
            if not isinstance(batch, dict):
                raise RoadmapSliceRegistryError(f"umbrella {umbrella_id} includes non-object batch")
            batch_id = _as_non_empty_string(batch.get("batch_id"), field="batch_id", slice_id=f"{umbrella_id}::<batch>")
            slice_ids = _as_string_list(batch.get("slice_ids"), field="slice_ids", slice_id=batch_id)
            if len(slice_ids) < 2:
                raise RoadmapSliceRegistryError(
                    f"invalid batch cardinality for {batch_id}: slice_ids must contain at least 2 slices"
                )
            normalized_batches.append({"batch_id": batch_id, "slice_ids": sorted(set(slice_ids))})
        normalized_umbrellas.append(
            {
                "umbrella_id": umbrella_id,
                "batches": sorted(normalized_batches, key=lambda item: item["batch_id"]),
            }
        )

    reserved_slice_ids = payload.get("reserved_slice_ids", [])
    if not isinstance(reserved_slice_ids, list):
        raise RoadmapSliceRegistryError("roadmap_structure.reserved_slice_ids must be a list")
    reserved = _as_string_list(reserved_slice_ids, field="reserved_slice_ids", slice_id="<structure>") if reserved_slice_ids else []

    return {
        "artifact_type": "roadmap_structure",
        "version": str(payload.get("version", "1.0.0")),
        "umbrellas": sorted(normalized_umbrellas, key=lambda item: item["umbrella_id"]),
        "reserved_slice_ids": sorted(set(reserved)),
    }


def validate_registry_structure_consistency(
    slices: list[dict[str, Any]],
    structure: dict[str, Any],
) -> None:
    slice_ids = {row["slice_id"] for row in slices}
    reserved_slice_ids = set(structure.get("reserved_slice_ids", []))

    mapped: dict[str, str] = {}
    for umbrella in structure["umbrellas"]:
        umbrella_id = umbrella["umbrella_id"]
        for batch in umbrella["batches"]:
            batch_id = batch["batch_id"]
            placement = f"{umbrella_id}/{batch_id}"
            for slice_id in batch["slice_ids"]:
                if slice_id not in slice_ids:
                    raise RoadmapSliceRegistryError(f"roadmap structure references unknown slice_id: {slice_id}")
                if slice_id in mapped:
                    raise RoadmapSliceRegistryError(
                        f"duplicate slice placement without explicit allowance: {slice_id} in {mapped[slice_id]} and {placement}"
                    )
                mapped[slice_id] = placement

    unmapped = sorted(slice_ids - set(mapped) - reserved_slice_ids)
    if unmapped:
        raise RoadmapSliceRegistryError(
            "slice_registry contains unplaced slices that are not reserved: " + ", ".join(unmapped)
        )


def load_slice_registry(path: Path | str) -> list[dict[str, Any]]:
    payload = _load_json_object(path, label="slice_registry")
    return validate_slice_registry(payload)


def load_roadmap_structure(path: Path | str) -> dict[str, Any]:
    payload = _load_json_object(path, label="roadmap_structure")
    return validate_roadmap_structure(payload)


def load_governed_slice_registry_artifacts(
    *,
    slice_registry_path: Path | str,
    roadmap_structure_path: Path | str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    slices = load_slice_registry(slice_registry_path)
    structure = load_roadmap_structure(roadmap_structure_path)
    validate_registry_structure_consistency(slices, structure)
    return slices, structure


__all__ = [
    "RoadmapSliceRegistryError",
    "load_governed_slice_registry_artifacts",
    "load_roadmap_structure",
    "load_slice_registry",
    "validate_registry_structure_consistency",
    "validate_roadmap_structure",
    "validate_pqx_slice_execution_compatibility",
    "validate_slice_registry",
]
