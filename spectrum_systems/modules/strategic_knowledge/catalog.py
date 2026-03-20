"""Source catalog management for Strategic Knowledge raw source registration."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pathing import SOURCE_DIR_BY_TYPE

VALID_SOURCE_TYPES = frozenset(SOURCE_DIR_BY_TYPE.keys())
VALID_SOURCE_STATUS = frozenset({"registered", "ready", "blocked", "archived"})


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_source_catalog() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "catalog_version": "1.0.0",
        "updated_at": _utcnow_iso(),
        "sources": [],
    }


def load_catalog(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_source_catalog()
    return json.loads(path.read_text(encoding="utf-8"))


def save_catalog(path: Path, catalog: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")


def register_source(
    *,
    source_catalog_path: Path,
    source_id: str,
    source_type: str,
    source_path: str,
    title: str,
    tags: list[str] | None = None,
    status: str = "registered",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not source_id:
        raise ValueError("source_id is required")
    if source_type not in VALID_SOURCE_TYPES:
        raise ValueError(f"Invalid source_type: {source_type}")
    if not source_path.startswith("strategic_knowledge/raw/"):
        raise ValueError("source_path must be under strategic_knowledge/raw/")
    if status not in VALID_SOURCE_STATUS:
        raise ValueError(f"Invalid source status: {status}")
    if not title:
        raise ValueError("title is required")

    catalog = load_catalog(source_catalog_path)
    sources = catalog.setdefault("sources", [])

    if any(existing.get("source_id") == source_id for existing in sources):
        raise ValueError(f"Duplicate source_id: {source_id}")

    entry = {
        "artifact_type": "strategic_knowledge_source_ref",
        "schema_version": "1.0.0",
        "source_id": source_id,
        "source_type": source_type,
        "source_path": source_path,
        "source_status": status,
        "registered_at": _utcnow_iso(),
        "tags": sorted(set(tags or [])),
        "metadata": {"title": title, **(metadata or {})},
    }
    sources.append(entry)
    catalog["updated_at"] = _utcnow_iso()
    save_catalog(source_catalog_path, catalog)
    return entry

