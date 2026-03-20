#!/usr/bin/env python3
"""CLI for the BR — Replay Regression Harness.

Executes a governed regression suite against persisted traces and emits a
schema-validated regression_run_result artifact.

Exit codes
----------
0   pass     – all traces in the suite passed
1   fail     – one or more trace regressions failed
2   error    – invalid suite, missing trace, schema validation failure,
               or any other hard runtime failure

Usage
-----
    python scripts/run_regression_suite.py --suite path/to/suite.json

Examples
--------
    python scripts/run_regression_suite.py --suite tests/fixtures/regression/sample_suite.json
    python scripts/run_regression_suite.py \\
        --suite tests/fixtures/regression/sample_suite.json \\
        --output outputs/regression_run_result.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.regression_harness import (  # noqa: E402
    InvalidSuiteError,
    MissingTraceError,
    RegressionHarnessError,
    run_regression_suite,
)

# ---------------------------------------------------------------------------
# Exit code constants
# ---------------------------------------------------------------------------

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 2

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_OUTPUT_DIR = _REPO_ROOT / "outputs"
_DEFAULT_OUTPUT = "regression_run_result.json"


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
    """Entry point for the Replay Regression Harness CLI.

    Returns the exit code (0=pass, 1=fail, 2=error).
    """
    parser = argparse.ArgumentParser(
        description=(
            "Execute a governed regression suite against persisted traces and "
            "emit a schema-validated regression_run_result artifact."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--suite",
        required=True,
        help="Path to the regression suite manifest JSON file.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            f"Path to write the regression_run_result artifact JSON. "
            f"Defaults to outputs/{_DEFAULT_OUTPUT}."
        ),
    )

    args = parser.parse_args(argv)

    output_path = (
        Path(args.output) if args.output else _OUTPUT_DIR / _DEFAULT_OUTPUT
    )

    # --- Execute regression suite ---
    try:
        run_result = run_regression_suite(args.suite)
    except InvalidSuiteError as exc:
        print(f"ERROR: invalid suite '{args.suite}': {exc}", file=sys.stderr)
        return EXIT_ERROR
    except MissingTraceError as exc:
        print(f"ERROR: missing trace: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except RegressionHarnessError as exc:
        print(f"ERROR: regression harness failure: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: unexpected failure ({type(exc).__name__}): {exc}", file=sys.stderr)
        return EXIT_ERROR

    # --- Write result ---
    try:
        _write_json(run_result, output_path)
    except OSError as exc:
        print(
            f"ERROR: failed to write regression run result to '{output_path}': {exc}",
            file=sys.stderr,
        )
        return EXIT_ERROR

    # --- Report outcome ---
    overall = run_result.get("overall_status", "fail")
    total = run_result.get("total_traces", 0)
    passed = run_result.get("passed_traces", 0)
    failed = run_result.get("failed_traces", 0)
    pass_rate = run_result.get("pass_rate", 0.0)
    summary = run_result.get("summary", {})
    avg_score = summary.get("average_reproducibility_score", 0.0)
    drift_counts = summary.get("drift_counts", {})

    print(
        f"Regression suite result: {overall.upper()}\n"
        f"  Suite ID:                {run_result.get('suite_id')}\n"
        f"  Run ID:                  {run_result.get('run_id')}\n"
        f"  Total traces:            {total}\n"
        f"  Passed:                  {passed}\n"
        f"  Failed:                  {failed}\n"
        f"  Pass rate:               {pass_rate:.1%}\n"
        f"  Avg reproducibility:     {avg_score:.3f}\n"
        f"  Drift counts:            {drift_counts}"
    )

    if overall == "fail":
        print("\nFailed traces:")
        for r in run_result.get("results", []):
            if not r.get("passed"):
                reasons = "; ".join(r.get("failure_reasons", []))
                print(
                    f"  [FAIL] trace_id={r['trace_id']} "
                    f"analysis_id={r['analysis_id']} "
                    f"decision_status={r['decision_status']} "
                    f"reproducibility_score={r['reproducibility_score']:.3f} "
                    f"drift_type={r['drift_type'] or 'none'} "
                    f"reasons: {reasons}"
                )
        return EXIT_FAIL

    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
