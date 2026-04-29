"""HOP-local schema loader and validator.

The repo-wide ``spectrum_systems.contracts.load_schema`` helper expects a flat
``contracts/schemas`` layout. HOP schemas live under ``contracts/schemas/hop/``
to keep a clean, namespaced surface, so HOP ships its own loader. Validation
is fail-closed: malformed payloads raise ``HopSchemaError`` and never return.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

_REPO_ROOT = Path(__file__).resolve().parents[3]
_HOP_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas" / "hop"

_SCHEMA_FILES: Mapping[str, str] = {
    "hop_harness_candidate": "harness_candidate.schema.json",
    "hop_harness_run": "harness_run.schema.json",
    "hop_harness_score": "harness_score.schema.json",
    "hop_harness_trace": "harness_trace.schema.json",
    "hop_harness_frontier": "harness_frontier.schema.json",
    "hop_harness_failure_hypothesis": "harness_failure_hypothesis.schema.json",
    "hop_harness_eval_case": "harness_eval_case.schema.json",
    "hop_harness_faq_output": "harness_faq_output.schema.json",
    "hop_harness_trace_diff": "harness_trace_diff.schema.json",
    "hop_harness_pattern_draft_verify": "harness_pattern_draft_verify.schema.json",
    "hop_harness_pattern_label_primer": "harness_pattern_label_primer.schema.json",
    "hop_harness_routing_observation": "harness_routing_observation.schema.json",
    "hop_harness_bootstrap_snapshot": "harness_bootstrap_snapshot.schema.json",
    "hop_harness_trial_summary": "harness_trial_summary.schema.json",
    "hop_harness_release_readiness_signal": "harness_release_readiness_signal.schema.json",
    "hop_harness_rollback_signal": "harness_rollback_signal.schema.json",
    "hop_harness_eval_factory_record": "harness_eval_factory_record.schema.json",
    "hop_harness_trend_report": "harness_trend_report.schema.json",
    "hop_harness_control_advisory": "harness_control_advisory.schema.json",
    "hop_harness_extraction_signal": "harness_extraction_signal.schema.json",
}


class HopSchemaError(Exception):
    """Raised when a HOP artifact fails schema validation."""


def list_hop_schemas() -> list[str]:
    return sorted(_SCHEMA_FILES.keys())


def schema_path(artifact_type: str) -> Path:
    if artifact_type not in _SCHEMA_FILES:
        raise HopSchemaError(f"hop_schema_unknown:{artifact_type}")
    return _HOP_SCHEMA_DIR / _SCHEMA_FILES[artifact_type]


_REQUIRED_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def load_hop_schema(artifact_type: str) -> dict[str, Any]:
    path = schema_path(artifact_type)
    if not path.is_file():
        raise HopSchemaError(f"hop_schema_missing:{artifact_type}:{path}")
    schema = json.loads(path.read_text(encoding="utf-8"))
    declared = schema.get("$schema")
    if declared != _REQUIRED_DIALECT:
        raise HopSchemaError(
            f"hop_schema_unsupported_dialect:{artifact_type}:{declared}"
        )
    if schema.get("additionalProperties", True) is not False:
        raise HopSchemaError(
            f"hop_schema_must_forbid_additional_properties:{artifact_type}"
        )
    return schema


def validate_hop_artifact(payload: Any, artifact_type: str) -> None:
    """Validate ``payload`` against the HOP schema for ``artifact_type``.

    Raises :class:`HopSchemaError` on any structural violation. Never returns
    a value: callers rely on absence-of-exception for validity.
    """
    if not isinstance(payload, dict):
        raise HopSchemaError(f"hop_artifact_not_object:{artifact_type}:{type(payload).__name__}")
    schema = load_hop_schema(artifact_type)
    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
    except ValidationError as exc:
        path = "/".join(str(p) for p in exc.absolute_path) or "<root>"
        raise HopSchemaError(
            f"hop_artifact_invalid:{artifact_type}:{path}:{exc.message}"
        ) from exc
