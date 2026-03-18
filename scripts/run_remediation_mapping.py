#!/usr/bin/env python3
"""
Remediation Mapping — scripts/run_remediation_mapping.py

Reads validated clusters (AW0 output), maps them through the AW1 Remediation
Mapping Engine, and emits a console summary plus a JSON output file.

Usage
-----
    python scripts/run_remediation_mapping.py --all
    python scripts/run_remediation_mapping.py --case CASE_ID

Outputs
-------
- Console summary: total / mapped / ambiguous / rejected counts, top
  remediation targets, top proposed actions by confidence.
- JSON: outputs/remediation_plans.json
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
    validate_clusters,
)
from spectrum_systems.modules.improvement.remediation_pipeline import (
    build_remediation_plans_from_validated_clusters,
    filter_mapped_plans,
    summarize_remediation_targets,
)
from spectrum_systems.modules.improvement.remediation_store import save_remediation_plan

_STORE_DIR = _ROOT / "data" / "error_classifications"
_REMEDIATION_STORE_DIR = _ROOT / "data" / "remediation_plans"
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
        description="Map validated clusters through the AW1 Remediation Mapping Engine."
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

    # Step 1: cluster (AV)
    clusters = build_clusters_from_classifications(records, catalog)

    # Step 2: validate (AW0)
    validated = validate_clusters(clusters, records)

    # Step 3: map (AW1)
    plans = build_remediation_plans_from_validated_clusters(
        validated_clusters=validated,
        classification_records=records,
        taxonomy_catalog=catalog,
    )

    summary = summarize_remediation_targets(plans)
    mapped_plans = filter_mapped_plans(plans, status="mapped")

    # ── Console Summary ────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("  REMEDIATION MAPPING REPORT (Prompt AW1)")
    print("=" * 62)
    if case_id:
        print(f"  Filter:           case_id = {case_id}")
    else:
        print("  Filter:           all records")
    print(f"  Input records:    {len(records)}")
    print(f"  Total clusters:   {len(validated)}")
    print(f"  Valid clusters:   {sum(1 for v in validated if v.validation_status == 'valid')}")
    print(f"  Total plans:      {summary['total_plans']}")
    print(f"  Mapped:           {summary['mapped']}")
    print(f"  Ambiguous:        {summary['ambiguous']}")
    print(f"  Rejected:         {summary['rejected']}")
    print(f"  Taxonomy:         {catalog.taxonomy_id} v{catalog.version}")
    print()

    if summary["top_remediation_targets"]:
        print("  TOP REMEDIATION TARGETS")
        _print_divider()
        for target, count in list(summary["top_remediation_targets"].items())[:10]:
            print(f"  {'':>3}{target:<45}  {count:>3} plan(s)")
        print()

    if summary["top_proposed_actions"]:
        print("  TOP PROPOSED ACTIONS (by confidence)")
        _print_divider()
        for action in summary["top_proposed_actions"][:10]:
            print(
                f"  {action['cluster_signature']:<30}"
                f"  {action['action_type']:<28}"
                f"  conf={action['confidence_score']:.2f}"
                f"  risk={action['risk_level']}"
            )
        print()

    # ── JSON Output ────────────────────────────────────────────────────────
    output = {
        "report_type": "remediation_mapping_report",
        "taxonomy_id": catalog.taxonomy_id,
        "taxonomy_version": catalog.version,
        "filters": {"case_id": case_id, "all": args.all},
        "summary": summary,
        "remediation_plans": [p.to_dict() for p in plans],
    }

    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _OUTPUTS_DIR / "remediation_plans.json"
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)
    print(f"  Report written to: {report_path}")
    print()

    # Save new mapped plans to the store
    saved = 0
    for plan in mapped_plans:
        dest = _REMEDIATION_STORE_DIR / f"{plan.remediation_id}.json"
        if not dest.exists():
            try:
                save_remediation_plan(plan, _REMEDIATION_STORE_DIR)
                saved += 1
            except FileExistsError:
                pass
    if saved:
        print(f"  Saved {saved} new mapped plan(s) to {_REMEDIATION_STORE_DIR}")
        print()


if __name__ == "__main__":
    main()
