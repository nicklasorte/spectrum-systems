#!/usr/bin/env python3
"""
Error Taxonomy Report — scripts/run_error_taxonomy_report.py

Reads persisted error classification records and produces a summary report
showing top error families, subtypes, source systems, and remediation targets.

Usage
-----
    python scripts/run_error_taxonomy_report.py --all
    python scripts/run_error_taxonomy_report.py --case CASE_ID
    python scripts/run_error_taxonomy_report.py --artifact ARTIFACT_ID

Outputs
-------
- Console summary (top families, subtypes, source system breakdown)
- JSON report: outputs/error_taxonomy_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on the path when run directly
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from spectrum_systems.modules.error_taxonomy.catalog import ErrorTaxonomyCatalog
from spectrum_systems.modules.error_taxonomy.classify import ErrorClassificationRecord
from spectrum_systems.modules.error_taxonomy.aggregation import (
    count_by_family,
    count_by_subtype,
    count_by_remediation_target,
    count_by_source_system,
    count_by_pass_type,
    identify_highest_impact_subtypes,
)

_OUTPUTS_DIR = _ROOT / "outputs"
_STORE_DIR = _ROOT / "data" / "error_classifications"


def _load_records(
    all_records: bool,
    case_id: str | None,
    artifact_id: str | None,
) -> list[ErrorClassificationRecord]:
    """Load and filter classification records."""
    records = ErrorClassificationRecord.list_all(_STORE_DIR)

    if case_id:
        records = [r for r in records if r.context.get("case_id") == case_id]

    if artifact_id:
        records = [r for r in records if r.context.get("artifact_id") == artifact_id]

    return records


def _avg_confidence(records: list[ErrorClassificationRecord]) -> float:
    """Compute average confidence across all classification entries."""
    all_confidences = [
        entry["confidence"]
        for rec in records
        for entry in rec.classifications
    ]
    if not all_confidences:
        return 0.0
    return sum(all_confidences) / len(all_confidences)


def _print_section(title: str, data: dict[str, int], top_n: int = 10) -> None:
    """Print a ranked section of the report."""
    print(f"\n  {title}")
    print(f"  {'─' * 40}")
    items = list(data.items())[:top_n]
    if not items:
        print("  (no data)")
        return
    for rank, (key, count) in enumerate(items, 1):
        print(f"  {rank:>3}. {key:<40} {count:>5}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate error taxonomy report from classification records."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all", action="store_true", help="Include all classification records."
    )
    group.add_argument(
        "--case", metavar="CASE_ID", help="Filter to a specific case ID."
    )
    group.add_argument(
        "--artifact", metavar="ARTIFACT_ID", help="Filter to a specific artifact ID."
    )
    args = parser.parse_args()

    case_id = args.case if args.case else None
    artifact_id = args.artifact if args.artifact else None

    # Load records
    records = _load_records(
        all_records=args.all,
        case_id=case_id,
        artifact_id=artifact_id,
    )

    if not records:
        filter_desc = ""
        if case_id:
            filter_desc = f" for case '{case_id}'"
        elif artifact_id:
            filter_desc = f" for artifact '{artifact_id}'"
        print(f"No classification records found{filter_desc}.")
        sys.exit(0)

    # Load catalog for enrichment
    catalog = ErrorTaxonomyCatalog.load_catalog()

    # Compute aggregations
    by_family = count_by_family(records)
    by_subtype = count_by_subtype(records)
    by_source = count_by_source_system(records)
    by_pass = count_by_pass_type(records)
    by_remediation = count_by_remediation_target(records, catalog)
    top_subtypes = identify_highest_impact_subtypes(records, catalog, top_n=10)
    avg_conf = _avg_confidence(records)
    total_classifications = sum(len(r.classifications) for r in records)

    # Print console summary
    print()
    print("=" * 55)
    print("  ERROR TAXONOMY REPORT")
    print("=" * 55)
    if case_id:
        print(f"  Filter: case_id = {case_id}")
    elif artifact_id:
        print(f"  Filter: artifact_id = {artifact_id}")
    else:
        print("  Filter: all records")
    print(f"  Records:         {len(records)}")
    print(f"  Classifications: {total_classifications}")
    print(f"  Avg Confidence:  {avg_conf:.2f}")
    print(f"  Taxonomy:        {catalog.taxonomy_id} v{catalog.version}")

    _print_section("Top Error Families", by_family)
    _print_section("Top Error Subtypes", by_subtype)
    _print_section("By Source System", by_source)
    _print_section("By Remediation Target", by_remediation)
    if any(p != "unknown" for p in by_pass):
        _print_section("By Pass Type", by_pass)

    print("\n  Highest-Impact Subtypes (count × severity)")
    print(f"  {'─' * 60}")
    for item in top_subtypes:
        print(
            f"  {item['error_code']:<40}"
            f"  cnt={item['count']:>3}"
            f"  sev={item['default_severity']:<8}"
            f"  impact={item['impact_score']:>4}"
        )

    print()

    # Build JSON report
    report = {
        "report_type": "error_taxonomy_report",
        "taxonomy_id": catalog.taxonomy_id,
        "taxonomy_version": catalog.version,
        "filters": {
            "case_id": case_id,
            "artifact_id": artifact_id,
            "all": args.all,
        },
        "summary": {
            "record_count": len(records),
            "total_classifications": total_classifications,
            "avg_confidence": round(avg_conf, 4),
        },
        "counts_by_family": by_family,
        "counts_by_subtype": by_subtype,
        "counts_by_source_system": by_source,
        "counts_by_remediation_target": by_remediation,
        "counts_by_pass_type": by_pass,
        "highest_impact_subtypes": top_subtypes,
    }

    # Write JSON report
    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _OUTPUTS_DIR / "error_taxonomy_report.json"
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"  Report written to: {report_path}")
    print()


if __name__ == "__main__":
    main()
