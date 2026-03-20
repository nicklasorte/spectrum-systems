#!/usr/bin/env python3
"""CLI for the BS — Continuous Evaluation Monitor.

Ingests one or more regression_run_result artifacts, computes monitoring
records and an aggregated summary, and emits schema-validated artifacts.

Exit codes
----------
0   healthy    – no critical recommendation, no degrading trend
1   warning    – warning or degrading state detected
2   error      – invalid input, schema failure, or critical / exhausting burn-rate state

Usage
-----
    python scripts/run_evaluation_monitor.py \\
        --input path/to/regression_run_result.json \\
        [--input path/to/another.json ...] \\
        --output-dir path/to/output/

Examples
--------
    python scripts/run_evaluation_monitor.py \\
        --input tests/fixtures/evaluation_monitor/healthy_run_1.json \\
        --input tests/fixtures/evaluation_monitor/healthy_run_2.json \\
        --output-dir outputs/evaluation_monitor/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.evaluation_monitor import (  # noqa: E402
    EvaluationMonitorError,
    InvalidRegressionResultError,
    run_evaluation_monitor,
)

# ---------------------------------------------------------------------------
# Exit code constants
# ---------------------------------------------------------------------------

EXIT_HEALTHY = 0
EXIT_WARNING = 1
EXIT_ERROR = 2

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_OUTPUT_DIR = _REPO_ROOT / "outputs" / "evaluation_monitor"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(artifact: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(artifact, fh, indent=2)
    print(f"Written: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the Continuous Evaluation Monitor CLI.

    Returns the exit code (0=healthy, 1=warning, 2=error).
    """
    parser = argparse.ArgumentParser(
        description=(
            "Ingest regression_run_result artifacts and emit governed "
            "evaluation_monitor_record and evaluation_monitor_summary artifacts."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input",
        dest="inputs",
        action="append",
        required=True,
        metavar="PATH",
        help=(
            "Path to a regression_run_result JSON file. "
            "May be repeated to ingest multiple runs."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="DIR",
        help=(
            f"Directory to write output artifacts. "
            f"Defaults to {_DEFAULT_OUTPUT_DIR}."
        ),
    )

    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir) if args.output_dir else _DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Execute monitor ---
    try:
        records, summary = run_evaluation_monitor(args.inputs)
    except InvalidRegressionResultError as exc:
        print(f"ERROR: invalid regression_run_result: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except EvaluationMonitorError as exc:
        print(f"ERROR: evaluation monitor failure: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:  # noqa: BLE001
        print(
            f"ERROR: unexpected failure ({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        return EXIT_ERROR

    # --- Write per-input monitor records ---
    for i, record in enumerate(records):
        record_filename = f"evaluation_monitor_record_{i + 1}.json"
        record_path = output_dir / record_filename
        try:
            _write_json(record, record_path)
        except OSError as exc:
            print(
                f"ERROR: failed to write monitor record to '{record_path}': {exc}",
                file=sys.stderr,
            )
            return EXIT_ERROR

    # --- Write summary ---
    summary_path = output_dir / "evaluation_monitor_summary.json"
    try:
        _write_json(summary, summary_path)
    except OSError as exc:
        print(
            f"ERROR: failed to write monitor summary to '{summary_path}': {exc}",
            file=sys.stderr,
        )
        return EXIT_ERROR

    # --- Print console summary ---
    agg = summary["aggregates"]
    trend = summary["trend_analysis"]
    burn = summary["burn_rate_assessment"]
    recommended = summary["recommended_action"]

    print(
        f"\nEvaluation Monitor Summary\n"
        f"  Summary ID:              {summary['summary_id']}\n"
        f"  Total runs:              {summary['window']['total_runs']}\n"
        f"  Avg pass rate:           {agg['average_pass_rate']:.1%}\n"
        f"  Avg drift rate:          {agg['average_drift_rate']:.1%}\n"
        f"  Avg reproducibility:     {agg['average_reproducibility_score']:.3f}\n"
        f"  Total failed runs:       {agg['total_failed_runs']}\n"
        f"  Total critical alerts:   {agg['total_critical_alerts']}\n"
        f"  Pass rate trend:         {trend['pass_rate_trend']}\n"
        f"  Drift rate trend:        {trend['drift_rate_trend']}\n"
        f"  Reproducibility trend:   {trend['reproducibility_trend']}\n"
        f"  Burn rate status:        {burn['status']}\n"
        f"  Recommended action:      {recommended}"
    )

    if burn["reasons"]:
        print("  Burn rate reasons:")
        for r in burn["reasons"]:
            print(f"    - {r}")

    # --- Determine exit code ---
    if (
        recommended in ("rollback_candidate",)
        or agg["total_critical_alerts"] > 0
        or burn["status"] == "exhausting"
    ):
        print(
            f"\nExit 2: critical recommendation or exhausting burn rate "
            f"(recommended_action={recommended}, "
            f"critical_alerts={agg['total_critical_alerts']}, "
            f"burn_rate={burn['status']})",
            file=sys.stderr,
        )
        return EXIT_ERROR

    if (
        recommended in ("watch", "freeze_changes")
        or trend["pass_rate_trend"] == "degrading"
        or agg["total_failed_runs"] > 0
    ):
        print(
            f"\nExit 1: warning or degrading state detected "
            f"(recommended_action={recommended}, "
            f"pass_rate_trend={trend['pass_rate_trend']}, "
            f"failed_runs={agg['total_failed_runs']})",
            file=sys.stderr,
        )
        return EXIT_WARNING

    return EXIT_HEALTHY


if __name__ == "__main__":
    sys.exit(main())
