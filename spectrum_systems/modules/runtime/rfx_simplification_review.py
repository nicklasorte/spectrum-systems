"""RFX-N12 — Final simplification review / justify-or-fold pass.

Every RFX helper must justify its existence by naming at least one failure it
prevents or one measurable signal it improves. Helpers that have no such
justification are flagged for folding or deprecation. Helpers with duplicate
responsibilities are flagged for consolidation.

This module is a non-owning phase-label support helper. It does not own the
outcome of removing or keeping modules — that belongs to the governed PR process
and canonical system owners in ``docs/architecture/system_registry.md``.

Failure prevented: bloated helper surface with no traceable failure-prevention
or signal-improvement claim; duplicate logic that decays independently.

Signal improved: helper justification coverage; consolidation candidate count.

Reason codes:
  rfx_simplification_no_justification   — helper has no failure_prevented or signal_improved
  rfx_simplification_duplicate_role     — two helpers share the same stated role
  rfx_simplification_empty_input        — no helpers supplied
  rfx_simplification_missing_name       — helper entry has no name field
  rfx_simplification_malformed_row      — a helper row is not a dict
"""

from __future__ import annotations

from typing import Any


def assess_rfx_simplification(
    *,
    helpers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assess each RFX helper for justification; flag folds and duplicates.

    Each helper dict must have:
      ``name``             — module/helper identifier
      ``failure_prevented`` — what failure this prevents (may be empty)
      ``signal_improved``  — what signal this improves (may be empty)
      ``role``             — a short role label (used for duplicate detection)
    """
    reason: list[str] = []
    recommendations: list[dict[str, Any]] = []
    role_index: dict[str, str] = {}

    if not helpers:
        reason.append("rfx_simplification_empty_input")
        return {
            "artifact_type": "rfx_simplification_review_result",
            "schema_version": "1.0.0",
            "recommendations": recommendations,
            "reason_codes_emitted": sorted(set(reason)),
            "status": "incomplete",
            "signals": {
                "total_helpers": 0,
                "justified_count": 0,
                "fold_candidates": 0,
                "duplicate_role_count": 0,
            },
        }

    for h in helpers:
        if not isinstance(h, dict):
            reason.append("rfx_simplification_malformed_row")
            continue
        name = (h.get("name") or "").strip()
        if not name:
            reason.append("rfx_simplification_missing_name")
            continue

        failure_prevented = (h.get("failure_prevented") or "").strip()
        signal_improved = (h.get("signal_improved") or "").strip()
        role = (h.get("role") or "").strip().lower()

        has_justification = bool(failure_prevented or signal_improved)
        if not has_justification:
            reason.append("rfx_simplification_no_justification")
            rec = "fold_or_deprecate"
        else:
            rec = "keep"

        if role:
            prior = role_index.get(role)
            if prior and prior != name:
                reason.append("rfx_simplification_duplicate_role")
                rec = "consolidate"
            role_index[role] = name

        recommendations.append({
            "name": name,
            "recommendation": rec,
            "failure_prevented": failure_prevented,
            "signal_improved": signal_improved,
        })

    justified_count = sum(1 for r in recommendations if r["recommendation"] == "keep")
    fold_candidates = sum(1 for r in recommendations if r["recommendation"] == "fold_or_deprecate")
    unique_reasons = sorted(set(reason))
    return {
        "artifact_type": "rfx_simplification_review_result",
        "schema_version": "1.0.0",
        "recommendations": recommendations,
        "reason_codes_emitted": unique_reasons,
        "status": "complete" if not unique_reasons else "findings_present",
        "signals": {
            "total_helpers": len(helpers),
            "justified_count": justified_count,
            "fold_candidates": fold_candidates,
            "duplicate_role_count": reason.count("rfx_simplification_duplicate_role"),
        },
    }
