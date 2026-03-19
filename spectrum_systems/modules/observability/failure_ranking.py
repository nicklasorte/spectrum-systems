"""Failure-first ranking utilities for observability case records."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from spectrum_systems.modules.observability.aggregation import enrich_failure_first_flags


def _severity_score(case: Dict[str, Any]) -> int:
    gating = str(case.get("gate_result") or case.get("promotion_recommendation") or "hold").lower()
    base = 0
    if case.get("dangerous_promote"):
        base += 500
    if case.get("high_confidence_error"):
        base += 300
    if case.get("failure_flags", {}).get("structural_failure") or case.get("structural_failure"):
        base += 200
    if any(bool(v) for v in (case.get("failure_flags") or {}).values()):
        base += 100
    if gating == "reject":
        base += 50
    return base


def rank_worst_cases(cases: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    """Rank individual cases by severity (failure-first ordering)."""
    enriched = [enrich_failure_first_flags(case) for case in cases]
    ranked = sorted(
        enriched,
        key=lambda case: (
            _severity_score(case),
            len([k for k, v in (case.get("failure_flags") or {}).items() if v]),
            -float(case.get("structural_score", 1.0) if case.get("structural_score") is not None else 1.0),
        ),
        reverse=True,
    )
    return ranked[:limit]


def rank_failure_modes(cases: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    """Rank recurring failure modes by count and severity weighting."""
    counts: Dict[str, int] = defaultdict(int)
    weighted: Dict[str, int] = defaultdict(int)
    for case in [enrich_failure_first_flags(c) for c in cases]:
        flags = case.get("failure_flags") or {}
        active = [k for k, v in flags.items() if v]
        if not active:
            gating = str(case.get("gate_result") or case.get("promotion_recommendation") or "hold").lower()
            if gating == "reject":
                active = ["reject_without_explicit_flag"]
        for flag in active:
            counts[flag] += 1
            weighted[flag] += _severity_score(case)

    ranked = sorted(
        (
            {"failure_mode": mode, "count": count, "weighted_severity": weighted[mode]}
            for mode, count in counts.items()
        ),
        key=lambda item: (item["count"], item["weighted_severity"]),
        reverse=True,
    )
    return ranked[:limit]


def rank_dangerous_promotes(cases: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    """Rank promoted cases that still appear risky."""
    dangerous = [
        case
        for case in [enrich_failure_first_flags(c) for c in cases]
        if case.get("dangerous_promote")
    ]
    dangerous.sort(key=lambda case: _severity_score(case), reverse=True)
    return dangerous[:limit]


def rank_pass_weaknesses(cases: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    """Rank pass/component weakness by failure concentration."""
    pass_counts: Dict[str, int] = defaultdict(int)
    pass_cases: Dict[str, set[str]] = defaultdict(set)

    for case in [enrich_failure_first_flags(c) for c in cases]:
        has_failure = any(bool(v) for v in (case.get("failure_flags") or {}).values())
        if not has_failure and not case.get("high_confidence_error"):
            continue
        case_id = str(case.get("case_id") or case.get("artifact_id") or "unknown_case")
        for pass_result in case.get("pass_results", []):
            pass_type = str(pass_result.get("pass_type") or "unknown")
            pass_counts[pass_type] += 1
            pass_cases[pass_type].add(case_id)

    ranked = sorted(
        (
            {
                "pass_type": pass_type,
                "failure_count": count,
                "affected_cases": len(pass_cases[pass_type]),
            }
            for pass_type, count in pass_counts.items()
        ),
        key=lambda item: (item["failure_count"], item["affected_cases"]),
        reverse=True,
    )
    return ranked[:limit]
