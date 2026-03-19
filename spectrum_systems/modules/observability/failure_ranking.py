"""
Failure Ranking — spectrum_systems/modules/observability/failure_ranking.py

Ranks worst-case failures, failure modes, dangerous promotes, and pass
weaknesses so that observability reports are failure-first rather than
average-first.

Design principles
-----------------
- Dangerous promotes are ranked highest — a promoted case with active
  failure flags is more dangerous than a clear reject.
- High-confidence errors are ranked second — the system thinks it is right
  but is wrong.
- Structural failures, repeated patterns, and ordinary rejects follow.
- All functions are pure (no side effects) and return plain dicts.

Public API
----------
detect_high_confidence_error(record) -> bool
detect_dangerous_promote(record) -> tuple[bool, str]
rank_worst_cases(records) -> list[dict]
rank_failure_modes(records) -> list[dict]
rank_dangerous_promotes(records) -> list[dict]
rank_pass_weaknesses(records) -> list[dict]
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

from spectrum_systems.modules.observability.metrics import ObservabilityRecord

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

#: Minimum composite score to be labelled "high" confidence.
_HIGH_CONFIDENCE_THRESHOLD = 0.65

#: Minimum composite score to be labelled "medium" confidence
#: (and therefore eligible for high-confidence error detection).
_MEDIUM_CONFIDENCE_THRESHOLD = 0.4

#: Minimum score below which structural failure is declared.
_STRUCTURAL_FAILURE_THRESHOLD = 0.5

# ---------------------------------------------------------------------------
# Per-record detection helpers
# ---------------------------------------------------------------------------


def _compute_composite_score(record: ObservabilityRecord) -> float:
    """Return the mean of structural, semantic, and grounding scores."""
    return (
        record.structural_score + record.semantic_score + record.grounding_score
    ) / 3.0


def _confidence_level(record: ObservabilityRecord) -> str:
    """Return ``'high'``, ``'medium'``, or ``'low'`` for *record*.

    Confidence is derived from the composite of structural, semantic, and
    grounding scores.  This approximates model self-confidence when an
    explicit confidence field is absent.
    """
    composite = _compute_composite_score(record)
    if composite >= _HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    if composite >= _MEDIUM_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


def detect_high_confidence_error(record: ObservabilityRecord) -> bool:
    """Return ``True`` when the record is a high-confidence but failing output.

    A high-confidence error occurs when:
    - Composite score is in the medium-or-high confidence band
      (>= ``_MEDIUM_CONFIDENCE_THRESHOLD`` = 0.4), AND
    - The record carries at least one failure indicator
      (failure_count > 0, grounding not passed, or regression not passed).

    This is one of the most dangerous signals in the system: the model
    appears confident but is wrong.

    Parameters
    ----------
    record:
        ``ObservabilityRecord`` to evaluate.

    Returns
    -------
    bool
    """
    composite = _compute_composite_score(record)
    appears_confident = composite >= _MEDIUM_CONFIDENCE_THRESHOLD
    has_failure = (
        record.failure_count > 0
        or not record.grounding_passed
        or not record.regression_passed
    )
    return appears_confident and has_failure


def detect_dangerous_promote(
    record: ObservabilityRecord,
) -> Tuple[bool, str]:
    """Detect whether *record* represents a dangerous promote.

    A dangerous promote is a case where failure or adversarial indicators
    remain present despite the record passing surface-level gates.

    Criteria checked (first match wins):
    1. Record has active error_types but failure_count == 0 — silent failure.
    2. Human reviewer disagrees but failure_count == 0 — override suppressed.
    3. Grounding failed but structural score is high — structural illusion.
    4. Regression not passed with high semantic score — silent regression.

    Parameters
    ----------
    record:
        ``ObservabilityRecord`` to evaluate.

    Returns
    -------
    (dangerous, reason)
        ``dangerous`` is ``True`` when any criterion is met.
        ``reason`` is a human-readable explanation string (empty when
        ``dangerous`` is ``False``).
    """
    # Criterion 1: error types present but failure_count is zero
    if record.error_types and record.failure_count == 0:
        return True, (
            f"error_types present ({', '.join(record.error_types)}) "
            "but failure_count is 0 — silent failure"
        )

    # Criterion 2: human reviewer disagreed but failure_count suppressed
    if record.human_disagrees and record.failure_count == 0:
        return True, (
            "human reviewer disagrees but failure_count is 0 — override suppressed"
        )

    # Criterion 3: grounding failed with high structural score
    if not record.grounding_passed and record.structural_score >= 0.7:
        return True, (
            f"grounding failed but structural_score={record.structural_score:.2f} "
            "— structural illusion"
        )

    # Criterion 4: regression not passed with high semantic score
    if not record.regression_passed and record.semantic_score >= 0.7:
        return True, (
            f"regression not passed but semantic_score={record.semantic_score:.2f} "
            "— silent regression"
        )

    return False, ""


# ---------------------------------------------------------------------------
# Ranking helpers
# ---------------------------------------------------------------------------


def _severity_key(record: ObservabilityRecord) -> int:
    """Return a numeric severity rank (lower = worse) for sorting."""
    is_dangerous_promote, _ = detect_dangerous_promote(record)
    is_hce = detect_high_confidence_error(record)
    is_structural_failure = record.structural_score < _STRUCTURAL_FAILURE_THRESHOLD
    has_any_failure = record.failure_count > 0

    if is_dangerous_promote:
        return 0
    if is_hce:
        return 1
    if is_structural_failure:
        return 2
    if has_any_failure:
        return 3
    return 4


# ---------------------------------------------------------------------------
# Public ranking functions
# ---------------------------------------------------------------------------


def rank_worst_cases(
    records: List[ObservabilityRecord],
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Rank records from worst to best failure severity.

    Priority order:
    1. Dangerous promotes
    2. High-confidence errors
    3. Structural failures
    4. Other failures (non-zero failure_count)
    5. Clean records (included only if ``top_n`` permits)

    Parameters
    ----------
    records:
        List of ``ObservabilityRecord`` instances.
    top_n:
        Maximum number of results to return.

    Returns
    -------
    list[dict]
        Each dict contains ``record_id``, ``artifact_id``, ``case_id``,
        ``pass_type``, ``severity_rank``, ``is_dangerous_promote``,
        ``dangerous_promote_reason``, ``is_high_confidence_error``,
        ``failure_count``, ``error_types``, ``structural_score``,
        ``semantic_score``, ``grounding_score``, ``flags``.
    """
    ranked = sorted(records, key=_severity_key)
    result = []
    for rec in ranked[:top_n]:
        is_dp, dp_reason = detect_dangerous_promote(rec)
        is_hce = detect_high_confidence_error(rec)
        result.append({
            "record_id": rec.record_id,
            "artifact_id": rec.artifact_id,
            "case_id": rec.case_id,
            "pass_type": rec.pass_type,
            "severity_rank": _severity_key(rec),
            "is_dangerous_promote": is_dp,
            "dangerous_promote_reason": dp_reason,
            "is_high_confidence_error": is_hce,
            "failure_count": rec.failure_count,
            "error_types": rec.error_types,
            "structural_score": rec.structural_score,
            "semantic_score": rec.semantic_score,
            "grounding_score": rec.grounding_score,
            "flags": {
                "schema_valid": rec.schema_valid,
                "grounding_passed": rec.grounding_passed,
                "regression_passed": rec.regression_passed,
                "human_disagrees": rec.human_disagrees,
            },
        })
    return result


