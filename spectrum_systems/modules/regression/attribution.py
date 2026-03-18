"""
Pass-Level Regression Attribution — spectrum_systems/modules/regression/attribution.py

Functions for attributing score regressions to specific passes and cases.

Design principles
-----------------
- Attribution is only claimed when pass-level data is available.
- Partial attribution is reported explicitly, not hidden.
- No fabrication of precision when granularity is insufficient.
- No external dependencies beyond the Python standard library.

Public API
----------
attribute_regressions_to_passes(eval_results, observability_records)
    Group regressions by pass_type and case.

compute_pass_regression_summary(pass_attributions)
    Aggregate per-pass regression counts and magnitudes.

identify_worst_passes(pass_regression_summary, top_n)
    Return the top-N worst passes by average regression magnitude.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def attribute_regressions_to_passes(
    baseline_records: List[Dict[str, Any]],
    candidate_records: List[Dict[str, Any]],
    dimensions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Match observability records by pass_type + case_id and compute deltas.

    Parameters
    ----------
    baseline_records:
        List of stable observability record dicts from the baseline run.
        Each dict must have at minimum: pass_type, case_id (optional),
        artifact_id, structural_score, semantic_score, grounding_score,
        latency_ms.
    candidate_records:
        Same format, from the candidate run.
    dimensions:
        Score dimensions to attribute.  Defaults to structural_score,
        semantic_score, grounding_score, latency_ms.

    Returns
    -------
    dict
        Keys:
        - pass_attributions: {pass_type -> [{case_id, dimension, baseline,
          candidate, delta}]}
        - unmatched_baseline: count of baseline records with no candidate match
        - unmatched_candidate: count of candidate records with no baseline match
        - partial_attribution: bool — True if any records could not be matched
    """
    if dimensions is None:
        dimensions = ["structural_score", "semantic_score", "grounding_score", "latency_ms"]

    # Index candidate records by (pass_type, case_id)
    cand_index: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for rec in candidate_records:
        key = (
            rec.get("pass_type", "unknown"),
            rec.get("case_id") or rec.get("artifact_id", ""),
        )
        cand_index[key].append(rec)

    pass_attributions: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    unmatched_baseline = 0

    for base_rec in baseline_records:
        pass_type = base_rec.get("pass_type", "unknown")
        case_key = base_rec.get("case_id") or base_rec.get("artifact_id", "")
        key = (pass_type, case_key)
        cands = cand_index.get(key, [])
        if not cands:
            unmatched_baseline += 1
            continue
        cand_rec = cands[0]
        for dim in dimensions:
            base_val = base_rec.get(dim)
            cand_val = cand_rec.get(dim)
            if base_val is None or cand_val is None:
                continue
            delta = float(cand_val) - float(base_val)
            pass_attributions[pass_type].append({
                "case_id": case_key or None,
                "pass_type": pass_type,
                "dimension": dim,
                "baseline_value": float(base_val),
                "candidate_value": float(cand_val),
                "delta": delta,
            })

    # Count unmatched candidate records
    base_keys = {
        (r.get("pass_type", "unknown"), r.get("case_id") or r.get("artifact_id", ""))
        for r in baseline_records
    }
    unmatched_candidate = sum(
        1
        for rec in candidate_records
        if (rec.get("pass_type", "unknown"), rec.get("case_id") or rec.get("artifact_id", ""))
        not in base_keys
    )

    partial = unmatched_baseline > 0 or unmatched_candidate > 0

    return {
        "pass_attributions": dict(pass_attributions),
        "unmatched_baseline": unmatched_baseline,
        "unmatched_candidate": unmatched_candidate,
        "partial_attribution": partial,
    }


def compute_pass_regression_summary(
    pass_attributions: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Dict[str, Any]]:
    """Aggregate per-pass attribution entries into summary statistics.

    Parameters
    ----------
    pass_attributions:
        Output from ``attribute_regressions_to_passes``["pass_attributions"].

    Returns
    -------
    dict
        Keys are pass types; values are dicts with per-dimension
        avg_delta, min_delta, record_count, and regression_count.
    """
    summary: Dict[str, Dict[str, Any]] = {}

    for pass_type, entries in pass_attributions.items():
        by_dim: Dict[str, List[float]] = defaultdict(list)
        for entry in entries:
            by_dim[entry["dimension"]].append(entry["delta"])

        dim_stats: Dict[str, Any] = {}
        for dim, deltas in by_dim.items():
            regressions = [d for d in deltas if d < 0]
            dim_stats[dim] = {
                "avg_delta": sum(deltas) / len(deltas),
                "min_delta": min(deltas),
                "record_count": len(deltas),
                "regression_count": len(regressions),
            }
        summary[pass_type] = {
            "dimension_stats": dim_stats,
            "total_entries": len(entries),
        }

    return summary


def identify_worst_passes(
    pass_regression_summary: Dict[str, Dict[str, Any]],
    top_n: int = 5,
    dimension: str = "semantic_score",
) -> List[Dict[str, Any]]:
    """Return the top-N worst passes by average regression magnitude for a dimension.

    Parameters
    ----------
    pass_regression_summary:
        Output from ``compute_pass_regression_summary``.
    top_n:
        Number of worst passes to return.
    dimension:
        Dimension to sort by.

    Returns
    -------
    list of dicts
        Each dict: pass_type, avg_delta, min_delta, regression_count, record_count.
        Sorted worst-first (most negative avg_delta first).
    """
    ranked: List[Dict[str, Any]] = []
    for pass_type, summary in pass_regression_summary.items():
        dim_stats = summary.get("dimension_stats", {}).get(dimension)
        if dim_stats is None:
            continue
        ranked.append({
            "pass_type": pass_type,
            "dimension": dimension,
            "avg_delta": dim_stats["avg_delta"],
            "min_delta": dim_stats["min_delta"],
            "regression_count": dim_stats["regression_count"],
            "record_count": dim_stats["record_count"],
        })

    ranked.sort(key=lambda x: x["avg_delta"])
    return ranked[:top_n]
