#!/usr/bin/env python3
"""
Fix Simulation Sandbox — scripts/run_fix_simulation.py

Reads AW1 remediation plans, simulates mapped plans through the AW2 Fix
Simulation Sandbox, and emits a console summary plus a JSON output file.

Usage
-----
    python scripts/run_fix_simulation.py --all
    python scripts/run_fix_simulation.py --remediation REMEDIATION_ID
    python scripts/run_fix_simulation.py --strict

Options
-------
--all               Simulate all mapped remediation plans.
--remediation ID    Simulate a single plan by remediation_id.
--strict            Exit code 2 if any hard regression failure is detected.

Outputs
-------
- Console summary: total / passed / failed / inconclusive / rejected counts,
  promotion recommendations, top targeted improvements, top regressions.
- JSON: outputs/simulation_results.json

Exit codes
----------
0   All simulated plans are promote/hold and no hard failures.
2   Any hard regression failure occurred.
3   No simulations could be meaningfully run (all rejected/inconclusive with 0 cases).
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

from spectrum_systems.modules.improvement.remediation_store import list_remediation_plans, load_remediation_plan
from spectrum_systems.modules.improvement.simulation_pipeline import (
    run_simulation_batch,
    summarize_simulation_outcomes,
)
from spectrum_systems.modules.improvement.simulation_store import save_simulation_result

_REMEDIATION_STORE_DIR = _ROOT / "data" / "remediation_plans"
_OUTPUTS_DIR = _ROOT / "outputs"
_GOLDEN_CASES_DIR = _ROOT / "data" / "golden_cases"


def _load_golden_cases() -> list[dict[str, Any]]:
    """Load golden cases from data/golden_cases/ directory."""
    cases = []
    if _GOLDEN_CASES_DIR.exists():
        for p in sorted(_GOLDEN_CASES_DIR.glob("*.json")):
            try:
                with open(p, encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, list):
                    cases.extend(data)
                elif isinstance(data, dict) and "case_id" in data:
                    cases.append(data)
            except (json.JSONDecodeError, OSError):
                pass
    return cases


def _print_divider(width: int = 60) -> None:
    print("  " + "─" * width)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate AW1 remediation plans through the AW2 Fix Simulation Sandbox."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all", action="store_true", help="Simulate all mapped remediation plans."
    )
    group.add_argument(
        "--remediation",
        metavar="REMEDIATION_ID",
        help="Simulate a single plan by remediation_id.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 2 if any hard regression failure is detected.",
    )
    args = parser.parse_args()

    # ── Load remediation plans ─────────────────────────────────────────────
    if args.remediation:
        try:
            plan = load_remediation_plan(args.remediation, _REMEDIATION_STORE_DIR)
            plans = [plan]
        except FileNotFoundError as exc:
            print(f"Error: {exc}")
            sys.exit(3)
    else:
        plans = list_remediation_plans(_REMEDIATION_STORE_DIR)

    if not plans:
        print("No remediation plans found.")
        sys.exit(3)

    # Only simulate mapped plans; others are handled by the simulator (rejected)
    # We pass all plans and let the simulator gate them
    golden_cases = _load_golden_cases()

    # ── Run simulation ─────────────────────────────────────────────────────
    results = run_simulation_batch(plans, golden_dataset=golden_cases)

    if not results:
        print("No simulation results produced.")
        sys.exit(3)

    summary = summarize_simulation_outcomes(results)

    # ── Console Summary ────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("  FIX SIMULATION SANDBOX REPORT (Prompt AW2 / AR Hard Gating AZ)")
    print("=" * 62)
    if args.remediation:
        print(f"  Filter:              remediation_id = {args.remediation}")
    else:
        print("  Filter:              all plans")
    print(f"  Total plans considered: {len(plans)}")
    print(f"  Total simulations:      {summary['total_results']}")
    print()

    by_status = summary["by_status"]
    print("  SIMULATION OUTCOMES")
    _print_divider()
    print(f"  {'Passed':<20}  {by_status.get('passed', 0):>5}")
    print(f"  {'Failed':<20}  {by_status.get('failed', 0):>5}")
    print(f"  {'Inconclusive':<20}  {by_status.get('inconclusive', 0):>5}")
    print(f"  {'Rejected':<20}  {by_status.get('rejected', 0):>5}")
    print()

    by_rec = summary["by_recommendation"]
    promote_count = by_rec.get("promote", 0)
    hold_count = by_rec.get("hold", 0)
    reject_count = by_rec.get("reject", 0)
    print("  PROMOTION RECOMMENDATIONS (AR Hard Gating)")
    _print_divider()
    print(f"  {'Promote':<20}  {promote_count:>5}")
    print(f"  {'Hold':<20}  {hold_count:>5}")
    print(f"  {'Reject':<20}  {reject_count:>5}")
    print()

    # Gating reason breakdown
    gating_reason_counts: dict[str, int] = {}
    gating_flag_counts: dict[str, int] = {}
    for r in results:
        reason = getattr(r, "gating_decision_reason", "")
        if reason:
            gating_reason_counts[reason] = gating_reason_counts.get(reason, 0) + 1
        for flag in getattr(r, "gating_flags", []):
            gating_flag_counts[flag] = gating_flag_counts.get(flag, 0) + 1

    if gating_reason_counts:
        print("  TOP GATING REASONS")
        _print_divider()
        for reason, count in sorted(gating_reason_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  {reason:<40}  {count:>5}")
        print()

    if summary["top_targeted_improvements"]:
        print("  TOP TARGETED IMPROVEMENTS")
        _print_divider()
        for item in summary["top_targeted_improvements"][:10]:
            print(
                f"  {item['target_component']:<35}  "
                f"{item['target_metric']:<20}  "
                f"delta={item['delta']:+.4f}"
            )
        print()

    if summary["top_regressions_detected"]:
        print("  TOP REGRESSIONS DETECTED")
        _print_divider()
        for item in summary["top_regressions_detected"][:10]:
            print(
                f"  {item['remediation_id']:<40}  "
                f"hard={item['hard_failures']}  "
                f"warn={item['warnings']}"
            )
        print()

    # ── JSON Output ────────────────────────────────────────────────────────
    output = {
        "report_type": "fix_simulation_report",
        "filters": {
            "remediation_id": args.remediation,
            "all": args.all,
        },
        "summary": summary,
        "gating_breakdown": {
            "total_plans": len(plans),
            "promote_count": promote_count,
            "hold_count": hold_count,
            "reject_count": reject_count,
            "top_gating_reasons": sorted(
                [{"reason": r, "count": c} for r, c in gating_reason_counts.items()],
                key=lambda x: -x["count"],
            )[:10],
        },
        "simulation_results": [r.to_dict() for r in results],
    }

    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _OUTPUTS_DIR / "simulation_results.json"
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)
    print(f"  Report written to: {report_path}")
    print()

    # Save new simulation results to the store
    saved = 0
    sim_store_dir = _ROOT / "data" / "simulation_results"
    for result in results:
        dest = sim_store_dir / f"{result.simulation_id}.json"
        if not dest.exists():
            try:
                save_simulation_result(result, sim_store_dir)
                saved += 1
            except FileExistsError:
                pass
    if saved:
        print(f"  Saved {saved} new simulation result(s) to {sim_store_dir}")
        print()

    # ── Exit codes ─────────────────────────────────────────────────────────
    has_hard_failures = any(
        r.regression_check.get("hard_failures", 0) > 0 for r in results
    )
    all_inconclusive_or_rejected = all(
        r.simulation_status in ("inconclusive", "rejected") for r in results
    )

    if all_inconclusive_or_rejected:
        sys.exit(3)

    if args.strict and has_hard_failures:
        sys.exit(2)

    if has_hard_failures and not args.strict:
        # Non-strict mode: report but exit 0
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
