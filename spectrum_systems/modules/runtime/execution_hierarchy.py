"""Fail-closed validation for governed execution hierarchy cardinality."""

from __future__ import annotations

from typing import Any


class ExecutionHierarchyError(ValueError):
    """Raised when execution hierarchy cardinality or authority rules are invalid."""


def _non_empty_name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExecutionHierarchyError("hierarchy entry id must be a non-empty string")
    return value.strip()


def _require_items(label: str, value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise ExecutionHierarchyError(f"{label} must be a list")
    return value


def _find_batch_slice_collection(batch: dict[str, Any]) -> tuple[str, list[Any]] | None:
    for key in ("slice_ids", "slices"):
        if key in batch:
            return key, _require_items(f"batch.{key}", batch[key])
    return None


def validate_execution_hierarchy(payload: dict[str, Any], *, label: str = "payload") -> None:
    """Validate canonical hierarchy cardinality with fail-closed behavior.

    Rules enforced:
    - Declared batches with explicit slice collections must include >= 2 slices.
    - Declared umbrellas must include >= 2 batches.
    - Batch/umbrella wrappers must not be pass-through (single-member) wrappers.
    """

    if not isinstance(payload, dict):
        raise ExecutionHierarchyError(f"{label} must be an object")

    batches = payload.get("batches")
    if batches is not None:
        for index, batch in enumerate(_require_items(f"{label}.batches", batches), start=1):
            if not isinstance(batch, dict):
                raise ExecutionHierarchyError(f"{label}.batches[{index}] must be an object")
            collection = _find_batch_slice_collection(batch)
            if collection is None:
                continue
            key, slices = collection
            if len(slices) < 2:
                batch_id = _non_empty_name(batch.get("batch_id") or f"index-{index}")
                raise ExecutionHierarchyError(
                    f"invalid batch cardinality for {batch_id}: {key} must contain at least 2 slices"
                )

    umbrellas = payload.get("umbrellas")
    if umbrellas is not None:
        for index, umbrella in enumerate(_require_items(f"{label}.umbrellas", umbrellas), start=1):
            if not isinstance(umbrella, dict):
                raise ExecutionHierarchyError(f"{label}.umbrellas[{index}] must be an object")
            umbrella_id = _non_empty_name(umbrella.get("umbrella_id") or f"index-{index}")
            if "batch_ids" in umbrella:
                batch_refs = _require_items(f"{label}.umbrellas[{index}].batch_ids", umbrella.get("batch_ids"))
            elif "batches" in umbrella:
                batch_refs = _require_items(f"{label}.umbrellas[{index}].batches", umbrella.get("batches"))
            else:
                raise ExecutionHierarchyError(
                    f"invalid umbrella definition for {umbrella_id}: batch_ids or batches is required"
                )
            if len(batch_refs) < 2:
                raise ExecutionHierarchyError(
                    f"invalid umbrella cardinality for {umbrella_id}: umbrellas must contain at least 2 batches"
                )


__all__ = ["ExecutionHierarchyError", "validate_execution_hierarchy"]
