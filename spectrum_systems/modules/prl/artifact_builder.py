"""PRL-01: Builds pr_failure_capture_record and pre_pr_failure_packet artifacts.

All artifacts are schema-validated before return. Fail-closed: schema not found
or validation failure raises immediately — no partial artifacts emitted.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

from spectrum_systems.utils.artifact_envelope import build_artifact_envelope
from spectrum_systems.utils.deterministic_id import deterministic_id
from spectrum_systems.modules.prl.failure_classifier import Classification
from spectrum_systems.modules.prl.failure_parser import ParsedFailure

_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "contracts" / "schemas" / "prl"


def _load_schema(name: str) -> dict[str, Any]:
    path = _SCHEMA_DIR / f"{name}.schema.json"
    if not path.exists():
        raise FileNotFoundError(f"PRL schema not found — fail-closed: {path}")
    with path.open() as f:
        return json.load(f)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate(artifact: dict[str, Any], schema_name: str) -> None:
    schema = _load_schema(schema_name)
    try:
        jsonschema.validate(artifact, schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(
            f"PRL artifact {schema_name} failed schema validation: {exc.message}"
        ) from exc


def build_capture_record(
    *,
    parsed: ParsedFailure,
    classification: Classification,
    source: str,
    run_id: str,
    trace_id: str,
) -> dict[str, Any]:
    """Build a validated pr_failure_capture_record. Fails closed on schema error."""
    ts = _now_iso()
    payload = {
        "failure_class": classification.failure_class,
        "normalized_message": parsed.normalized_message,
        "source": source,
        "run_id": run_id,
        "trace_id": trace_id,
    }
    artifact_id = deterministic_id(
        prefix="prl-cap",
        payload=payload,
        namespace="prl::capture",
    )
    envelope = build_artifact_envelope(
        artifact_id=artifact_id,
        timestamp=ts,
        schema_version="1.0.0",
        primary_trace_ref=trace_id,
    )
    artifact: dict[str, Any] = {
        "artifact_type": "pr_failure_capture_record",
        "schema_version": "1.0.0",
        "id": envelope["id"],
        "timestamp": envelope["timestamp"],
        "run_id": run_id,
        "trace_id": trace_id,
        "trace_refs": envelope["trace_refs"],
        "source": source,
        "raw_log_excerpt": parsed.raw_excerpt,
        "normalized_message": parsed.normalized_message,
        "failure_class": classification.failure_class,
        "owning_system": classification.owning_system,
        "file_refs": list(parsed.file_refs),
    }
    if parsed.line_number is not None:
        artifact["line_number"] = parsed.line_number
    if parsed.exit_code is not None:
        artifact["exit_code"] = parsed.exit_code

    _validate(artifact, "pr_failure_capture_record")
    return artifact


def build_failure_packet(
    *,
    capture_record: dict[str, Any],
    classification: Classification,
    run_id: str,
    trace_id: str,
) -> dict[str, Any]:
    """Build a validated pre_pr_failure_packet. Fails closed on schema error."""
    ts = _now_iso()
    capture_ref = f"pr_failure_capture_record:{capture_record['id']}"
    payload = {
        "capture_ref": capture_ref,
        "failure_class": classification.failure_class,
        "control_signal": classification.control_signal,
        "run_id": run_id,
    }
    artifact_id = deterministic_id(
        prefix="prl-pkt",
        payload=payload,
        namespace="prl::packet",
    )
    envelope = build_artifact_envelope(
        artifact_id=artifact_id,
        timestamp=ts,
        schema_version="1.0.0",
        primary_trace_ref=trace_id,
        related_trace_refs=[capture_record["trace_id"]],
    )
    artifact: dict[str, Any] = {
        "artifact_type": "pre_pr_failure_packet",
        "schema_version": "1.0.0",
        "id": envelope["id"],
        "timestamp": envelope["timestamp"],
        "run_id": run_id,
        "trace_id": trace_id,
        "trace_refs": envelope["trace_refs"],
        "capture_record_ref": capture_ref,
        "failure_class": classification.failure_class,
        "owning_system": classification.owning_system,
        "control_signal": classification.control_signal,
        "normalized_message": capture_record["normalized_message"],
        "file_refs": capture_record["file_refs"],
        "remediation_hint": classification.remediation_hint,
    }
    _validate(artifact, "pre_pr_failure_packet")
    return artifact
