#!/usr/bin/env python3
"""
Auto-Failure Clustering — scripts/run_error_clustering.py

Reads persisted error classification records (AU), clusters them into
recurring failure patterns (AV), ranks them by impact, and emits a
console summary plus a JSON output file.

Usage
-----
    python scripts/run_error_clustering.py --all
    python scripts/run_error_clustering.py --case CASE_ID

Outputs
-------
- Console summary: top clusters, cluster sizes, dominant families,
  recommended remediation targets.
- JSON: outputs/error_clusters.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path when run directly
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from spectrum_systems.modules.error_taxonomy.catalog import ErrorTaxonomyCatalog
from spectrum_systems.modules.error_taxonomy.classify import ErrorClassificationRecord
from spectrum_systems.modules.error_taxonomy.cluster_pipeline import (
    build_clusters_from_classifications,
    rank_and_filter_clusters,
)

_STORE_DIR = _ROOT / "data" / "error_classifications"
_OUTPUTS_DIR = _ROOT / "outputs"


def _load_records(
    all_records: bool,
    case_id: str | None,
) -> list[ErrorClassificationRecord]:
    records = ErrorClassificationRecord.list_all(_STORE_DIR)
    if case_id:
        records = [r for r in records if r.context.get("case_id") == case_id]
    return records


def _print_divider(width: int = 60) -> None:
    print("  " + "─" * width)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cluster error classification records into failure patterns."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all", action="store_true", help="Include all classification records."
    )
    group.add_argument(
        "--case", metavar="CASE_ID", help="Filter to a specific case ID."
    )
    args = parser.parse_args()

    case_id = args.case if args.case else None

    records = _load_records(all_records=args.all, case_id=case_id)

    if not records:
        filter_desc = f" for case '{case_id}'" if case_id else ""
        print(f"No classification records found{filter_desc}.")
        sys.exit(0)

    catalog = ErrorTaxonomyCatalog.load_catalog()

    # Build and rank clusters (no min_size filter here — show all)
    clusters = build_clusters_from_classifications(records, catalog)

    # Apply min_size=3 filter for the "actionable" view
    actionable = rank_and_filter_clusters(clusters, min_size=3)

    # ── Console Summary ────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("  AUTO-FAILURE CLUSTERING REPORT (Prompt AV)")
    print("=" * 62)
    if case_id:
        print(f"  Filter:         case_id = {case_id}")
    else:
        print("  Filter:         all records")
    print(f"  Input records:  {len(records)}")
    print(f"  Total clusters: {len(clusters)}")
    print(f"  Actionable (≥3 records): {len(actionable)}")
    print(f"  Taxonomy:       {catalog.taxonomy_id} v{catalog.version}")
    print()

    print("  TOP CLUSTERS BY IMPACT")
    _print_divider()
    top = clusters[:10]
    if not top:
        print("  (no clusters)")
    for rank, c in enumerate(top, 1):
        sig = c.cluster_signature
        m = c.metrics
        print(
            f"  {rank:>2}. {sig['primary_error_code']:<35}"
            f"  n={m['record_count']:>3}"
            f"  sev={m['weighted_severity_score']:>6.2f}"
            f"  conf={m['avg_confidence']:.2f}"
        )
        if sig["secondary_error_codes"]:
            secondary_str = ", ".join(sig["secondary_error_codes"][:3])
            if len(sig["secondary_error_codes"]) > 3:
                secondary_str += f" (+{len(sig['secondary_error_codes']) - 3} more)"
            print(f"      co-occurs: {secondary_str}")
        if c.remediation_targets:
            print(f"      remediate: {', '.join(c.remediation_targets)}")
    print()

    # Dominant families
    family_counts: dict[str, int] = {}
    for c in clusters:
        fam = c.cluster_signature["dominant_family"]
        family_counts[fam] = family_counts.get(fam, 0) + c.metrics["record_count"]
    family_sorted = sorted(family_counts.items(), key=lambda x: x[1], reverse=True)

    print("  DOMINANT ERROR FAMILIES")
    _print_divider()
    for fam, cnt in family_sorted[:8]:
        print(f"  {'':>3}{fam:<35}  {cnt:>4} records")
    print()

    # Remediation targets
    remediation_counts: dict[str, int] = {}
    for c in clusters:
        for t in c.remediation_targets:
            remediation_counts[t] = remediation_counts.get(t, 0) + c.metrics["record_count"]
    remediation_sorted = sorted(
        remediation_counts.items(), key=lambda x: x[1], reverse=True
    )

    print("  RECOMMENDED REMEDIATION TARGETS")
    _print_divider()
    for target, cnt in remediation_sorted[:8]:
        print(f"  {'':>3}{target:<35}  {cnt:>4} records")
    print()

    # ── JSON Output ────────────────────────────────────────────────────────
    output = {
        "report_type": "error_clustering_report",
        "taxonomy_id": catalog.taxonomy_id,
        "taxonomy_version": catalog.version,
        "filters": {"case_id": case_id, "all": args.all},
        "summary": {
            "input_record_count": len(records),
            "total_clusters": len(clusters),
            "actionable_clusters": len(actionable),
        },
        "clusters": [c.to_dict() for c in clusters],
    }

    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _OUTPUTS_DIR / "error_clusters.json"
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)
    print(f"  Report written to: {report_path}")
    print()


if __name__ == "__main__":
    main()
