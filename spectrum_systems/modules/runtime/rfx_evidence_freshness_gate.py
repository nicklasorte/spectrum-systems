"""RFX-N15 — Evidence freshness gate for proof inputs.

Validates that proof inputs supplied to RFX verification steps are within an
acceptable freshness window. Stale evidence must not silently pass — the gate
emits a deterministic block signal when any required input is too old or
missing a timestamp.

This module is a non-owning phase-label support helper. Canonical ownership
of those surfaces is recorded in ``docs/architecture/system_registry.md``.
This gate emits freshness findings; downstream systems consume those findings.

Failure prevented: stale proof inputs silently passing verification, allowing
outdated evidence to satisfy freshness-required gates.

Signal improved: evidence freshness compliance rate; stale-input detection
coverage.

Reason codes:
  rfx_freshness_missing_timestamp      — evidence record lacks a timestamp
  rfx_freshness_stale                  — evidence record is older than the max age
  rfx_freshness_empty_inputs           — no evidence records supplied
  rfx_freshness_invalid_max_age        — max_age_seconds is missing or non-positive
  rfx_freshness_invalid_reference_time — reference_time_seconds is missing or non-finite
  rfx_freshness_malformed_record       — evidence record is not a dict
"""

from __future__ import annotations

import math
from typing import Any


def check_rfx_evidence_freshness(
    *,
    evidence_records: list[dict[str, Any]],
    reference_time_seconds: float,
    max_age_seconds: float = 3600.0,
) -> dict[str, Any]:
    """Gate evidence inputs on freshness relative to reference_time_seconds.

    ``reference_time_seconds`` is the current time as a Unix timestamp.
    ``max_age_seconds`` is the maximum age (in seconds) for a fresh record.

    Each evidence record must have a ``timestamp_seconds`` field (Unix epoch).
    """
    reason: list[str] = []
    stale_ids: list[str] = []
    missing_ts_ids: list[str] = []

    records: list = evidence_records if isinstance(evidence_records, (list, tuple)) else []
    if not records:
        reason.append("rfx_freshness_empty_inputs")

    if not isinstance(max_age_seconds, (int, float)) or not math.isfinite(max_age_seconds) or max_age_seconds <= 0:
        reason.append("rfx_freshness_invalid_max_age")
        max_age_seconds = 3600.0  # default fallback for reporting

    invalid_reference_time = not isinstance(reference_time_seconds, (int, float)) or not math.isfinite(reference_time_seconds)
    if invalid_reference_time:
        reason.append("rfx_freshness_invalid_reference_time")

    fresh_count = 0
    for rec in records:
        if not isinstance(rec, dict):
            reason.append("rfx_freshness_malformed_record")
            continue
        rec_id = rec.get("id") or rec.get("evidence_id") or rec.get("artifact_type") or "unknown"
        ts = rec.get("timestamp_seconds")
        if ts is None:
            reason.append("rfx_freshness_missing_timestamp")
            missing_ts_ids.append(str(rec_id))
            continue
        try:
            ts_float = float(ts)
            if not math.isfinite(ts_float):
                raise ValueError("non-finite timestamp")
        except (TypeError, ValueError):
            reason.append("rfx_freshness_missing_timestamp")
            missing_ts_ids.append(str(rec_id))
            continue
        if invalid_reference_time:
            reason.append("rfx_freshness_stale")
            stale_ids.append(str(rec_id))
            continue
        age = reference_time_seconds - ts_float
        if age > max_age_seconds:
            reason.append("rfx_freshness_stale")
            stale_ids.append(str(rec_id))
        else:
            fresh_count += 1

    total = len(records)
    unique_reasons = sorted(set(reason))
    return {
        "artifact_type": "rfx_evidence_freshness_gate_result",
        "schema_version": "1.0.0",
        "stale_record_ids": stale_ids,
        "missing_timestamp_ids": missing_ts_ids,
        "reason_codes_emitted": unique_reasons,
        "status": "fresh" if not unique_reasons else "stale",
        "signals": {
            "total_records": total,
            "fresh_count": fresh_count,
            "stale_count": len(stale_ids),
            "missing_timestamp_count": len(missing_ts_ids),
            "freshness_rate": fresh_count / max(total, 1),
        },
    }
