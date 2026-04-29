"""RFX-N13 — RFX failure replay packet.

Packages a failure into a minimal, self-contained replay packet that allows
the failure to be reproduced deterministically without access to the original
runtime environment. The packet must include all inputs needed to trigger the
failure and the expected observable outcome.

This module is a non-owning phase-label support helper. It does not own
replay authority or replay integrity decisions — those belong to REP as
declared in ``docs/architecture/system_registry.md``. The packet is a
support input for REP-owned replay runs.

Failure prevented: failures that cannot be reproduced because the minimal
reproduction inputs were never captured; postmortems blocked by missing replay
evidence.

Signal improved: replay reproducibility rate; failure replay packet completeness.

Reason codes:
  rfx_replay_missing_failure_id     — packet lacks a failure identifier
  rfx_replay_missing_inputs         — packet lacks reproduction inputs
  rfx_replay_missing_expected       — packet lacks the expected observable outcome
  rfx_replay_missing_trace_ref      — packet lacks a trace reference for lineage
  rfx_replay_missing_system_context — packet lacks system-context snapshot
  rfx_replay_packet_empty           — no failure record supplied
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _stable_packet_id(failure_id: str, inputs: Any) -> str:
    payload = json.dumps({"failure_id": failure_id, "inputs": inputs},
                         sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "replay-" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def build_rfx_failure_replay_packet(
    *,
    failure_record: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a self-contained replay packet from a failure record.

    Fails closed when the failure record is absent or lacks required fields.
    """
    reason: list[str] = []

    if not isinstance(failure_record, dict) or not failure_record:
        reason.append("rfx_replay_packet_empty")
        return {
            "artifact_type": "rfx_failure_replay_packet",
            "schema_version": "1.0.0",
            "packet_id": None,
            "failure_id": None,
            "reproduction_inputs": None,
            "expected_outcome": None,
            "trace_ref": None,
            "system_context": None,
            "reason_codes_emitted": sorted(set(reason)),
            "status": "incomplete",
            "signals": {"completeness_score": 0.0},
        }

    failure_id = (failure_record.get("failure_id") or failure_record.get("id") or "").strip()
    if not failure_id:
        reason.append("rfx_replay_missing_failure_id")

    reproduction_inputs = failure_record.get("reproduction_inputs") or failure_record.get("inputs")
    if not reproduction_inputs:
        reason.append("rfx_replay_missing_inputs")

    expected_outcome = failure_record.get("expected_outcome") or failure_record.get("expected")
    if not expected_outcome:
        reason.append("rfx_replay_missing_expected")

    trace_ref = failure_record.get("trace_ref") or failure_record.get("trace_id")
    if not trace_ref:
        reason.append("rfx_replay_missing_trace_ref")

    system_context = failure_record.get("system_context")
    if not system_context:
        reason.append("rfx_replay_missing_system_context")

    required_fields = 5
    missing = len(set(reason))
    completeness = max(0.0, (required_fields - missing) / required_fields)

    packet_id = _stable_packet_id(failure_id, reproduction_inputs) if failure_id else None
    unique_reasons = sorted(set(reason))
    return {
        "artifact_type": "rfx_failure_replay_packet",
        "schema_version": "1.0.0",
        "packet_id": packet_id,
        "failure_id": failure_id or None,
        "reproduction_inputs": reproduction_inputs,
        "expected_outcome": expected_outcome,
        "trace_ref": trace_ref,
        "system_context": system_context,
        "reason_codes_emitted": unique_reasons,
        "status": "complete" if not unique_reasons else "incomplete",
        "signals": {"completeness_score": completeness},
    }
