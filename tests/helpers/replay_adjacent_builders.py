"""Shared canonical builders for replay-adjacent governed test artifacts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from spectrum_systems.contracts import load_example, load_schema


def _schema_const(schema_name: str) -> str:
    schema = load_schema(schema_name)
    value = schema.get("properties", {}).get("schema_version", {}).get("const")
    return str(value or "")


def make_canonical_observability_metrics(*, replay_success_rate: float = 1.0, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return schema-valid observability_metrics seeded from the canonical example."""
    artifact = deepcopy(load_example("observability_metrics"))
    artifact["schema_version"] = _schema_const("observability_metrics")
    artifact.setdefault("metrics", {})["replay_success_rate"] = replay_success_rate

    if overrides:
        artifact.update(deepcopy(overrides))
    return artifact
