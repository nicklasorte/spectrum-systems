"""AEX observability emitter.

AEX produces observability records (admission_trace_record,
admission_evidence_record). OBS owns the trace store and observability
authority — this module only *emits*; it does not write to OBS storage,
configure metrics, or fire alerts.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


_NON_AUTHORITY_ASSERTIONS = (
    "aex_does_not_own_observability_authority",
    "aex_does_not_own_lineage_issuance_authority",
    "aex_does_not_own_replay_authority",
    "aex_does_not_own_evaluation_authority",
    "aex_does_not_own_enforcement_authority",
)


def _utc(now: datetime | None = None) -> str:
    return (now or datetime.now(tz=timezone.utc)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_hash16(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _stable_hash24(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def _stable_hash64(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def derive_run_id(*, request_id: str, trace_id: str) -> str:
    digest = _stable_hash16([request_id, trace_id, "run"])
    return f"run-{digest}"


def derive_span_id(*, request_id: str, trace_id: str, span_label: str = "admission") -> str:
    digest = _stable_hash16([request_id, trace_id, span_label])
    return f"span-{digest}"


def build_admission_trace_record(
    *,
    admission_outcome: str,
    request_id: str,
    trace_id: str,
    admission_artifact_ref: str,
    normalized_execution_request_ref: str,
    downstream_refs: list[str],
    started_at: str,
    finished_at: str,
    parent_span_id: str | None = None,
    produced_by: str = "AEXObservabilityEmitter",
) -> dict[str, Any]:
    """Emit a contract-valid admission_trace_record.

    OBS owns the trace store; this record is suitable for OBS ingestion but
    AEX does not enforce ingestion or own observability authority.
    """
    if admission_outcome not in {"admitted", "rejected", "indeterminate"}:
        raise ValueError("admission_outcome must be admitted|rejected|indeterminate")

    run_id = derive_run_id(request_id=request_id, trace_id=trace_id)
    span_id = derive_span_id(request_id=request_id, trace_id=trace_id)
    record = {
        "artifact_type": "admission_trace_record",
        "schema_version": "1.0.0",
        "trace_record_id": f"atr-{_stable_hash16([request_id, trace_id, 'trace'])}",
        "request_id": request_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "produced_by": produced_by,
        "producer_authority": "AEX",
        "admission_outcome": admission_outcome,
        "admission_artifact_ref": admission_artifact_ref,
        "normalized_execution_request_ref": normalized_execution_request_ref,
        "downstream_refs": list(downstream_refs),
        "observability_owner_ref": "OBS",
    }
    validate_artifact(record, "admission_trace_record")
    return record


def build_admission_evidence_record(
    *,
    admission_outcome: str,
    request_id: str,
    trace_id: str,
    admission_artifact_ref: str,
    normalized_execution_request_ref: str,
    source_request_ref: str,
    downstream_refs: list[str],
    input_hash: str,
    output_hash: str,
    replay_command_ref: str,
    created_at: str | None = None,
    produced_by: str = "AEXObservabilityEmitter",
) -> dict[str, Any]:
    """Emit a contract-valid admission_evidence_record bundling AEX outputs
    with lineage / observability / replay refs that downstream authorities
    (LIN / OBS / REP / SEL / GOV / PQX) can consume.
    """
    run_id = derive_run_id(request_id=request_id, trace_id=trace_id)
    span_id = derive_span_id(request_id=request_id, trace_id=trace_id)
    lineage_token_id = "lin-" + _stable_hash24([request_id, trace_id, "lineage"])
    record = {
        "artifact_type": "admission_evidence_record",
        "schema_version": "1.0.0",
        "evidence_id": f"aer-{_stable_hash16([request_id, trace_id, 'evidence'])}",
        "request_id": request_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "created_at": created_at or _utc(),
        "produced_by": produced_by,
        "producer_authority": "AEX",
        "admission_outcome": admission_outcome,
        "input_refs": [source_request_ref],
        "output_refs": [admission_artifact_ref, normalized_execution_request_ref],
        "lineage_refs": {
            "lineage_token_id": lineage_token_id,
            "lineage_owner": "LIN",
            "source_request_ref": source_request_ref,
            "admission_artifact_ref": admission_artifact_ref,
            "normalized_execution_request_ref": normalized_execution_request_ref,
        },
        "observability_refs": {
            "trace_id": trace_id,
            "run_id": run_id,
            "span_id": span_id,
            "observability_owner": "OBS",
        },
        "replay_refs": {
            "input_hash": input_hash,
            "output_hash": output_hash,
            "replay_command_ref": replay_command_ref,
            "replay_owner": "REP",
        },
        "downstream_refs": list(downstream_refs),
        "evidence_hash": "sha256:" + _stable_hash64([request_id, trace_id, input_hash, output_hash]),
    }
    validate_artifact(record, "admission_evidence_record")
    return record


def write_admission_observability_artifacts(
    *,
    admission_outcome: str,
    request_id: str,
    trace_id: str,
    admission_artifact_ref: str,
    normalized_execution_request_ref: str,
    source_request_ref: str,
    downstream_refs: list[str],
    input_hash: str,
    output_hash: str,
    replay_command_ref: str,
    out_dir: Path,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> dict[str, Path]:
    """Write the admission_trace_record and admission_evidence_record under
    out_dir. Returns the paths written.
    """
    started = started_at or _utc()
    finished = finished_at or started
    trace = build_admission_trace_record(
        admission_outcome=admission_outcome,
        request_id=request_id,
        trace_id=trace_id,
        admission_artifact_ref=admission_artifact_ref,
        normalized_execution_request_ref=normalized_execution_request_ref,
        downstream_refs=downstream_refs,
        started_at=started,
        finished_at=finished,
    )
    evidence = build_admission_evidence_record(
        admission_outcome=admission_outcome,
        request_id=request_id,
        trace_id=trace_id,
        admission_artifact_ref=admission_artifact_ref,
        normalized_execution_request_ref=normalized_execution_request_ref,
        source_request_ref=source_request_ref,
        downstream_refs=downstream_refs,
        input_hash=input_hash,
        output_hash=output_hash,
        replay_command_ref=replay_command_ref,
        created_at=started,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "aex_admission_trace_record.json"
    evidence_path = out_dir / "aex_admission_evidence_record.json"
    trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"trace": trace_path, "evidence": evidence_path}


__all__ = [
    "build_admission_trace_record",
    "build_admission_evidence_record",
    "derive_run_id",
    "derive_span_id",
    "write_admission_observability_artifacts",
]
