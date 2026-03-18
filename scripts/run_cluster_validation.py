#!/usr/bin/env python3
"""
Cluster Validation — scripts/run_cluster_validation.py

Reads persisted error classification records (AU), clusters them (AV),
validates each cluster through the AW0 Cluster Validation Layer, and emits
a console summary plus a JSON output file.

Usage
-----
    python scripts/run_cluster_validation.py --all
    python scripts/run_cluster_validation.py --case CASE_ID

Outputs
-------
- Console summary: total / valid / invalid cluster counts and top invalidation
  reasons.
- JSON: outputs/validated_clusters.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# Ensure project root is on sys.path when run directly
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from spectrum_systems.modules.error_taxonomy.catalog import ErrorTaxonomyCatalog
from spectrum_systems.modules.error_taxonomy.classify import ErrorClassificationRecord
from spectrum_systems.modules.error_taxonomy.cluster_pipeline import (
    build_clusters_from_classifications,
    validate_clusters,
)
from spectrum_systems.modules.error_taxonomy.validated_cluster_store import (
    save_validated_cluster,
)

_STORE_DIR = _ROOT / "data" / "error_classifications"
_VALIDATED_STORE_DIR = _ROOT / "data" / "validated_clusters"
_OUTPUTS_DIR = _ROOT / "outputs"


def _load_records(
    all_records: bool,
    case_id: str | None,
) -> list[ErrorClassificationRecord]:
    records = ErrorClassificationRecord.list_all(_STORE_DIR)
    if case_id:
        records = [r for r in records if r.context.get("case_id") == case_id]
    return records


def _extract_invalidation_tags(validation_reasons: list[str]) -> list[str]:
    """Extract the short invalidation tag from each reason string."""
    tags = []
    for reason in validation_reasons:
        tag = reason.split(":")[0]
        # Only collect reasons that represent failures (known invalid tags)
        invalid_tags = {
            "too_small",
            "low_cohesion",
            "too_broad",
            "unstable_signature",
            "unclear_remediation",
            "low_confidence",
        }
        if tag in invalid_tags:
            tags.append(tag)
    return tags


def _print_divider(width: int = 60) -> None:
    print("  " + "─" * width)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate error clusters through the AW0 Cluster Validation Layer."
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

    # Step 1: build clusters (AV)
    clusters = build_clusters_from_classifications(records, catalog)

    # Step 2: validate clusters (AW0)
    validated = validate_clusters(clusters, records)

    valid_clusters = [v for v in validated if v.validation_status == "valid"]
    invalid_clusters = [v for v in validated if v.validation_status == "invalid"]

    # Collect top invalidation reasons
    reason_counter: Counter[str] = Counter()
    for v in invalid_clusters:
        for tag in _extract_invalidation_tags(v.validation_reasons):
            reason_counter[tag] += 1

    # ── Console Summary ────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("  CLUSTER VALIDATION REPORT (Prompt AW0)")
    print("=" * 62)
    if case_id:
        print(f"  Filter:           case_id = {case_id}")
    else:
        print("  Filter:           all records")
    print(f"  Input records:    {len(records)}")
    print(f"  Total clusters:   {len(validated)}")
    print(f"  Valid clusters:   {len(valid_clusters)}")
    print(f"  Invalid clusters: {len(invalid_clusters)}")
    print(f"  Taxonomy:         {catalog.taxonomy_id} v{catalog.version}")
    print()

    if reason_counter:
        print("  TOP INVALIDATION REASONS")
        _print_divider()
        for tag, count in reason_counter.most_common():
            print(f"  {'':>3}{tag:<35}  {count:>3} cluster(s)")
        print()

    if valid_clusters:
        print("  VALID CLUSTERS")
        _print_divider()
        for v in valid_clusters[:10]:
            print(
                f"  {v.cluster_signature:<35}"
                f"  n={v.record_count:>3}"
                f"  coh={v.cohesion_score:.2f}"
                f"  act={v.actionability_score:.2f}"
                f"  stab={v.stability_score:.2f}"
            )
        if len(valid_clusters) > 10:
            print(f"  … and {len(valid_clusters) - 10} more valid clusters")
        print()

    # ── JSON Output ────────────────────────────────────────────────────────
    output = {
        "report_type": "cluster_validation_report",
        "taxonomy_id": catalog.taxonomy_id,
        "taxonomy_version": catalog.version,
        "filters": {"case_id": case_id, "all": args.all},
        "summary": {
            "input_record_count": len(records),
            "total_clusters": len(validated),
            "valid_clusters": len(valid_clusters),
            "invalid_clusters": len(invalid_clusters),
            "top_invalidation_reasons": dict(reason_counter.most_common()),
        },
        "validated_clusters": [v.to_dict() for v in validated],
    }

    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _OUTPUTS_DIR / "validated_clusters.json"
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)
    print(f"  Report written to: {report_path}")
    print()

    # Optionally save valid clusters to the store
    saved = 0
    for v in valid_clusters:
        dest = _VALIDATED_STORE_DIR / f"{v.cluster_id}.json"
        if not dest.exists():
            save_validated_cluster(v, _VALIDATED_STORE_DIR)
            saved += 1
    if saved:
        print(f"  Saved {saved} new valid cluster(s) to {_VALIDATED_STORE_DIR}")
        print()


if __name__ == "__main__":
    main()
