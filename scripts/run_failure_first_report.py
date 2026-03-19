#!/usr/bin/env python3
"""
Failure-First Report — scripts/run_failure_first_report.py

Generates a failure-first observability report that surfaces the most
dangerous failures first, rather than averaging behaviour across all records.

Usage
-----
    python scripts/run_failure_first_report.py --all
    python scripts/run_failure_first_report.py --case CASE_ID

Outputs
-------
- Console summary (failure-first order):
    1. Executive failure summary
    2. Worst cases (top 5)
    3. Top failure modes
    4. Passes / components most at risk
    5. False-confidence zones
    6. Structural health
- JSON report written to outputs/failure_first_report.json
- Derived summary persisted under data/observability_reports/
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
    compute_failure_first_metrics,
)
from spectrum_systems.modules.observability.failure_ranking import (
    rank_dangerous_promotes,
    rank_failure_modes,
    rank_pass_weaknesses,
    rank_worst_cases,
)

_DEFAULT_OUTPUT_PATH = _REPO_ROOT / "outputs" / "failure_first_report.json"
_REPORTS_DIR = _REPO_ROOT / "data" / "observability_reports"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_failure_first_report(
    store: MetricsStore,
    case_id: str | None = None,
) -> dict:
    """Build the failure-first report dict.

    Parameters
    ----------
    store:
        ``MetricsStore`` instance.
    case_id:
        Filter to a specific golden case.  When ``None``, all records used.

    Returns
    -------
    dict
        Structured failure-first report.
    """
    filters = {"case_id": case_id} if case_id else None
    records = store.list(filters=filters)

    generated_at = datetime.now(timezone.utc).isoformat()

    if not records:
        return {
            "generated_at": generated_at,
            "case_id_filter": case_id,
            "record_count": 0,
            "message": "No observability records found for the given filter.",
        }

    ff_metrics = compute_failure_first_metrics(records)
    worst_cases = rank_worst_cases(records, top_n=5)
    top_failure_modes = rank_failure_modes(records, top_n=10)
    dangerous_promotes = rank_dangerous_promotes(records, top_n=10)
    pass_weaknesses = rank_pass_weaknesses(records, top_n=10)

    # Structural health distribution
    structural_scores = [r.structural_score for r in records]
    structural_score_distribution = {
        "min": min(structural_scores),
        "max": max(structural_scores),
        "mean": sum(structural_scores) / len(structural_scores),
        "below_0_5": sum(1 for s in structural_scores if s < 0.5),
        "below_0_7": sum(1 for s in structural_scores if s < 0.7),
    }

    # False-confidence zones: high-confidence errors grouped by pass_type
    false_confidence_zones: dict = {}
    for r in records:
        from spectrum_systems.modules.observability.failure_ranking import (
            detect_high_confidence_error,
        )
        if detect_high_confidence_error(r):
            false_confidence_zones[r.pass_type] = (
                false_confidence_zones.get(r.pass_type, 0) + 1
            )
    false_confidence_zones = dict(
        sorted(false_confidence_zones.items(), key=lambda x: x[1], reverse=True)
    )

    report = {
        "generated_at": generated_at,
        "case_id_filter": case_id,
        "record_count": len(records),
        # 1. Executive failure summary
        "executive_failure_summary": {
            "total_cases": ff_metrics["record_count"],
            "rejection_rate": ff_metrics["rejection_rate"],
            "promote_rate": ff_metrics["promote_rate"],
            "dangerous_promotes": ff_metrics["dangerous_promote_count"],
            "high_confidence_errors": int(
                round((ff_metrics["high_confidence_error_rate"] or 0.0) * len(records))
            ),
            "structural_failure_rate": ff_metrics["structural_failure_rate"],
            "inconsistent_grounding_rate": ff_metrics["inconsistent_grounding_rate"],
        },
        # 2. Worst cases
        "worst_cases": worst_cases,
        # 3. Top failure modes
        "top_failure_modes": top_failure_modes,
        # 4. Passes / components most at risk
        "passes_most_at_risk": pass_weaknesses,
        # 5. False-confidence zones
        "false_confidence_zones": false_confidence_zones,
        # 6. Structural health
        "structural_health": {
            "structural_score_distribution": structural_score_distribution,
            "structural_failure_count": int(
                round((ff_metrics.get("structural_failure_rate") or 0.0) * len(records))
            ),
        },
        # Full BB metrics
        "failure_first_metrics": ff_metrics,
        # Dangerous promotes detail
        "dangerous_promotes_detail": dangerous_promotes,
    }

    return report


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------


def print_failure_first_summary(report: dict) -> None:
    """Print a human-readable failure-first console summary."""
    n = report.get("record_count", 0)
    case_filter = report.get("case_id_filter")

    print()
    print("=" * 70)
    print("  BB — FAILURE-FIRST OBSERVABILITY REPORT")
    print("=" * 70)
    if case_filter:
        print(f"  Case filter  : {case_filter}")
    print(f"  Records      : {n}")
    print(f"  Generated at : {report.get('generated_at', 'N/A')}")

    if n == 0:
        print()
        print(f"  {report.get('message', 'No data.')}")
        print()
        return

    # 1. Executive failure summary
    efs = report.get("executive_failure_summary", {})
    print()
    print("  1. EXECUTIVE FAILURE SUMMARY")
    print(f"  Total cases            : {efs.get('total_cases', n)}")
    print(f"  Promotion rate         : {_pct(efs.get('promote_rate'))}")
    print(f"  Rejection rate         : {_pct(efs.get('rejection_rate'))}")
    print(f"  Dangerous promotes     : {efs.get('dangerous_promotes', 0)}")
    print(f"  High-confidence errors : {efs.get('high_confidence_errors', 0)}")
    print(f"  Structural failure rate: {_pct(efs.get('structural_failure_rate'))}")
    print(f"  Grounding failure rate : {_pct(efs.get('inconsistent_grounding_rate'))}")

    # 2. Worst cases
    worst = report.get("worst_cases", [])
    print()
    print("  2. WORST CASES (top 5)")
    if worst:
        for i, wc in enumerate(worst, 1):
            dp_flag = " ⚠ DANGEROUS PROMOTE" if wc.get("is_dangerous_promote") else ""
            hce_flag = " ⚠ HIGH-CONF ERROR" if wc.get("is_high_confidence_error") else ""
            print(
                f"  [{i}] {wc.get('artifact_id', 'N/A')} "
                f"(pass={wc.get('pass_type', 'N/A')}, "
                f"failures={wc.get('failure_count', 0)})"
                f"{dp_flag}{hce_flag}"
            )
            if wc.get("dangerous_promote_reason"):
                print(f"      → {wc['dangerous_promote_reason']}")
            if wc.get("error_types"):
                print(f"      errors: {', '.join(wc['error_types'])}")
    else:
        print("  (none)")

    # 3. Top failure modes
    modes = report.get("top_failure_modes", [])
    print()
    print("  3. TOP FAILURE MODES")
    if modes:
        for fm in modes[:5]:
            print(f"  {fm['failure_mode']:<35} {fm['count']:>5}  "
                  f"passes: {', '.join(fm.get('affected_pass_types', []))}")
    else:
        print("  (none)")

    # 4. Passes most at risk
    risks = report.get("passes_most_at_risk", [])
    print()
    print("  4. PASSES / COMPONENTS MOST AT RISK")
    if risks:
        print(f"  {'Pass Type':<28} {'Fail Rate':>10} {'DngProm':>10} {'HCE':>10}")
        print(f"  {'-'*28} {'-'*10} {'-'*10} {'-'*10}")
        for r in risks[:5]:
            print(
                f"  {r['pass_type']:<28} "
                f"{_pct(r['failure_rate']):>10} "
                f"{_pct(r['dangerous_promote_rate']):>10} "
                f"{_pct(r['high_confidence_error_rate']):>10}"
            )
    else:
        print("  (none)")

    # 5. False-confidence zones
    fcz = report.get("false_confidence_zones", {})
    print()
    print("  5. FALSE-CONFIDENCE ZONES")
    if fcz:
        for pt, cnt in list(fcz.items())[:5]:
            print(f"  {pt:<28} {cnt:>5} high-confidence error(s)")
    else:
        print("  (none — system confidence aligns with outcomes)")

    # 6. Structural health
    sh = report.get("structural_health", {})
    ssd = sh.get("structural_score_distribution", {})
    print()
    print("  6. STRUCTURAL HEALTH")
    print(f"  Mean structural score  : {_fmt(ssd.get('mean'))}")
    print(f"  Below 0.5 (failures)   : {ssd.get('below_0_5', 0)}")
    print(f"  Below 0.7 (weak)       : {ssd.get('below_0_7', 0)}")

    print()
    print("=" * 70)
    print()

    # Final summary line (required by spec)
    ff = report.get("failure_first_metrics", {})
    dp_count = ff.get("dangerous_promote_count", 0)
    hce_count = int(round((ff.get("high_confidence_error_rate") or 0.0) * n))
    top3_modes = ff.get("repeated_failure_concentration", [])[:3]
    worst3 = report.get("worst_cases", [])[:3]
    risks3 = report.get("passes_most_at_risk", [])[:3]

    print("  SUMMARY")
    print(f"  dangerous_promote_count    : {dp_count}")
    print(f"  high_confidence_error_count: {hce_count}")
    print("  top_3_failure_modes        :")
    for fm in top3_modes:
        print(f"    - {fm['failure_mode']} ({fm['count']})")
    print("  top_3_worst_cases          :")
    for wc in worst3:
        print(f"    - {wc.get('artifact_id', 'N/A')} [{wc.get('pass_type', '?')}]")
    print("  top_3_weakest_components   :")
    for rk in risks3:
        print(f"    - {rk['pass_type']} (fail_rate={_pct(rk['failure_rate'])})")
    print()


def _pct(v) -> str:
    if v is None:
        return "N/A"
    return f"{v * 100:.1f}%"


def _fmt(v) -> str:
    if v is None:
        return "N/A"
    return f"{v:.3f}"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _save_derived_summary(report: dict) -> Path:
    """Persist derived summary to data/observability_reports/.

    Uses a timestamped filename to avoid silent overwrites.

    Parameters
    ----------
    report:
        The full report dict.

    Returns
    -------
    Path
        Path to the saved file.
    """
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = _REPORTS_DIR / f"failure_first_report_{ts}.json"
    filename.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return filename


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate failure-first observability report (BB).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all",
        action="store_true",
        help="Report across all stored observability records.",
    )
    group.add_argument(
        "--case",
        metavar="CASE_ID",
        help="Report filtered to a specific golden case ID.",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=str(_DEFAULT_OUTPUT_PATH),
        help=f"Primary JSON output path (default: {_DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--store",
        metavar="DIR",
        default=None,
        help="Path to observability store directory (default: data/observability/).",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Skip persisting derived summary to data/observability_reports/.",
    )
    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    store_dir = Path(args.store) if args.store else None
    store = MetricsStore(store_dir=store_dir)

    case_id = args.case if not args.all else None
    report = generate_failure_first_report(store, case_id=case_id)

    print_failure_first_summary(report)

    # Write primary output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"  JSON report written to: {output_path}")

    # Persist derived summary
    if not args.no_persist and report.get("record_count", 0) > 0:
        summary_path = _save_derived_summary(report)
        print(f"  Derived summary persisted: {summary_path}")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
