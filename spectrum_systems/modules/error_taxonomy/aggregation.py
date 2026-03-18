"""
Aggregation Support — spectrum_systems/modules/error_taxonomy/aggregation.py

Aggregates classification records for downstream analysis, trend visibility,
and remediation targeting.

Prepares data for:
- AV failure clustering
- AW prompt improvement loop

Public API
----------
count_by_family(classification_records) -> Dict[str, int]
count_by_subtype(classification_records) -> Dict[str, int]
count_by_remediation_target(classification_records, catalog) -> Dict[str, int]
count_by_source_system(classification_records) -> Dict[str, int]
count_by_pass_type(classification_records) -> Dict[str, int]
identify_highest_impact_subtypes(classification_records, catalog, top_n) -> List[Dict]
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from spectrum_systems.modules.error_taxonomy.catalog import ErrorTaxonomyCatalog
    from spectrum_systems.modules.error_taxonomy.classify import ErrorClassificationRecord


def _iter_codes(records: List[Any]) -> List[str]:
    """Yield all error_codes from a list of classification records."""
    codes: List[str] = []
    for rec in records:
        for entry in rec.classifications:
            codes.append(entry["error_code"])
    return codes


def count_by_family(records: List[Any]) -> Dict[str, int]:
    """Count classifications grouped by top-level family code.

    Parameters
    ----------
    records:
        List of ``ErrorClassificationRecord`` objects.

    Returns
    -------
    Dict[str, int]
        Mapping of family_code → count, sorted by count descending.
    """
    counts: Dict[str, int] = defaultdict(int)
    for code in _iter_codes(records):
        family = code.split(".")[0] if "." in code else code
        counts[family] += 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def count_by_subtype(records: List[Any]) -> Dict[str, int]:
    """Count classifications grouped by full error code (subtype).

    Parameters
    ----------
    records:
        List of ``ErrorClassificationRecord`` objects.

    Returns
    -------
    Dict[str, int]
        Mapping of error_code → count, sorted by count descending.
    """
    counts: Dict[str, int] = defaultdict(int)
    for code in _iter_codes(records):
        counts[code] += 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def count_by_remediation_target(
    records: List[Any],
    catalog: "ErrorTaxonomyCatalog",
) -> Dict[str, int]:
    """Count classifications grouped by remediation_target.

    Parameters
    ----------
    records:
        List of ``ErrorClassificationRecord`` objects.
    catalog:
        Loaded ``ErrorTaxonomyCatalog`` for subtype lookup.

    Returns
    -------
    Dict[str, int]
        Mapping of remediation_target → count, sorted by count descending.
    """
    counts: Dict[str, int] = defaultdict(int)
    for code in _iter_codes(records):
        subtype = catalog.get_error(code)
        target = subtype.remediation_target if subtype else "unknown"
        counts[target] += 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def count_by_source_system(records: List[Any]) -> Dict[str, int]:
    """Count classifications grouped by source system.

    Parameters
    ----------
    records:
        List of ``ErrorClassificationRecord`` objects.

    Returns
    -------
    Dict[str, int]
        Mapping of source_system → count, sorted by count descending.
    """
    counts: Dict[str, int] = defaultdict(int)
    for rec in records:
        source = rec.context.get("source_system", "unknown")
        # Count once per record (not per classification entry)
        counts[source] += len(rec.classifications)
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def count_by_pass_type(records: List[Any]) -> Dict[str, int]:
    """Count classifications grouped by pass_type from context.

    Parameters
    ----------
    records:
        List of ``ErrorClassificationRecord`` objects.

    Returns
    -------
    Dict[str, int]
        Mapping of pass_type → count.
    """
    counts: Dict[str, int] = defaultdict(int)
    for rec in records:
        pass_type = rec.context.get("pass_type") or "unknown"
        counts[pass_type] += len(rec.classifications)
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def identify_highest_impact_subtypes(
    records: List[Any],
    catalog: "ErrorTaxonomyCatalog",
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Identify the highest-impact error subtypes by combined count and severity.

    Impact score = count × severity_weight.
    Severity weights: critical=4, high=3, medium=2, low=1.

    Parameters
    ----------
    records:
        List of ``ErrorClassificationRecord`` objects.
    catalog:
        Loaded ``ErrorTaxonomyCatalog``.
    top_n:
        Number of top subtypes to return.

    Returns
    -------
    List[Dict[str, Any]]
        Sorted list of dicts with keys:
        ``error_code``, ``count``, ``default_severity``,
        ``remediation_target``, ``impact_score``.
    """
    _SEVERITY_WEIGHTS = {"critical": 4, "high": 3, "medium": 2, "low": 1}

    code_counts: Dict[str, int] = defaultdict(int)
    for code in _iter_codes(records):
        code_counts[code] += 1

    results = []
    for code, count in code_counts.items():
        subtype = catalog.get_error(code)
        severity = subtype.default_severity if subtype else "medium"
        remediation = subtype.remediation_target if subtype else "unknown"
        weight = _SEVERITY_WEIGHTS.get(severity, 2)
        results.append({
            "error_code": code,
            "count": count,
            "default_severity": severity,
            "remediation_target": remediation,
            "impact_score": count * weight,
        })

    results.sort(key=lambda x: x["impact_score"], reverse=True)
    return results[:top_n]