def rank_failure_modes(
    records: List[ObservabilityRecord],
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Rank failure modes by occurrence count, most frequent first.

    Failure modes are derived from ``error_types`` on each record.
    Records with no error types but non-zero ``failure_count`` are bucketed
    under ``"unclassified_failure"``.

    Parameters
    ----------
    records:
        List of ``ObservabilityRecord`` instances.
    top_n:
        Maximum number of failure modes to return.

    Returns
    -------
    list[dict]
        Each dict contains ``failure_mode``, ``count``, ``affected_records``,
        ``affected_pass_types``.
    """
    mode_counts: Counter = Counter()
    mode_records: Dict[str, List[str]] = defaultdict(list)
    mode_pass_types: Dict[str, set] = defaultdict(set)

    for rec in records:
        if rec.error_types:
            for et in rec.error_types:
                mode_counts[et] += 1
                mode_records[et].append(rec.record_id)
                mode_pass_types[et].add(rec.pass_type)
        elif rec.failure_count > 0:
            mode_counts["unclassified_failure"] += 1
            mode_records["unclassified_failure"].append(rec.record_id)
            mode_pass_types["unclassified_failure"].add(rec.pass_type)

    result = []
    for mode, count in mode_counts.most_common(top_n):
        result.append({
            "failure_mode": mode,
            "count": count,
            "affected_records": mode_records[mode],
            "affected_pass_types": sorted(mode_pass_types[mode]),
        })
    return result


def rank_dangerous_promotes(
    records: List[ObservabilityRecord],
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Return dangerous promote records ranked by severity.

    A record is a dangerous promote when ``detect_dangerous_promote`` returns
    ``True``.  Within that set, records are ordered by descending failure_count
    then descending error_type count.

    Parameters
    ----------
    records:
        List of ``ObservabilityRecord`` instances.
    top_n:
        Maximum number of results to return.

    Returns
    -------
    list[dict]
        Each dict contains ``record_id``, ``artifact_id``, ``case_id``,
        ``pass_type``, ``dangerous_promote_reason``, ``failure_count``,
        ``error_types``, ``confidence_level``.
    """
    dangerous = []
    for rec in records:
        is_dp, reason = detect_dangerous_promote(rec)
        if is_dp:
            dangerous.append((rec, reason))

    # Sort: more error_types first, then higher failure_count
    dangerous.sort(
        key=lambda x: (len(x[0].error_types), x[0].failure_count),
        reverse=True,
    )

    result = []
    for rec, reason in dangerous[:top_n]:
        result.append({
            "record_id": rec.record_id,
            "artifact_id": rec.artifact_id,
            "case_id": rec.case_id,
            "pass_type": rec.pass_type,
            "dangerous_promote_reason": reason,
            "failure_count": rec.failure_count,
            "error_types": rec.error_types,
            "confidence_level": _confidence_level(rec),
        })
    return result


def rank_pass_weaknesses(
    records: List[ObservabilityRecord],
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Rank passes / components by failure concentration, worst first.

    Failure concentration combines failure rate with dangerous promote
    and high-confidence error rates for the pass.

    Parameters
    ----------
    records:
        List of ``ObservabilityRecord`` instances.
    top_n:
        Maximum number of passes to return.

    Returns
    -------
    list[dict]
        Each dict contains ``pass_type``, ``record_count``,
        ``failure_rate``, ``dangerous_promote_rate``,
        ``high_confidence_error_rate``, ``total_failures``,
        ``total_dangerous_promotes``, ``total_high_confidence_errors``.
    """
    by_pass: Dict[str, List[ObservabilityRecord]] = defaultdict(list)
    for rec in records:
        by_pass[rec.pass_type].append(rec)

    result = []
    for pass_type, recs in by_pass.items():
        n = len(recs)
        failures = sum(1 for r in recs if r.failure_count > 0)
        dp_count = sum(1 for r in recs if detect_dangerous_promote(r)[0])
        hce_count = sum(1 for r in recs if detect_high_confidence_error(r))
        result.append({
            "pass_type": pass_type,
            "record_count": n,
            "failure_rate": failures / n if n > 0 else 0.0,
            "dangerous_promote_rate": dp_count / n if n > 0 else 0.0,
            "high_confidence_error_rate": hce_count / n if n > 0 else 0.0,
            "total_failures": failures,
            "total_dangerous_promotes": dp_count,
            "total_high_confidence_errors": hce_count,
        })

    # Sort by combined risk score: dangerous_promotes most weight
    result.sort(
        key=lambda x: (
            x["dangerous_promote_rate"] * 3
            + x["high_confidence_error_rate"] * 2
            + x["failure_rate"]
        ),
        reverse=True,
    )
    return result[:top_n]
