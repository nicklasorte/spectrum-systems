"""RFX-N21 — Bloat burn-down / consolidation report.

Produces a deterministic bloat-burndown report by comparing the current
RFX helper surface against a justified-helper baseline. Helpers with no
justification, duplicate responsibilities, or superseded functionality are
flagged as consolidation candidates.

This module is a non-owning phase-label support helper. It does not own
the module lifecycle or deprecation outputs — those require governed PR
review. This module emits a candidate list as input to the governed process.

Failure prevented: duplicate or unjustified helper modules surviving in the
codebase without governance oversight, causing maintenance debt and
inconsistency.

Signal improved: consolidation candidate identification rate; helper
justification coverage trend.

Reason codes:
  rfx_bloat_unjustified_helper       — helper has no justification claim
  rfx_bloat_duplicate_responsibility — two helpers share the same stated responsibility
  rfx_bloat_superseded               — helper is explicitly marked as superseded
  rfx_bloat_empty_input              — no helper records supplied
  rfx_bloat_missing_name             — helper record has no name
  rfx_bloat_malformed_helper         — a helper row is not a dict
"""

from __future__ import annotations

from typing import Any


def build_rfx_bloat_burndown_report(
    *,
    helpers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Produce a bloat burn-down report for the RFX helper surface.

    Each helper dict may have:
      ``name``             — module/helper identifier (required)
      ``justification``    — failure_prevented or signal_improved claim
      ``responsibility``   — role label for duplicate detection
      ``superseded_by``    — name of replacement module (marks as superseded)
    """
    reason: list[str] = []
    report: list[dict[str, Any]] = []
    responsibility_index: dict[str, str] = {}

    helpers = helpers if isinstance(helpers, (list, tuple)) else []
    if not helpers:
        reason.append("rfx_bloat_empty_input")
        return {
            "artifact_type": "rfx_bloat_burndown_report",
            "schema_version": "1.0.0",
            "consolidation_candidates": report,
            "reason_codes_emitted": sorted(set(reason)),
            "status": "findings_present",
            "signals": {
                "total_helpers": 0,
                "justified_count": 0,
                "consolidation_candidate_count": 0,
                "duplicate_responsibility_count": 0,
            },
        }

    valid_helpers: list[dict] = []
    for h in helpers:
        if not isinstance(h, dict):
            reason.append("rfx_bloat_malformed_helper")
            continue
        valid_helpers.append(h)
        name = str(h.get("name") or "").strip()
        if not name:
            reason.append("rfx_bloat_missing_name")
            continue

        justification = str(h.get("justification") or "").strip()
        responsibility = str(h.get("responsibility") or "").strip().lower()
        superseded_by = str(h.get("superseded_by") or "").strip()

        tags: list[str] = []
        action = "keep"

        if superseded_by:
            reason.append("rfx_bloat_superseded")
            tags.append("superseded")
            action = "remove"
        elif not justification:
            reason.append("rfx_bloat_unjustified_helper")
            tags.append("unjustified")
            action = "review_for_removal"

        if responsibility:
            prior = responsibility_index.get(responsibility)
            if prior and prior != name:
                reason.append("rfx_bloat_duplicate_responsibility")
                tags.append("duplicate_responsibility")
                action = "consolidate"
            else:
                responsibility_index[responsibility] = name

        if tags:
            report.append({
                "name": name,
                "action": action,
                "tags": tags,
                "superseded_by": superseded_by or None,
                "justification": justification or None,
            })

    justified_count = sum(
        1 for h in valid_helpers
        if str(h.get("name") or "").strip()
        and str(h.get("justification") or "").strip()
        and not str(h.get("superseded_by") or "").strip()
    )
    unique_reasons = sorted(set(reason))
    return {
        "artifact_type": "rfx_bloat_burndown_report",
        "schema_version": "1.0.0",
        "consolidation_candidates": report,
        "reason_codes_emitted": unique_reasons,
        "status": "complete" if not unique_reasons else "findings_present",
        "signals": {
            "total_helpers": len(helpers),
            "justified_count": justified_count,
            "consolidation_candidate_count": len(report),
            "duplicate_responsibility_count": reason.count("rfx_bloat_duplicate_responsibility"),
        },
    }
