"""PQX-issued execution authority proof artifact helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


class PqxExecutionAuthorityError(ValueError):
    """Raised when PQX execution authority proof is missing or invalid."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _build_integrity_payload(*, queue_id: str, work_item_id: str, step_id: str, trace: Mapping[str, Any], issued_at: str, issuer: str, authority_scope: str, source_refs: list[str]) -> dict[str, Any]:
    return {
        "queue_id": queue_id,
        "work_item_id": work_item_id,
        "step_id": step_id,
        "trace": {
            "trace_id": str(trace.get("trace_id") or ""),
            "trace_refs": sorted(str(ref) for ref in (trace.get("trace_refs") or []) if str(ref)),
        },
        "issued_at": issued_at,
        "issuer": issuer,
        "authority_scope": authority_scope,
        "source_refs": sorted(str(ref) for ref in source_refs if str(ref)),
    }


def compute_authority_integrity(*, queue_id: str, work_item_id: str, step_id: str, trace: Mapping[str, Any], issued_at: str, issuer: str, authority_scope: str, source_refs: list[str]) -> str:
    payload = _build_integrity_payload(
        queue_id=queue_id,
        work_item_id=work_item_id,
        step_id=step_id,
        trace=trace,
        issued_at=issued_at,
        issuer=issuer,
        authority_scope=authority_scope,
        source_refs=source_refs,
    )
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def issue_pqx_execution_authority_record(
    *,
    queue_id: str,
    work_item_id: str,
    step_id: str,
    trace: Mapping[str, Any],
    source_refs: list[str],
    issuer: str = "pqx_state_machine",
    authority_scope: str = "queue_step_execution",
    issued_at: str | None = None,
) -> dict[str, Any]:
    issued_at = issued_at or _utc_now()
    authority_id = f"pqar-{queue_id}-{work_item_id}-{step_id}"
    integrity = compute_authority_integrity(
        queue_id=queue_id,
        work_item_id=work_item_id,
        step_id=step_id,
        trace=trace,
        issued_at=issued_at,
        issuer=issuer,
        authority_scope=authority_scope,
        source_refs=source_refs,
    )
    record = {
        "artifact_type": "pqx_execution_authority_record",
        "schema_version": "1.0.0",
        "authority_id": authority_id,
        "queue_id": queue_id,
        "work_item_id": work_item_id,
        "step_id": step_id,
        "trace": {
            "trace_id": str(trace.get("trace_id") or ""),
            "trace_refs": sorted(str(ref) for ref in (trace.get("trace_refs") or []) if str(ref)),
        },
        "issued_at": issued_at,
        "issuer": issuer,
        "authority_scope": authority_scope,
        "source_refs": sorted(str(ref) for ref in source_refs if str(ref)),
        "integrity": integrity,
        "provenance": {"producer": "pqx_state_machine", "produced_at": issued_at},
    }
    validate_artifact(record, "pqx_execution_authority_record")
    return record


def validate_pqx_execution_authority_record(record: Mapping[str, Any], *, expected_queue_id: str | None = None, expected_work_item_id: str | None = None, expected_step_id: str | None = None) -> dict[str, Any]:
    normalized = dict(record)
    validate_artifact(normalized, "pqx_execution_authority_record")

    if normalized.get("issuer") != "pqx_state_machine":
        raise PqxExecutionAuthorityError("PQX authority proof issuer mismatch")

    if expected_queue_id is not None and normalized.get("queue_id") != expected_queue_id:
        raise PqxExecutionAuthorityError("PQX authority proof queue_id mismatch")
    if expected_work_item_id is not None and normalized.get("work_item_id") != expected_work_item_id:
        raise PqxExecutionAuthorityError("PQX authority proof work_item_id mismatch")
    if expected_step_id is not None and normalized.get("step_id") != expected_step_id:
        raise PqxExecutionAuthorityError("PQX authority proof step_id mismatch")

    expected_integrity = compute_authority_integrity(
        queue_id=str(normalized["queue_id"]),
        work_item_id=str(normalized["work_item_id"]),
        step_id=str(normalized["step_id"]),
        trace=dict(normalized["trace"]),
        issued_at=str(normalized["issued_at"]),
        issuer=str(normalized["issuer"]),
        authority_scope=str(normalized["authority_scope"]),
        source_refs=list(normalized["source_refs"]),
    )
    if normalized.get("integrity") != expected_integrity:
        raise PqxExecutionAuthorityError("PQX authority proof integrity mismatch")
    return normalized


__all__ = [
    "PqxExecutionAuthorityError",
    "compute_authority_integrity",
    "issue_pqx_execution_authority_record",
    "validate_pqx_execution_authority_record",
]
