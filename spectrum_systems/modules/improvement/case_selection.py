"""
Case Selection — spectrum_systems/modules/improvement/case_selection.py

Selects evaluation cases for a remediation plan simulation.

Purpose
-------
Choose which eval cases should be run when simulating a given remediation plan.
The selection logic prefers cases that are associated with the cluster's dominant
error family, ensures at least one targeted case and one control case are included,
and falls back to all golden cases when cluster linkage is weak.

Public API
----------
select_cases_for_plan(remediation_plan, golden_dataset, classification_records)
    -> Dict[str, Any]
        {
            "selected_case_ids": List[str],
            "selection_reasons": List[str],
        }
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from spectrum_systems.modules.improvement.remediation_mapping import RemediationPlan

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_TARGETED = 1
_MIN_CONTROL = 1

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def select_cases_for_plan(
    remediation_plan: "RemediationPlan",
    golden_dataset: List[Dict[str, Any]],
    classification_records: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """Select evaluation cases for simulating a remediation plan.

    Parameters
    ----------
    remediation_plan:
        The ``RemediationPlan`` being simulated.
    golden_dataset:
        List of golden case dicts.  Each dict must include at least a
        ``case_id`` key.  Optional keys: ``error_codes``, ``tags``.
    classification_records:
        Optional list of classification records for the source cluster.
        Used to link cases to the cluster's dominant error family.

    Returns
    -------
    Dict[str, Any]
        ``selected_case_ids`` — ordered list of selected case IDs.
        ``selection_reasons`` — auditable reasons for each selection decision.
    """
    reasons: List[str] = []
    dominant_codes = set(remediation_plan.dominant_error_codes)
    cluster_id = remediation_plan.cluster_id

    # Build index: case_id → case
    case_index: Dict[str, Dict[str, Any]] = {
        c["case_id"]: c for c in golden_dataset if "case_id" in c
    }

    # Determine which cases are linked to the source cluster
    cluster_linked_ids: List[str] = []
    if classification_records:
        for rec in classification_records:
            cid = getattr(rec, "context", {}).get("case_id") or getattr(rec, "case_id", None)
            if cid and cid in case_index:
                cluster_linked_ids.append(cid)
        cluster_linked_ids = list(dict.fromkeys(cluster_linked_ids))  # deduplicate, preserve order
        if cluster_linked_ids:
            reasons.append(
                f"cluster_linkage: found {len(cluster_linked_ids)} case(s) linked to "
                f"cluster_id={cluster_id!r} via classification_records"
            )

    # Identify targeted cases: cases whose error_codes overlap dominant codes
    targeted_ids: List[str] = []
    for cid, case in case_index.items():
        case_error_codes = set(case.get("error_codes", []))
        if case_error_codes & dominant_codes:
            targeted_ids.append(cid)

    if not targeted_ids and cluster_linked_ids:
        # Fall back to cluster-linked cases as targeted
        targeted_ids = cluster_linked_ids[:_MIN_TARGETED]
        reasons.append(
            "targeted_fallback: no cases with matching error_codes; "
            "using cluster-linked cases as targeted"
        )
    elif targeted_ids:
        reasons.append(
            f"targeted_selection: {len(targeted_ids)} case(s) matched "
            f"dominant_error_codes={sorted(dominant_codes)!r}"
        )

    # Identify control cases: cases NOT in targeted set
    all_case_ids = list(case_index.keys())
    control_ids = [cid for cid in all_case_ids if cid not in set(targeted_ids)]

    # Assemble selection
    if not targeted_ids and not control_ids:
        # No cases at all — return empty with reason
        reasons.append("no_cases: golden_dataset is empty; no cases selected")
        return {"selected_case_ids": [], "selection_reasons": reasons}

    # Guarantee minimum of 1 targeted, 1 control where possible
    selected_targeted = targeted_ids[:_MIN_TARGETED] if targeted_ids else []
    selected_control = control_ids[:_MIN_CONTROL] if control_ids else []

    if not selected_targeted:
        # If no targeted cases, promote first control to targeted role
        if selected_control:
            selected_targeted = selected_control[:1]
            selected_control = selected_control[1:]
            reasons.append(
                "targeted_promote: no targeted cases found; "
                "promoting first control case to satisfy minimum"
            )

    if not selected_control:
        # If no distinct control, take from remaining targeted set
        remaining = [cid for cid in targeted_ids if cid not in set(selected_targeted)]
        if remaining:
            selected_control = remaining[:1]
            reasons.append(
                "control_fallback: no control cases available; "
                "using second targeted case as control"
            )
        else:
            reasons.append(
                "control_unavailable: only one case exists; "
                "control case requirement cannot be met"
            )

    # Merge targeted + control, then add remaining linked cases
    selected: List[str] = list(dict.fromkeys(selected_targeted + selected_control))

    # Include remaining cluster-linked targeted cases (up to all available)
    for cid in targeted_ids:
        if cid not in set(selected):
            selected.append(cid)

    # Weak linkage fallback: if we have <2 cases total, include all golden cases
    if len(selected) < 2 and len(all_case_ids) > len(selected):
        reasons.append(
            "weak_linkage_fallback: fewer than 2 cases selected from targeted/control; "
            "falling back to all golden cases"
        )
        selected = all_case_ids

    reasons.append(f"final_selection: {len(selected)} case(s) selected")

    return {
        "selected_case_ids": selected,
        "selection_reasons": reasons,
    }
