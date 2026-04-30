"""RFX-N14 — RFX incident-to-eval bridge.

Converts a closed or classified incident record into an EVL-compatible eval
candidate and emits a non-owning handoff record. Every incident must either
produce an eval candidate or supply an explicit rationale for why no eval
candidate is warranted.

This module is a non-owning phase-label support helper. EVL remains the sole
eval-coverage authority as recorded in ``docs/architecture/system_registry.md``.
This bridge emits candidate inputs for EVL; it does not own or record eval
coverage outputs.

Failure prevented: incidents that close without any regression eval coverage,
allowing the same failure to recur undetected; missing rationale when eval is
skipped.

Signal improved: incident-to-eval conversion rate; eval candidate coverage of
known incidents.

Reason codes:
  rfx_bridge_missing_incident_id     — incident record lacks an identifier
  rfx_bridge_missing_classification  — incident lacks a classification label
  rfx_bridge_no_eval_candidate       — incident produced neither candidate nor rationale
  rfx_bridge_missing_rationale       — eval skip declared but no rationale supplied
  rfx_bridge_missing_trace_ref       — incident lacks a trace/lineage reference
  rfx_bridge_empty                   — no incident records supplied
  rfx_bridge_malformed_incident      — incident row is not a dict
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _stable_eval_id(incident_id: str, classification: str) -> str:
    payload = json.dumps({"incident_id": incident_id, "classification": classification},
                         sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "eval-" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def build_rfx_incident_to_eval_bridge(
    *,
    incidents: list[dict[str, Any]],
    evl_target_ref: str | None = None,
) -> dict[str, Any]:
    """Convert incident records into EVL eval candidates with a handoff record.

    Each incident must either produce a candidate eval case or supply an
    explicit ``eval_skip_rationale`` field.
    """
    reason: list[str] = []
    candidates: list[dict[str, Any]] = []

    if not incidents:
        reason.append("rfx_bridge_empty")
        return {
            "artifact_type": "rfx_incident_to_eval_bridge",
            "schema_version": "1.0.0",
            "evl_target_ref": evl_target_ref,
            "eval_candidates": candidates,
            "reason_codes_emitted": sorted(set(reason)),
            "status": "empty",
            "signals": {
                "incident_count": 0,
                "candidate_count": 0,
                "skip_with_rationale_count": 0,
                "conversion_rate": 0.0,
            },
        }

    skip_with_rationale = 0
    for inc in incidents:
        if not isinstance(inc, dict):
            reason.append("rfx_bridge_malformed_incident")
            continue
        incident_id = str(inc.get("incident_id") or inc.get("id") or "").strip()
        if not incident_id:
            reason.append("rfx_bridge_missing_incident_id")

        classification = str(inc.get("classification") or inc.get("category") or "").strip()
        if not classification:
            reason.append("rfx_bridge_missing_classification")

        trace_ref_raw = inc.get("trace_ref") or inc.get("trace_id")
        trace_ref = str(trace_ref_raw).strip() if trace_ref_raw is not None else ""
        if not trace_ref:
            reason.append("rfx_bridge_missing_trace_ref")

        eval_skip = inc.get("eval_skip", False)
        eval_skip_rationale = str(inc.get("eval_skip_rationale") or "").strip()

        if eval_skip:
            if not eval_skip_rationale:
                reason.append("rfx_bridge_missing_rationale")
            else:
                skip_with_rationale += 1
        else:
            if not classification or not incident_id or not trace_ref:
                reason.append("rfx_bridge_no_eval_candidate")
            else:
                candidates.append({
                    "eval_candidate_id": _stable_eval_id(incident_id, classification),
                    "source_incident_id": incident_id,
                    "classification": classification,
                    "trace_ref": trace_ref,
                    "description": inc.get("description", ""),
                    "reproduction_inputs": inc.get("reproduction_inputs"),
                    "expected_outcome": inc.get("expected_outcome"),
                })

    total = len(incidents)
    candidate_count = len(candidates)
    unique_reasons = sorted(set(reason))
    return {
        "artifact_type": "rfx_incident_to_eval_bridge",
        "schema_version": "1.0.0",
        "evl_target_ref": evl_target_ref,
        "eval_candidates": candidates,
        "reason_codes_emitted": unique_reasons,
        "status": "complete" if not unique_reasons else "incomplete",
        "signals": {
            "incident_count": total,
            "candidate_count": candidate_count,
            "skip_with_rationale_count": skip_with_rationale,
            "conversion_rate": candidate_count / max(total, 1),
        },
    }
