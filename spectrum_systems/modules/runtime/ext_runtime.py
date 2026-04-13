"""EXT external runtime governance runtime."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from spectrum_systems.contracts import validate_artifact


class EXTRuntimeError(ValueError):
    pass


def _hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_runtime_provenance(*, runtime_name: str, runtime_version: str, environment: dict[str, Any], inputs: dict[str, Any], outputs: dict[str, Any], cpu_seconds: float, memory_mb: float, created_at: str, artifact_id: str = "ext-prov-001") -> dict[str, Any]:
    if not runtime_version or cpu_seconds <= 0 or memory_mb <= 0:
        raise EXTRuntimeError("missing_runtime_or_constraints")
    rec = {
        "artifact_type": "ext_runtime_provenance_record",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": created_at,
        "runtime_name": runtime_name,
        "runtime_version": runtime_version,
        "environment_fingerprint": _hash(environment),
        "input_fingerprint": _hash(inputs),
        "output_fingerprint": _hash(outputs),
        "resource_limits": {"cpu_seconds": cpu_seconds, "memory_mb": memory_mb},
    }
    validate_artifact(rec, "ext_runtime_provenance_record")
    return rec


def enforce_constraints(*, provenance: dict[str, Any], observed_cpu_seconds: float, observed_memory_mb: float) -> dict[str, Any]:
    limits = provenance["resource_limits"]
    reasons = []
    if observed_cpu_seconds > limits["cpu_seconds"]:
        reasons.append("cpu_limit_exceeded")
    if observed_memory_mb > limits["memory_mb"]:
        reasons.append("memory_limit_exceeded")
    rec = {
        "artifact_type": "ext_constraint_enforcement_record",
        "artifact_id": f"ext-constraint-{provenance['artifact_id']}",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": provenance["created_at"],
        "provenance_ref": f"ext_runtime_provenance_record:{provenance['artifact_id']}",
        "status": "pass" if not reasons else "fail",
        "constraint_results": reasons or ["cpu_ok", "memory_ok"],
        "block_execution": bool(reasons),
    }
    validate_artifact(rec, "ext_constraint_enforcement_record")
    return rec
