"""Persisted authoritative issuance registry for repo-write lineage artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from threading import Lock
from typing import Any

from spectrum_systems.modules.pqx_backbone import REPO_ROOT


class LineageIssuanceRegistryError(ValueError):
    """Raised when lineage issuance registry state is missing, invalid, or mismatched."""


_ISSUANCE_REGISTRY_PATH = REPO_ROOT / "state" / "lineage_issuance_registry.json"
_ISSUANCE_REGISTRY_LOCK = Lock()

_EXPECTED_ISSUER_BY_ARTIFACT = {
    "build_admission_record": "AEX",
    "normalized_execution_request": "AEX",
    "tlc_handoff_record": "TLC",
    "tpa_slice_artifact": "TPA",
}

_ARTIFACT_ID_FIELD_BY_TYPE = {
    "build_admission_record": "admission_id",
    "normalized_execution_request": "request_id",
    "tlc_handoff_record": "handoff_id",
    "tpa_slice_artifact": "artifact_id",
}


def _require_non_empty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LineageIssuanceRegistryError(f"lineage_issuance_registry_invalid:{field}_required")
    return value.strip()


def _artifact_identity(artifact: dict[str, Any]) -> tuple[str, str]:
    artifact_type = _require_non_empty_string(artifact.get("artifact_type"), field="artifact_type")
    id_field = _ARTIFACT_ID_FIELD_BY_TYPE.get(artifact_type)
    if not id_field:
        raise LineageIssuanceRegistryError(f"lineage_issuance_registry_invalid:unsupported_artifact_type:{artifact_type}")
    artifact_id = _require_non_empty_string(artifact.get(id_field), field=f"{artifact_type}.{id_field}")
    return artifact_type, artifact_id


def _issuance_record_id(
    *,
    artifact_type: str,
    artifact_id: str,
    issuer: str,
    key_id: str,
    payload_digest: str,
    request_id: str,
    trace_id: str,
) -> str:
    material = f"{artifact_type}|{artifact_id}|{issuer}|{key_id}|{payload_digest}|{request_id}|{trace_id}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"lir-{digest}"


def _read_registry(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LineageIssuanceRegistryError("lineage_issuance_registry_unreadable") from exc
    if not isinstance(payload, dict):
        raise LineageIssuanceRegistryError("lineage_issuance_registry_invalid")
    records = payload.get("issuance_records")
    if not isinstance(records, list):
        raise LineageIssuanceRegistryError("lineage_issuance_registry_invalid")

    indexed: dict[str, dict[str, str]] = {}
    required_fields = {
        "issuance_record_id",
        "artifact_type",
        "artifact_id",
        "issuer",
        "key_id",
        "payload_digest",
        "trace_id",
        "request_id",
        "issued_at",
    }
    for record in records:
        if not isinstance(record, dict):
            raise LineageIssuanceRegistryError("lineage_issuance_registry_invalid")
        normalized: dict[str, str] = {}
        for field in required_fields:
            normalized[field] = _require_non_empty_string(record.get(field), field=f"issuance_records.{field}")
        indexed[normalized["issuance_record_id"]] = normalized
    return indexed


def _write_registry(path: Path, indexed: dict[str, dict[str, str]]) -> None:
    payload = {
        "schema_version": "1.0",
        "issuance_records": [indexed[key] for key in sorted(indexed)],
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(path)
    except OSError as exc:
        raise LineageIssuanceRegistryError("lineage_issuance_registry_write_failed") from exc


def record_authoritative_lineage_issuance(
    *,
    artifact: dict[str, Any],
    issuer: str,
    key_id: str,
    payload_digest: str,
    issued_at: str,
) -> dict[str, str]:
    artifact_type, artifact_id = _artifact_identity(artifact)
    expected_issuer = _EXPECTED_ISSUER_BY_ARTIFACT[artifact_type]
    if issuer != expected_issuer:
        raise LineageIssuanceRegistryError("lineage_issuance_registry_invalid:issuer_artifact_mismatch")

    request_id = _require_non_empty_string(artifact.get("request_id"), field=f"{artifact_type}.request_id")
    trace_id = _require_non_empty_string(artifact.get("trace_id"), field=f"{artifact_type}.trace_id")
    normalized_key_id = _require_non_empty_string(key_id, field="key_id")
    normalized_digest = _require_non_empty_string(payload_digest, field="payload_digest")
    normalized_issued_at = _require_non_empty_string(issued_at, field="issued_at")

    issuance_record_id = _issuance_record_id(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        issuer=issuer,
        key_id=normalized_key_id,
        payload_digest=normalized_digest,
        request_id=request_id,
        trace_id=trace_id,
    )
    entry = {
        "issuance_record_id": issuance_record_id,
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "issuer": issuer,
        "key_id": normalized_key_id,
        "payload_digest": normalized_digest,
        "trace_id": trace_id,
        "request_id": request_id,
        "issued_at": normalized_issued_at,
    }

    with _ISSUANCE_REGISTRY_LOCK:
        indexed = _read_registry(_ISSUANCE_REGISTRY_PATH)
        indexed[issuance_record_id] = entry
        _write_registry(_ISSUANCE_REGISTRY_PATH, indexed)
    return dict(entry)


def verify_authoritative_lineage_issuance(
    *,
    artifact: dict[str, Any],
    issuer: str,
    key_id: str,
    payload_digest: str,
) -> dict[str, str]:
    artifact_type, artifact_id = _artifact_identity(artifact)
    request_id = _require_non_empty_string(artifact.get("request_id"), field=f"{artifact_type}.request_id")
    trace_id = _require_non_empty_string(artifact.get("trace_id"), field=f"{artifact_type}.trace_id")
    normalized_key_id = _require_non_empty_string(key_id, field="key_id")
    normalized_digest = _require_non_empty_string(payload_digest, field="payload_digest")

    issuance_record_id = _issuance_record_id(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        issuer=issuer,
        key_id=normalized_key_id,
        payload_digest=normalized_digest,
        request_id=request_id,
        trace_id=trace_id,
    )

    with _ISSUANCE_REGISTRY_LOCK:
        indexed = _read_registry(_ISSUANCE_REGISTRY_PATH)
    record = indexed.get(issuance_record_id)
    if not record:
        raise LineageIssuanceRegistryError("lineage_issuance_missing")

    expected_pairs = {
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "issuer": issuer,
        "key_id": normalized_key_id,
        "payload_digest": normalized_digest,
        "request_id": request_id,
        "trace_id": trace_id,
    }
    for field, expected_value in expected_pairs.items():
        if record.get(field) != expected_value:
            raise LineageIssuanceRegistryError(f"lineage_issuance_mismatch:{field}")
    return dict(record)


def reset_lineage_issuance_registry_state(*, clear_persistent_registry: bool = False) -> None:
    """Test helper to clear persisted issuance registry state."""
    if clear_persistent_registry and _ISSUANCE_REGISTRY_PATH.exists():
        _ISSUANCE_REGISTRY_PATH.unlink()
