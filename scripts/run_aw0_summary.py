#!/usr/bin/env python3
"""
AW0 Cluster Validation Summary — scripts/run_aw0_summary.py

Reads persisted ValidatedCluster objects from data/validated_clusters/,
produces a human-readable console report, and writes a structured JSON
summary to outputs/aw0_validation_summary.json.

Usage
-----
    python scripts/run_aw0_summary.py

If data/validated_clusters/ is empty, run first:
    python scripts/run_cluster_validation.py --all

Outputs
-------
- Console: summary statistics, invalidation breakdown, top valid/invalid clusters.
- JSON: outputs/aw0_validation_summary.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import List

# Ensure project root is on sys.path when run directly
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from spectrum_systems.modules.error_taxonomy.cluster_validation import ValidatedCluster
from spectrum_systems.modules.error_taxonomy.validated_cluster_store import (
    load_validated_clusters,
)

_VALIDATED_STORE_DIR = _ROOT / "data" / "validated_clusters"
_OUTPUTS_DIR = _ROOT / "outputs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_invalidation_tags(validation_reasons: List[str]) -> List[str]:
    """Return the short failure tag for each reason that represents an invalidation."""
    invalid_tags = {
        "too_small",
        "low_cohesion",
        "too_broad",
        "unstable_signature",
        "unclear_remediation",
        "low_confidence",
    }
    tags: List[str] = []
    for reason in validation_reasons:
        tag = reason.split(":")[0]
        if tag in invalid_tags:
            tags.append(tag)
    return tags


def _cluster_to_report_dict(vc: ValidatedCluster, include_reasons: bool = False) -> dict:
    """Serialise the fields required by the report spec."""
    data = {
        "cluster_id": vc.cluster_id,
        "cluster_signature": vc.cluster_signature,
        "record_count": vc.record_count,
        "error_codes": vc.error_codes,
        "pass_types": vc.pass_types,
        "remediation_targets": vc.remediation_targets,
        "cohesion_score": round(vc.cohesion_score, 4),
        "actionability_score": round(vc.actionability_score, 4),
        "stability_score": round(vc.stability_score, 4),
        "validation_status": vc.validation_status,
    }
    if include_reasons:
        data["validation_reasons"] = vc.validation_reasons
    return data


def _print_divider(width: int = 60) -> None:
    print("  " + "─" * width)


def _print_cluster(vc: ValidatedCluster, include_reasons: bool = False) -> None:
    print(f"    cluster_id:           {vc.cluster_id}")
    print(f"    cluster_signature:    {vc.cluster_signature}")
    print(f"    record_count:         {vc.record_count}")
    print(f"    error_codes:          {', '.join(vc.error_codes)}")
    print(f"    pass_types:           {', '.join(vc.pass_types)}")
    print(f"    remediation_targets:  {', '.join(vc.remediation_targets)}")
    print(f"    cohesion_score:       {vc.cohesion_score:.4f}")
    print(f"    actionability_score:  {vc.actionability_score:.4f}")
    print(f"    stability_score:      {vc.stability_score:.4f}")
    print(f"    validation_status:    {vc.validation_status}")
    if include_reasons:
        print(f"    validation_reasons:")
        for r in vc.validation_reasons:
            print(f"      - {r}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    clusters = load_validated_clusters(_VALIDATED_STORE_DIR)

    if not clusters:
        print(
            "No validated clusters found in data/validated_clusters/.\n"
            "Run first:  python scripts/run_cluster_validation.py --all"
        )
        sys.exit(0)

    valid_clusters = [c for c in clusters if c.validation_status == "valid"]
    invalid_clusters = [c for c in clusters if c.validation_status == "invalid"]

    total = len(clusters)
    n_valid = len(valid_clusters)
    n_invalid = len(invalid_clusters)
    valid_pct = round(100.0 * n_valid / total, 2) if total > 0 else 0.0
    invalid_pct = round(100.0 * n_invalid / total, 2) if total > 0 else 0.0

    # Invalidation breakdown
    reason_counter: Counter[str] = Counter()
    for vc in invalid_clusters:
        for tag in _extract_invalidation_tags(vc.validation_reasons):
            reason_counter[tag] += 1

    # Top valid clusters: highest actionability_score, then cohesion_score, then record_count
    top_valid = sorted(
        valid_clusters,
        key=lambda c: (c.actionability_score, c.cohesion_score, c.record_count),
        reverse=True,
    )[:3]

    # Top invalid clusters: largest record_count, then most validation_reasons
    top_invalid = sorted(
        invalid_clusters,
        key=lambda c: (c.record_count, len(c.validation_reasons)),
        reverse=True,
    )[:3]

    # ── Console Output ────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("  AW0 CLUSTER VALIDATION SUMMARY")
    print("=" * 62)

    print()
    print("  1. SUMMARY STATISTICS")
    _print_divider()
    print(f"  total_clusters:     {total}")
    print(f"  valid_clusters:     {n_valid}")
    print(f"  invalid_clusters:   {n_invalid}")
    print(f"  valid_percentage:   {valid_pct:.2f}%")
    print(f"  invalid_percentage: {invalid_pct:.2f}%")
    print()

    print("  2. INVALIDATION BREAKDOWN")
    _print_divider()
    if reason_counter:
        for tag, count in reason_counter.most_common():
            print(f"  {tag}: {count}")
    else:
        print("  (no invalid clusters)")
    print()

    print("  3. TOP VALID CLUSTERS (up to 3)")
    _print_divider()
    if top_valid:
        for i, vc in enumerate(top_valid, start=1):
            print(f"  [{i}]")
            _print_cluster(vc, include_reasons=False)
            print()
    else:
        print("  (no valid clusters)")
        print()

    print("  4. TOP INVALID CLUSTERS (up to 3)")
    _print_divider()
    if top_invalid:
        for i, vc in enumerate(top_invalid, start=1):
            print(f"  [{i}]")
            _print_cluster(vc, include_reasons=True)
            print()
    else:
        print("  (no invalid clusters)")
        print()

    # ── JSON Output ────────────────────────────────────────────────────────
    output = {
        "summary": {
            "total_clusters": total,
            "valid_clusters": n_valid,
            "invalid_clusters": n_invalid,
            "valid_percentage": valid_pct,
            "invalid_percentage": invalid_pct,
        },
        "invalidation_breakdown": dict(reason_counter.most_common()),
        "top_valid_clusters": [_cluster_to_report_dict(c) for c in top_valid],
        "top_invalid_clusters": [
            _cluster_to_report_dict(c, include_reasons=True) for c in top_invalid
        ],
    }

    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _OUTPUTS_DIR / "aw0_validation_summary.json"
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)

    print(f"  5. JSON output written to: {report_path}")
    print()


if __name__ == "__main__":
    main()
