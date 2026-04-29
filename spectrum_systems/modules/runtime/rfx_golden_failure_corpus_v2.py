"""RFX-N09 — Golden failure corpus v2.

Extends the original corpus with historical RFX/CI failure cases that have
been verified through trace references. Each case records the failure that
occurred, the expected outcome (what the system should have done), the actual
outcome (what happened), the fix lineage, and the revalidation reference.

This module is a non-owning phase-label support helper. It does not own eval
coverage, control decisions, or promotion authority. Canonical ownership of
those surfaces is recorded in ``docs/architecture/system_registry.md``.

Failure prevented: regression to known historical failures when corpus drift
goes undetected; untracked CI failure patterns re-entering the pipeline.

Signal improved: regression coverage density; historical failure traceability.

Reason codes:
  rfx_v2_case_missing_id          — case lacks a stable ID
  rfx_v2_case_missing_trace       — case lacks a trace/lineage reference
  rfx_v2_outcome_mismatch         — actual != expected for a case
  rfx_v2_case_missing_fix_ref     — case lacks a fix-lineage reference
  rfx_v2_case_missing_category    — case lacks a failure-category label
  rfx_v2_corpus_empty             — no cases supplied
  rfx_v2_duplicate_case_id        — two cases share the same ID
  rfx_v2_case_unregistered        — case ID absent from registered_case_ids when the set is supplied
"""

from __future__ import annotations

from typing import Any


# Historical failure categories derived from known RFX/CI incidents.
KNOWN_CATEGORIES: frozenset[str] = frozenset({
    "authority_shape_doc_violation",
    "authority_drift_fixture_violation",
    "system_registry_shadow_overlap",
    "missing_dependency_import",
    "canary_hash_distribution_failure",
    "pytest_selection_incomplete",
    "missing_pra_pol_evidence",
    "direct_pqx_without_lineage",
    "missing_evl_tpa_evidence",
    "missing_trace_lineage_replay",
})


def build_rfx_golden_failure_corpus_v2(
    *,
    cases: list[dict[str, Any]],
    registered_case_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Build a versioned golden failure corpus artifact.

    Each supplied case is validated for completeness and outcome stability.
    Returns a deterministic artifact; callers must not mutate the result.
    """
    registered_case_ids = registered_case_ids or set()
    reason: list[str] = []
    validated: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    if not cases:
        reason.append("rfx_v2_corpus_empty")

    for c in cases:
        case_id = c.get("id") or ""
        if not case_id:
            reason.append("rfx_v2_case_missing_id")
        elif case_id in seen_ids:
            reason.append("rfx_v2_duplicate_case_id")
        else:
            # Only check registration when registered_case_ids was explicitly supplied.
            if registered_case_ids and case_id not in registered_case_ids:
                reason.append("rfx_v2_case_unregistered")
        seen_ids.add(case_id)

        if not c.get("trace_ref"):
            reason.append("rfx_v2_case_missing_trace")
        if not c.get("fix_ref"):
            reason.append("rfx_v2_case_missing_fix_ref")
        if not c.get("category"):
            reason.append("rfx_v2_case_missing_category")
        if c.get("actual") != c.get("expected"):
            reason.append("rfx_v2_outcome_mismatch")

        validated.append({
            "id": case_id,
            "category": c.get("category"),
            "description": c.get("description", ""),
            "trace_ref": c.get("trace_ref"),
            "fix_ref": c.get("fix_ref"),
            "expected": c.get("expected"),
            "actual": c.get("actual"),
            "revalidation_ref": c.get("revalidation_ref"),
        })

    unique_reasons = sorted(set(reason))
    return {
        "artifact_type": "rfx_golden_failure_corpus_v2",
        "schema_version": "2.0.0",
        "cases": validated,
        "known_categories": sorted(KNOWN_CATEGORIES),
        "reason_codes_emitted": unique_reasons,
        "status": "stable" if not unique_reasons else "drifted",
        "signals": {
            "total_cases": len(cases),
            "stable_cases": sum(
                1 for c in cases if c.get("actual") == c.get("expected")
            ),
            "category_coverage": len(
                {c.get("category") for c in cases if c.get("category")}
            ),
            "historical_category_coverage_pct": (
                100.0
                * len({c.get("category") for c in cases if c.get("category")} & KNOWN_CATEGORIES)
                / len(KNOWN_CATEGORIES)
            ),
        },
    }
