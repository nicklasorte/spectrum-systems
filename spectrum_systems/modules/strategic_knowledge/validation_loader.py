"""Controlled IO adapter for strategic knowledge validation gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .validator import validate_strategic_knowledge_artifact


def load_artifact_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"artifact path does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_source_catalog_payload(data_lake_root: Path) -> dict[str, Any]:
    catalog_path = data_lake_root / "strategic_knowledge" / "metadata" / "source_catalog.json"
    if not catalog_path.exists():
        return {}
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def load_artifact_registry_payload(data_lake_root: Path) -> dict[str, Any] | None:
    registry_path = data_lake_root / "strategic_knowledge" / "lineage" / "artifact_registry.json"
    if not registry_path.exists():
        return None
    return json.loads(registry_path.read_text(encoding="utf-8"))


def validate_strategic_knowledge_artifact_from_paths(
    *,
    artifact_path: Path,
    data_lake_root: Path,
) -> dict[str, Any]:
    artifact = load_artifact_payload(artifact_path)
    source_catalog = load_source_catalog_payload(data_lake_root)
    artifact_registry = load_artifact_registry_payload(data_lake_root)
    return validate_strategic_knowledge_artifact(
        artifact,
        {
            "source_catalog": source_catalog,
            "artifact_registry": artifact_registry,
        },
    )


__all__ = [
    "load_artifact_payload",
    "load_source_catalog_payload",
    "load_artifact_registry_payload",
    "validate_strategic_knowledge_artifact_from_paths",
]
