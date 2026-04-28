"""RFX failure → eval auto-generation — RFX-06.

Converts failure artifacts into EVL-compatible regression eval candidates.
This module is a non-owning phase-label support helper; it does **not** own
eval coverage decisions or eval lifecycle. EVL remains the sole eval-coverage
authority recorded in ``docs/architecture/system_registry.md``.

Outputs:

  * ``rfx_failure_derived_eval_case`` — candidate eval case derived from a
    classified failure, with stable deterministic ID and lineage refs.
  * ``rfx_eval_handoff_record``       — non-owning handoff envelope to EVL.

Reason codes:

  * ``rfx_failure_missing_reason_code`` — failure record lacks reason code
  * ``rfx_failure_missing_trace``       — failure record lacks trace ref
  * ``rfx_eval_case_duplicate``         — generated case duplicates an existing one
  * ``rfx_eval_case_invalid``           — case structure is invalid
  * ``rfx_eval_handoff_missing_evl_ref``— EVL handoff missing target reference
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


class RFXFailureToEvalError(ValueError):
    """Raised when failure → eval generation fails closed."""


def _stable_id(payload: Any, *, prefix: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _coerce_str(record: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        v = record.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _coerce_lineage_refs(failure: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    direct = failure.get("lineage_refs")
    if isinstance(direct, list):
        for r in direct:
            if isinstance(r, str) and r.strip():
                refs.append(r.strip())
    for key in ("trace_id", "failure_id", "fix_record_id", "run_id"):
        v = failure.get(key)
        if isinstance(v, str) and v.strip():
            refs.append(f"{key}:{v.strip()}")
    # Stable, dedup-preserving ordering.
    seen: set[str] = set()
    ordered: list[str] = []
    for r in refs:
        if r not in seen:
            seen.add(r)
            ordered.append(r)
    return ordered


def build_rfx_failure_derived_eval_case(
    *,
    failure_record: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a deterministic ``rfx_failure_derived_eval_case`` from a failure.

    Fails closed when the failure lacks a reason code or trace reference.
    """
    if not isinstance(failure_record, dict) or not failure_record:
        raise RFXFailureToEvalError(
            "rfx_eval_case_invalid: failure_record absent or not a mapping"
        )

    reason_code = _coerce_str(failure_record, "reason_code", "code", "classification")
    if reason_code is None:
        raise RFXFailureToEvalError(
            "rfx_failure_missing_reason_code: failure record has no reason_code"
        )

    trace_id = _coerce_str(failure_record, "trace_id", "trace", "run_id")
    if trace_id is None:
        raise RFXFailureToEvalError(
            "rfx_failure_missing_trace: failure record has no trace_id"
        )

    lineage_refs = _coerce_lineage_refs(failure_record)
    if not lineage_refs:
        raise RFXFailureToEvalError(
            "rfx_eval_case_invalid: failure record has no lineage references"
        )

    inputs = failure_record.get("inputs")
    expected_block = failure_record.get("expected_block")
    case_id_payload = {
        "reason_code": reason_code,
        "trace_id": trace_id,
        "inputs": inputs if isinstance(inputs, (dict, list)) else None,
        "expected_block": expected_block,
    }
    case_id = _stable_id(case_id_payload, prefix="rfx-eval")

    return {
        "artifact_type": "rfx_failure_derived_eval_case",
        "schema_version": "1.0.0",
        "case_id": case_id,
        "reason_code": reason_code,
        "trace_id": trace_id,
        "source_failure_refs": lineage_refs,
        "inputs": inputs if isinstance(inputs, (dict, list)) else None,
        "expected_outcome": "blocked",
        "expected_reason_codes": [reason_code],
        "version": 1,
    }


def deduplicate_eval_cases(
    cases: list[dict[str, Any]],
    *,
    existing_case_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (unique_cases, duplicate_case_ids) for a list of generated cases.

    Stable deterministic ``case_id`` is the dedup key. Duplicates inside the
    incoming batch are also detected.
    """
    seen: set[str] = set(existing_case_ids or set())
    unique: list[dict[str, Any]] = []
    duplicates: list[str] = []
    for c in cases:
        if not isinstance(c, dict):
            continue
        cid = c.get("case_id")
        if not isinstance(cid, str) or not cid.strip():
            continue
        if cid in seen:
            duplicates.append(cid)
            continue
        seen.add(cid)
        unique.append(c)
    return unique, duplicates


def build_rfx_eval_handoff_record(
    *,
    cases: list[dict[str, Any]],
    evl_target_ref: str | None,
) -> dict[str, Any]:
    """Build a non-owning handoff envelope to EVL for the supplied cases.

    Fails closed when the EVL target reference is absent. Does not alter
    eval coverage; EVL retains coverage authority.
    """
    if not isinstance(evl_target_ref, str) or not evl_target_ref.strip():
        raise RFXFailureToEvalError(
            "rfx_eval_handoff_missing_evl_ref: EVL target reference absent — "
            "RFX cannot complete a non-owning eval handoff"
        )
    valid_cases: list[dict[str, Any]] = []
    for c in cases or []:
        if isinstance(c, dict) and c.get("artifact_type") == "rfx_failure_derived_eval_case":
            valid_cases.append(c)
    handoff_id_payload = {
        "evl_target_ref": evl_target_ref.strip(),
        "case_ids": sorted(c.get("case_id") for c in valid_cases if isinstance(c.get("case_id"), str)),
    }
    handoff_id = _stable_id(handoff_id_payload, prefix="rfx-eval-handoff")
    return {
        "artifact_type": "rfx_eval_handoff_record",
        "schema_version": "1.0.0",
        "handoff_id": handoff_id,
        "evl_target_ref": evl_target_ref.strip(),
        "case_count": len(valid_cases),
        "case_ids": [c.get("case_id") for c in valid_cases],
        "ownership_note": "EVL retains eval coverage authority; RFX is non-owning phase label",
    }


__all__ = [
    "RFXFailureToEvalError",
    "build_rfx_failure_derived_eval_case",
    "deduplicate_eval_cases",
    "build_rfx_eval_handoff_record",
]
