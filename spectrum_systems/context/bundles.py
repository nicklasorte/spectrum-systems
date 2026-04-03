from __future__ import annotations

from typing import Any, Dict, Iterable, List


class ContextBuildError(RuntimeError):
    """Raised when context bundle completeness checks fail."""


def build_context_bundle(recipe: Dict[str, Any], provided_sources: Dict[str, Any], *, bundle_id: str) -> Dict[str, Any]:
    required = list(recipe.get("required_sources", []))
    missing = sorted(source for source in required if source not in provided_sources)
    if missing:
        raise ContextBuildError(f"missing required context sources: {missing}")

    return {
        "artifact_type": "context_bundle_record",
        "schema_version": "1.0.0",
        "bundle_id": bundle_id,
        "recipe_id": recipe["recipe_id"],
        "inputs": {k: provided_sources[k] for k in sorted(provided_sources)},
        "resolved_sources": sorted(provided_sources),
        "missing_required_sources": [],
    }


def detect_context_conflicts(source_a_id: str, source_b_id: str, field: str, left: Any, right: Any) -> Dict[str, Any] | None:
    if left == right:
        return None
    return {
        "artifact_type": "context_conflict_record",
        "schema_version": "1.0.0",
        "conflict_id": "ccr-" + f"{abs(hash((source_a_id, source_b_id, field, str(left), str(right)))) & ((1<<64)-1):016x}",
        "source_a": source_a_id,
        "source_b": source_b_id,
        "field": field,
        "resolution_status": "open",
    }
