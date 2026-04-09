"""Fail-closed FRE fix-plan artifact intake (non-authoritative consumer)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class FixPlanError(ValueError):
    """Raised when FRE-produced fix-plan artifact intake fails fail-closed checks."""


def _load_json(path: str | Path) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FixPlanError(f"expected object artifact: {path}")
    return payload


def build_fix_plan_artifact(*, manifest: Dict[str, Any], decision: Dict[str, Any], remediation: Dict[str, Any]) -> Dict[str, Any]:
    fre_fix_plan_ref = remediation.get("fre_fix_plan_artifact_ref") or decision.get("fre_fix_plan_artifact_ref")
    if not isinstance(fre_fix_plan_ref, str) or not fre_fix_plan_ref.strip():
        raise FixPlanError("missing FRE fix-plan artifact reference: fre_fix_plan_artifact_ref")
    path = Path(fre_fix_plan_ref)
    if not path.is_file():
        raise FixPlanError("missing FRE fix-plan artifact file")

    artifact = _load_json(path)
    validator = Draft202012Validator(load_schema("fix_plan_artifact"), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise FixPlanError(f"FRE fix-plan artifact failed schema validation: {details}")

    policy_id = str(artifact.get("policy_id") or "")
    if not policy_id.startswith("FRE_"):
        raise FixPlanError("FRE fix-plan artifact must declare policy_id prefixed with FRE_")

    trace_id = decision.get("trace_id")
    if isinstance(trace_id, str) and trace_id and artifact.get("decision_id") != decision.get("decision_id"):
        raise FixPlanError("FRE fix-plan artifact decision linkage mismatch")

    _ = manifest  # explicit non-authoritative intake; manifest is consumed only for call compatibility.
    return artifact
