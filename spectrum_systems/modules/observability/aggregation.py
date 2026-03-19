"""
Aggregation Engine — spectrum_systems/modules/observability/aggregation.py

Computes structured aggregations over observability records.

All functions accept a list of ``ObservabilityRecord`` instances and return
plain dicts suitable for JSON serialisation and downstream consumption.

Design principles
-----------------
- No side effects: pure aggregation over provided records.
- All return values are structured and queryable.
- Uses only the Python standard library.

Public API
----------
compute_pass_metrics(records) -> dict
compute_error_distribution(records) -> dict
compute_human_disagreement(records) -> dict
compute_grounding_failure_rate(records) -> dict
compute_latency_stats(records) -> dict
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any, Dict, List, Optional

from spectrum_systems.modules.observability.metrics import ObservabilityRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_mean(values: List[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _safe_pct(numerator: int, denominator: int) -> Optional[float]:
    return numerator / denominator if denominator > 0 else None


# ---------------------------------------------------------------------------
# Aggregation functions
# ---------------------------------------------------------------------------


def compute_pass_metrics(records: List[ObservabilityRecord]) -> Dict[str, Any]:
    """Compute per-pass aggregated metrics.

    Groups records by ``pass_type`` and returns average scores, latency,
    and failure rates.

    Parameters
    ----------
    records:
        List of ``ObservabilityRecord`` instances.

    Returns
    -------
    dict
        Keys: ``by_pass_type`` (dict of pass_type → stats),
        ``overall`` (aggregate across all records).
    """
    if not records:
        return {"by_pass_type": {}, "overall": {}}

    by_pass: Dict[str, List[ObservabilityRecord]] = defaultdict(list)
    for r in records:
        by_pass[r.pass_type].append(r)

    by_pass_type: Dict[str, Any] = {}
    for pass_type, recs in by_pass.items():
        n = len(recs)
        failures = sum(1 for r in recs if r.failure_count > 0)
        by_pass_type[pass_type] = {
            "record_count": n,
            "avg_structural_score": _safe_mean([r.structural_score for r in recs]),
            "avg_semantic_score": _safe_mean([r.semantic_score for r in recs]),
            "avg_grounding_score": _safe_mean([r.grounding_score for r in recs]),
            "avg_latency_ms": _safe_mean([float(r.latency_ms) for r in recs]),
            "failure_rate": _safe_pct(failures, n),
            "total_failures": failures,
        }

    n_all = len(records)
    all_failures = sum(1 for r in records if r.failure_count > 0)
    overall = {
        "record_count": n_all,
        "avg_structural_score": _safe_mean([r.structural_score for r in records]),
        "avg_semantic_score": _safe_mean([r.semantic_score for r in records]),
        "avg_grounding_score": _safe_mean([r.grounding_score for r in records]),
        "avg_latency_ms": _safe_mean([float(r.latency_ms) for r in records]),
        "failure_rate": _safe_pct(all_failures, n_all),
    }

    return {"by_pass_type": by_pass_type, "overall": overall}


def compute_error_distribution(records: List[ObservabilityRecord]) -> Dict[str, Any]:
    """Count errors by type across all records.

    Parameters
    ----------
    records:
        List of ``ObservabilityRecord`` instances.

    Returns
    -------
    dict
        Keys: ``by_error_type`` (dict of error_type → count),
        ``total_error_count`` (int),
        ``top_error_type`` (str | None).
    """
    counts: Dict[str, int] = defaultdict(int)
    for r in records:
        for et in r.error_types:
            counts[et] += 1

    total = sum(counts.values())
    top = max(counts, key=lambda k: counts[k]) if counts else None

    return {
        "by_error_type": dict(counts),
        "total_error_count": total,
        "top_error_type": top,
    }


def compute_human_disagreement(records: List[ObservabilityRecord]) -> Dict[str, Any]:
    """Compute human disagreement rates per pass type and per artifact.

    Parameters
    ----------
    records:
        List of ``ObservabilityRecord`` instances.

    Returns
    -------
    dict
        Keys:
        ``overall_disagreement_rate`` (float | None),
        ``by_pass_type`` (dict of pass_type → rate),
        ``by_artifact_id`` (dict of artifact_id → rate).
    """
    if not records:
        return {
            "overall_disagreement_rate": None,
            "by_pass_type": {},
            "by_artifact_id": {},
        }

    total_disagreements = sum(1 for r in records if r.human_disagrees)
    overall_rate = _safe_pct(total_disagreements, len(records))

    by_pass: Dict[str, List[bool]] = defaultdict(list)
    by_artifact: Dict[str, List[bool]] = defaultdict(list)
    for r in records:
        by_pass[r.pass_type].append(r.human_disagrees)
        by_artifact[r.artifact_id].append(r.human_disagrees)

    by_pass_type = {
        pt: _safe_pct(sum(1 for v in vals if v), len(vals))
        for pt, vals in by_pass.items()
    }
    by_artifact_id = {
        aid: _safe_pct(sum(1 for v in vals if v), len(vals))
        for aid, vals in by_artifact.items()
    }

    return {
        "overall_disagreement_rate": overall_rate,
        "by_pass_type": by_pass_type,
        "by_artifact_id": by_artifact_id,
    }


def compute_grounding_failure_rate(records: List[ObservabilityRecord]) -> Dict[str, Any]:
    """Compute grounding failure rates overall and per pass type.

    Parameters
    ----------
    records:
        List of ``ObservabilityRecord`` instances.

    Returns
    -------
    dict
        Keys: ``overall_failure_rate`` (float | None),
        ``by_pass_type`` (dict of pass_type → rate),
        ``avg_grounding_score`` (float | None).
    """
    if not records:
        return {
            "overall_failure_rate": None,
            "by_pass_type": {},
            "avg_grounding_score": None,
        }

    grounding_failures = sum(1 for r in records if not r.grounding_passed)
    overall_rate = _safe_pct(grounding_failures, len(records))

    by_pass: Dict[str, List[bool]] = defaultdict(list)
    for r in records:
        by_pass[r.pass_type].append(not r.grounding_passed)

    by_pass_type = {
        pt: _safe_pct(sum(1 for v in vals if v), len(vals))
        for pt, vals in by_pass.items()
    }

    return {
        "overall_failure_rate": overall_rate,
        "by_pass_type": by_pass_type,
        "avg_grounding_score": _safe_mean([r.grounding_score for r in records]),
    }


def compute_latency_stats(records: List[ObservabilityRecord]) -> Dict[str, Any]:
    """Compute latency statistics: mean, p95, and max.

    Parameters
    ----------
    records:
        List of ``ObservabilityRecord`` instances.

    Returns
    -------
    dict
        Keys: ``mean_ms``, ``p95_ms``, ``max_ms``, ``by_pass_type``
        (dict of pass_type → ``{mean_ms, p95_ms, max_ms}``).
    """
    if not records:
        return {"mean_ms": None, "p95_ms": None, "max_ms": None, "by_pass_type": {}}

    latencies = [r.latency_ms for r in records]

    def _p95(vals: List[int]) -> float:
        if not vals:
            return 0.0
        sorted_vals = sorted(vals)
        # Use the value at the 95th percentile index (0-based).
        # For n values: index = int(n * 0.95), clamped to valid range.
        idx = min(int(len(sorted_vals) * 0.95), len(sorted_vals) - 1)
        return float(sorted_vals[idx])

    by_pass: Dict[str, List[int]] = defaultdict(list)
    for r in records:
        by_pass[r.pass_type].append(r.latency_ms)

    by_pass_type = {
        pt: {
            "mean_ms": statistics.mean(vals),
            "p95_ms": _p95(vals),
            "max_ms": max(vals),
        }
        for pt, vals in by_pass.items()
    }

    return {
        "mean_ms": statistics.mean(latencies),
        "p95_ms": _p95(latencies),
        "max_ms": max(latencies),
        "by_pass_type": by_pass_type,
    }


def compute_weakest_passes(records: List[ObservabilityRecord]) -> List[Dict[str, Any]]:
    """Identify passes ranked by descending failure rate.

    Parameters
    ----------
    records:
        List of ``ObservabilityRecord`` instances.

    Returns
    -------
    list[dict]
        List of dicts with ``pass_type``, ``failure_rate``,
        ``avg_structural_score``, ``avg_grounding_score``,
        sorted by failure_rate descending.
    """
    pass_metrics = compute_pass_metrics(records)
    ranked = []
    for pt, stats in pass_metrics["by_pass_type"].items():
        ranked.append({
            "pass_type": pt,
            "failure_rate": stats.get("failure_rate") or 0.0,
            "avg_structural_score": stats.get("avg_structural_score"),
            "avg_grounding_score": stats.get("avg_grounding_score"),
            "record_count": stats.get("record_count", 0),
        })
    ranked.sort(key=lambda x: x["failure_rate"], reverse=True)
    return ranked


def _as_confidence_band(value: Any) -> str:
    """Normalise confidence to low/medium/high."""
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"low", "medium", "high"}:
            return lowered
    if isinstance(value, (int, float)):
        if value >= 0.8:
            return "high"
        if value >= 0.5:
            return "medium"
    return "low"


def enrich_failure_first_flags(case: Dict[str, Any]) -> Dict[str, Any]:
    """Attach failure-first derived flags to a case-like record dict."""
    enriched = dict(case)
    gating = str(
        enriched.get("gate_result")
        or enriched.get("promotion_recommendation")
        or "hold"
    ).lower()
    failure_flags = dict(enriched.get("failure_flags") or {})
    gating_flags = list(enriched.get("gating_flags") or [])
    confidence_band = _as_confidence_band(enriched.get("confidence"))

    gate_failed = gating in {"hold", "reject"}
    downstream_failed = bool(enriched.get("downstream_failure"))
    high_confidence_error = confidence_band in {"medium", "high"} and (
        gate_failed or downstream_failed
    )
    enriched["high_confidence_error"] = high_confidence_error

    structural_failure = bool(
        failure_flags.get("structural_failure")
        or enriched.get("structural_failure")
        or ((enriched.get("structural_score") is not None) and enriched.get("structural_score", 1) < 0.6)
    )
    inconsistent_grounding = bool(
        failure_flags.get("inconsistent_grounding")
        or enriched.get("inconsistent_grounding")
    )

    dangerous_reasons: List[str] = []
    if gating == "promote" and failure_flags:
        flagged = sorted([k for k, v in failure_flags.items() if v])
        if flagged:
            dangerous_reasons.append(f"failure_flags={','.join(flagged)}")
    if gating == "promote" and bool(enriched.get("adversarial_type")):
        dangerous_reasons.append("promoted_adversarial_case")
    if gating == "promote" and structural_failure:
        dangerous_reasons.append("structural_weakness")
    if gating == "promote" and inconsistent_grounding:
        dangerous_reasons.append("unclear_or_inconsistent_grounding")

    enriched["dangerous_promote"] = bool(dangerous_reasons)
    enriched["dangerous_promote_reason"] = "; ".join(dangerous_reasons)
    return enriched


def compute_failure_first_metrics(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute failure-first derived metrics across case-level records."""
    if not cases:
        return {
            "total_cases": 0,
            "rejection_rate": None,
            "promote_rate": None,
            "structural_failure_rate": None,
            "no_decision_extraction_rate": None,
            "duplicate_decision_rate": None,
            "inconsistent_grounding_rate": None,
            "high_confidence_error_rate": None,
            "dangerous_promote_count": 0,
            "repeated_failure_concentration": [],
            "pass_failure_concentration": {},
        }

    enriched = [enrich_failure_first_flags(case) for case in cases]
    total = len(enriched)
    promoted = 0
    rejected = 0
    structural_failures = 0
    no_decisions = 0
    duplicates = 0
    inconsistent_grounding = 0
    high_conf_errors = 0
    dangerous_promotes = 0
    failure_pattern_counts: Dict[str, int] = defaultdict(int)
    pass_failure_counts: Dict[str, int] = defaultdict(int)

    for case in enriched:
        gating = str(
            case.get("gate_result")
            or case.get("promotion_recommendation")
            or "hold"
        ).lower()
        if gating == "promote":
            promoted += 1
        if gating == "reject":
            rejected += 1

        flags = dict(case.get("failure_flags") or {})
        if flags.get("structural_failure") or case.get("structural_failure"):
            structural_failures += 1
        if flags.get("no_decisions_extracted"):
            no_decisions += 1
        if flags.get("duplicate_decisions"):
            duplicates += 1
        if flags.get("inconsistent_grounding") or case.get("inconsistent_grounding"):
            inconsistent_grounding += 1

        if case.get("high_confidence_error"):
            high_conf_errors += 1
        if case.get("dangerous_promote"):
            dangerous_promotes += 1

        active_flags = sorted([k for k, v in flags.items() if v]) or ["no_flag"]
        failure_pattern_counts["+".join(active_flags)] += 1

        for pass_result in case.get("pass_results", []):
            pass_type = str(pass_result.get("pass_type") or "unknown")
            pass_has_failure = (
                bool(case.get("failure_flags"))
                and any(bool(v) for v in case.get("failure_flags", {}).values())
            ) or str(
                pass_result.get("schema_validation", {}).get("status", "")
            ).lower() != "passed"
            if pass_has_failure:
                pass_failure_counts[pass_type] += 1

    top_patterns = sorted(
        (
            {"pattern": pattern, "count": count}
            for pattern, count in failure_pattern_counts.items()
            if pattern != "no_flag"
        ),
        key=lambda item: item["count"],
        reverse=True,
    )[:3]

    return {
        "total_cases": total,
        "rejection_rate": _safe_pct(rejected, total),
        "promote_rate": _safe_pct(promoted, total),
        "structural_failure_rate": _safe_pct(structural_failures, total),
        "no_decision_extraction_rate": _safe_pct(no_decisions, total),
        "duplicate_decision_rate": _safe_pct(duplicates, total),
        "inconsistent_grounding_rate": _safe_pct(inconsistent_grounding, total),
        "high_confidence_error_rate": _safe_pct(high_conf_errors, total),
        "dangerous_promote_count": dangerous_promotes,
        "repeated_failure_concentration": top_patterns,
        "pass_failure_concentration": dict(
            sorted(pass_failure_counts.items(), key=lambda item: item[1], reverse=True)
        ),
    }
