"""Thin load + validation helpers for BBC dataset governance artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


def _load_and_validate(path: str, schema_name: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    schema = load_schema(schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
    return payload


def load_eval_admission_policy(path: str) -> dict[str, Any]:
    """Load and validate an eval_admission_policy artifact from disk."""
    return _load_and_validate(path, "eval_admission_policy")


def load_eval_dataset(path: str) -> dict[str, Any]:
    """Load and validate an eval_dataset artifact from disk."""
    return _load_and_validate(path, "eval_dataset")


def load_eval_canonicalization_policy(path: str) -> dict[str, Any]:
    """Load and validate an eval_canonicalization_policy artifact from disk."""
    return _load_and_validate(path, "eval_canonicalization_policy")


def load_eval_registry_snapshot(path: str) -> dict[str, Any]:
    """Load and validate an eval_registry_snapshot artifact from disk."""
    return _load_and_validate(path, "eval_registry_snapshot")
