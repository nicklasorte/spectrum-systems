"""Canonical artifact-class taxonomy loader and validators."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_CLASS_REGISTRY_PATH = REPO_ROOT / "contracts" / "artifact-class-registry.json"


@lru_cache(maxsize=1)
def load_allowed_artifact_classes() -> tuple[str, ...]:
    registry = json.loads(ARTIFACT_CLASS_REGISTRY_PATH.read_text(encoding="utf-8"))
    classes = tuple(sorted(entry["name"] for entry in registry.get("artifact_classes", [])))
    if not classes:
        raise ValueError("artifact-class-registry.json does not define any artifact_classes")
    return classes


def ensure_allowed_artifact_class(value: str) -> None:
    if value not in load_allowed_artifact_classes():
        raise ValueError(
            f"artifact_class '{value}' is not allowed; expected one of {list(load_allowed_artifact_classes())}"
        )
