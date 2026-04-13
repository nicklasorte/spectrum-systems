"""Eval registry helpers for bounded artifact family."""

from __future__ import annotations

from typing import Any


def resolve_required_evals(*, registry: dict[str, Any], artifact_family: str) -> list[str]:
    return sorted(
        entry["eval_id"]
        for entry in registry.get("evals", [])
        if entry.get("artifact_family") == artifact_family and entry.get("required", False)
    )
