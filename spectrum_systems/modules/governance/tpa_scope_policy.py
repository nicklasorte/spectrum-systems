"""Deterministic TPA scope policy loading and evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class TPAScopePolicyError(ValueError):
    """Raised when TPA scope policy cannot be loaded or evaluated."""


_DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[3] / "config" / "policy" / "tpa_scope_policy.json"


def _validate_schema(instance: Dict[str, Any], schema_name: str, *, label: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise TPAScopePolicyError(f"{label} failed schema validation ({schema_name}): {details}")


def load_tpa_scope_policy(path: str | Path | None = None) -> Dict[str, Any]:
    """Load and schema-validate the governed TPA scope policy."""
    policy_path = Path(path) if path is not None else _DEFAULT_POLICY_PATH
    if not policy_path.is_file():
        raise TPAScopePolicyError(f"tpa_scope_policy file not found: {policy_path}")
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TPAScopePolicyError(f"tpa_scope_policy is not valid JSON: {policy_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise TPAScopePolicyError(f"tpa_scope_policy must be a JSON object: {policy_path}")
    _validate_schema(payload, "tpa_scope_policy", label="tpa_scope_policy")
    return payload


def is_tpa_required(context: Dict[str, Any], *, policy: Dict[str, Any] | None = None) -> bool:
    """Return whether TPA is mandatory for the supplied promotion/certification context."""
    if not isinstance(context, dict):
        raise TPAScopePolicyError("tpa scope context must be an object")

    scope_policy = policy if policy is not None else load_tpa_scope_policy()
    if not isinstance(scope_policy, dict):
        raise TPAScopePolicyError("resolved tpa_scope_policy must be an object")

    required_paths = tuple(str(v).strip() for v in scope_policy.get("required_paths", []) if str(v).strip())
    optional_paths = tuple(str(v).strip() for v in scope_policy.get("optional_paths", []) if str(v).strip())
    required_artifact_types = {
        str(v).strip() for v in scope_policy.get("required_artifact_types", []) if str(v).strip()
    }
    required_pqx_steps = tuple(str(v).strip() for v in scope_policy.get("required_pqx_steps", []) if str(v).strip())

    file_path = str(context.get("file_path") or "").strip()
    module = str(context.get("module") or "").strip()
    artifact_type = str(context.get("artifact_type") or "").strip()
    pqx_step_metadata = context.get("pqx_step_metadata")
    pqx_step_id = ""
    if pqx_step_metadata is not None:
        if not isinstance(pqx_step_metadata, dict):
            raise TPAScopePolicyError("pqx_step_metadata must be an object when provided")
        pqx_step_id = str(pqx_step_metadata.get("step_id") or "").strip()

    normalized_path_candidates = tuple(v for v in (file_path, module) if v)

    if normalized_path_candidates and any(
        any(candidate.startswith(prefix) for prefix in optional_paths)
        for candidate in normalized_path_candidates
    ):
        return False

    if artifact_type and artifact_type in required_artifact_types:
        return True

    if pqx_step_id and any(pqx_step_id.startswith(prefix) for prefix in required_pqx_steps):
        return True

    if normalized_path_candidates and any(
        any(candidate.startswith(prefix) for prefix in required_paths)
        for candidate in normalized_path_candidates
    ):
        return True

    return False


__all__ = ["TPAScopePolicyError", "is_tpa_required", "load_tpa_scope_policy"]
