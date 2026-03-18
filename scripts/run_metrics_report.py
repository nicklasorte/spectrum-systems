#!/usr/bin/env python3
"""
Metrics Report — scripts/run_metrics_report.py

Generates a structured observability report from stored ObservabilityRecords.

Usage
-----
    python scripts/run_metrics_report.py --all
    python scripts/run_metrics_report.py --case CASE_ID

Outputs
-------
- Console summary:
    - Worst performing passes
    - Top error types
    - Grounding failure rate
    - Human disagreement rate
- JSON report written to outputs/metrics_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on the path
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.observability.metrics import MetricsStore
from spectrum_systems.modules.observability.aggregation import (
    compute_error_distribution,
    compute_grounding_failure_rate,
    compute_human_disagreement,
    compute_latency_stats,
    compute_pass_metrics,
    compute_weakest_passes,
)

_DEFAULT_OUTPUT_PATH = _REPO_ROOT / "outputs" / "metrics_report.json"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report(
    store: MetricsStore,
    case_id: str | None = None,
) -> dict:
    """Load records and compute the full metrics report.

    Parameters
    ----------
    store:
        ``MetricsStore`` instance.
    case_id:
        Filter to a specific golden case.  When ``None``, all records are used.

    Returns
    -------
    dict
        Structured metrics report.
    """
    filters = {"case_id": case_id} if case_id else None
    records = store.list(filters=filters)

    if not records:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "case_id_filter": case_id,
            "record_count": 0,
            "message": "No observability records found for the given filter.",
        }

    pass_metrics = compute_pass_metrics(records)
    error_dist = compute_error_distribution(records)
    grounding = compute_grounding_failure_rate(records)
    disagreement = compute_human_disagreement(records)
    latency = compute_latency_stats(records)
    weakest = compute_weakest_passes(records)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_id_filter": case_id,
        "record_count": len(records),
        "pass_metrics": pass_metrics,
        "error_distribution": error_dist,
        "grounding_failure": grounding,
        "human_disagreement": disagreement,
        "latency_stats": latency,
        "weakest_passes": weakest,
    }


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------


def print_summary(report: dict) -> None:
    """Print a human-readable console summary of the metrics report."""
    n = report.get("record_count", 0)
    case_filter = report.get("case_id_filter")

    print()
    print("=" * 65)
    print("  OBSERVABILITY METRICS REPORT")
    print("=" * 65)
    if case_filter:
        print(f"  Case filter  : {case_filter}")
    print(f"  Records      : {n}")
    print(f"  Generated at : {report.get('generated_at', 'N/A')}")

    if n == 0:
        print()
        print(f"  {report.get('message', 'No data.')}")
        print()
        return

    # -- Grounding failure rate
    gf = report.get("grounding_failure", {})
    gf_rate = gf.get("overall_failure_rate")
    avg_gs = gf.get("avg_grounding_score")
    print()
    print("  GROUNDING")
    print(f"  Failure rate : {_pct(gf_rate)}")
    print(f"  Avg score    : {_fmt(avg_gs)}")

    # -- Human disagreement
    hd = report.get("human_disagreement", {})
    hd_rate = hd.get("overall_disagreement_rate")
    print()
    print("  HUMAN DISAGREEMENT")
    print(f"  Rate         : {_pct(hd_rate)}")

    # -- Top error types
    ed = report.get("error_distribution", {})
    top_error = ed.get("top_error_type")
    by_error = ed.get("by_error_type", {})
    total_errors = ed.get("total_error_count", 0)
    print()
    print("  ERROR DISTRIBUTION")
    print(f"  Total errors : {total_errors}")
    if top_error:
        print(f"  Top error    : {top_error}")
    if by_error:
        for et, count in sorted(by_error.items(), key=lambda x: -x[1]):
            print(f"    {et:<28} {count:>5}")

    # -- Worst performing passes
    weakest = report.get("weakest_passes", [])
    print()
    print("  WEAKEST PASSES (by failure rate)")
    if weakest:
        print(f"  {'Pass Type':<28} {'Failure Rate':>14} {'Struct Score':>14} {'Ground Score':>14}")
        print(f"  {'-' * 28} {'-' * 14} {'-' * 14} {'-' * 14}")
        for wp in weakest[:10]:
            print(
                f"  {wp['pass_type']:<28} "
                f"{_pct(wp['failure_rate']):>14} "
                f"{_fmt(wp['avg_structural_score']):>14} "
                f"{_fmt(wp['avg_grounding_score']):>14}"
            )
    else:
        print("  (no pass data)")

    # -- Latency
    lat = report.get("latency_stats", {})
    print()
    print("  LATENCY")
    print(f"  Mean         : {_ms(lat.get('mean_ms'))}")
    print(f"  p95          : {_ms(lat.get('p95_ms'))}")
    print(f"  Max          : {_ms(lat.get('max_ms'))}")

    print()
    print("=" * 65)
    print()


def _pct(v) -> str:
    if v is None:
        return "N/A"
    return f"{v * 100:.1f}%"


def _fmt(v) -> str:
    if v is None:
        return "N/A"
    return f"{v:.3f}"


def _ms(v) -> str:
    if v is None:
        return "N/A"
    return f"{v:.0f} ms"


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate observability metrics report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all",
        action="store_true",
        help="Generate report across all stored observability records.",
    )
    group.add_argument(
        "--case",
        metavar="CASE_ID",
        help="Generate report filtered to a specific golden case ID.",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=str(_DEFAULT_OUTPUT_PATH),
        help=f"Output JSON path (default: {_DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--store",
        metavar="DIR",
        default=None,
        help="Path to observability store directory (default: data/observability/).",
    )
    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    store_dir = Path(args.store) if args.store else None
    store = MetricsStore(store_dir=store_dir)

    case_id = args.case if not args.all else None
    report = generate_report(store, case_id=case_id)

    print_summary(report)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"  JSON report written to: {output_path}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
