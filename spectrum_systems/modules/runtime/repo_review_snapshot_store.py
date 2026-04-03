"""Deterministic storage helper for governed ``repo_review_snapshot`` artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class RepoReviewSnapshotStoreError(ValueError):
    """Raised when snapshot payloads or storage operations fail closed."""


def validate_repo_review_snapshot(snapshot: Dict[str, Any]) -> None:
    schema = load_schema("repo_review_snapshot")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(snapshot), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise RepoReviewSnapshotStoreError(f"repo_review_snapshot failed schema validation: {details}")


def write_repo_review_snapshot(snapshot: Dict[str, Any], output_path: Path) -> Path:
    validate_repo_review_snapshot(snapshot)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def read_repo_review_snapshot(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RepoReviewSnapshotStoreError(f"repo_review_snapshot artifact not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RepoReviewSnapshotStoreError(f"repo_review_snapshot artifact is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise RepoReviewSnapshotStoreError("repo_review_snapshot artifact root must be a JSON object")
    validate_repo_review_snapshot(payload)
    return payload


__all__ = [
    "RepoReviewSnapshotStoreError",
    "read_repo_review_snapshot",
    "validate_repo_review_snapshot",
    "write_repo_review_snapshot",
]
