#!/usr/bin/env python3
"""CLI for the BQ — Replay Decision Integrity Engine.

Evaluates whether a replayed execution reproduces the same SLO decision and
enforcement outcome as the original run.  Establishes decision reproducibility
and enables drift detection.

Exit codes
----------
0   consistent   – replay decision matches original
1   drift        – replay decision differs from original (drift detected)
2   failure      – missing decision, replay failure, schema validation error,
                   or any other hard failure

Usage
-----
    python scripts/run_replay_decision_analysis.py --trace-id <TRACE_ID>

Examples
--------
    python scripts/run_replay_decision_analysis.py --trace-id trace-abc123
    python scripts/run_replay_decision_analysis.py --trace-id trace-abc123 \\
        --replay-output outputs/replay_result.json \\
        --analysis-output outputs/replay_decision_analysis.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.replay_decision_engine import (  # noqa: E402
    CONSISTENCY_CONSISTENT,
    CONSISTENCY_DRIFTED,
    ReplayDecisionError,
    run_replay_decision_analysis,
)
from spectrum_systems.modules.runtime.replay_engine import (  # noqa: E402
    ReplayEngineError,
    ReplayPrerequisiteError,
    execute_replay,
)

# ---------------------------------------------------------------------------
# Exit code constants
# ---------------------------------------------------------------------------

EXIT_CONSISTENT: int = 0
EXIT_DRIFT: int = 1
EXIT_FAILURE: int = 2

_OUTPUT_DIR = _REPO_ROOT / "outputs"
_DEFAULT_REPLAY_OUTPUT: str = "replay_result.json"
_DEFAULT_ANALYSIS_OUTPUT: str = "replay_decision_analysis.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(data: Dict[str, Any], path: Path) -> None:
    """Write *data* as formatted JSON to *path*, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _print_summary(analysis: Dict[str, Any]) -> None:
    """Print a human-readable summary of the decision analysis to stdout."""
    consistency = analysis.get("decision_consistency") or {}
    status = consistency.get("status", "(unknown)")
    drift_type = analysis.get("drift_type")
    score = analysis.get("reproducibility_score")
    score_str = f"{score:.3f}" if score is not None else "None"
    explanation = analysis.get("explanation", "")
    trace_id = analysis.get("trace_id", "(unknown)")
    analysis_id = analysis.get("analysis_id", "(unknown)")

    orig = analysis.get("original_decision") or {}
    replay = analysis.get("replay_decision") or {}

    print("=" * 60)
    print("Replay Decision Integrity Analysis")
    print("=" * 60)
    print(f"  trace_id             : {trace_id}")
    print(f"  analysis_id          : {analysis_id}")
    print(f"  consistency          : {status}")
    if drift_type:
        print(f"  drift_type           : {drift_type}")
    print(f"  reproducibility_score: {score_str}")
    print(f"  original_status      : {orig.get('decision_status', '(unknown)')}")
    print(f"  replay_status        : {replay.get('decision_status', '(unknown)')}")

    differences: List[Dict[str, Any]] = consistency.get("differences") or []
    if differences:
        print("  differences:")
        for diff in differences:
            print(
                f"    {diff['field']}: {diff['original_value']!r} → {diff['replay_value']!r}"
            )

    print(f"  explanation          : {explanation}")
    print("=" * 60)


def _consistency_exit_code(analysis: Dict[str, Any]) -> int:
    """Map analysis consistency status to a CLI exit code."""
    consistency = (analysis.get("decision_consistency") or {}).get("status")
    if consistency == CONSISTENCY_CONSISTENT:
        return EXIT_CONSISTENT
    if consistency == CONSISTENCY_DRIFTED:
        return EXIT_DRIFT
    # indeterminate or unknown → treat as failure
    return EXIT_FAILURE


# ---------------------------------------------------------------------------
# CLI main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the Replay Decision Integrity Analysis CLI.

    Returns the exit code (0=consistent, 1=drift, 2=failure).
    """
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate whether a replayed execution reproduces the same SLO "
            "decision and enforcement outcome as the original run."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--trace-id",
        required=True,
        help="The trace ID of the original execution to analyze.",
    )
    parser.add_argument(
        "--replay-output",
        default=None,
        help=(
            f"Path to write the replay_result artifact JSON. "
            f"Defaults to outputs/{_DEFAULT_REPLAY_OUTPUT}."
        ),
    )
    parser.add_argument(
        "--analysis-output",
        default=None,
        help=(
            f"Path to write the replay_decision_analysis artifact JSON. "
            f"Defaults to outputs/{_DEFAULT_ANALYSIS_OUTPUT}."
        ),
    )

    args = parser.parse_args(argv)
    trace_id: str = args.trace_id

    # --- Step 1: Execute replay ---
    try:
        replay_result = execute_replay(trace_id)
    except (ReplayEngineError, ReplayPrerequisiteError) as exc:
        print(f"ERROR: replay failed for trace_id='{trace_id}': {exc}", file=sys.stderr)
        return EXIT_FAILURE
    except Exception as exc:  # noqa: BLE001  # unexpected errors must not silently pass
        print(f"ERROR: unexpected replay failure for trace_id='{trace_id}': {exc}", file=sys.stderr)
        return EXIT_FAILURE

    replay_output_path = (
        Path(args.replay_output) if args.replay_output else _OUTPUT_DIR / _DEFAULT_REPLAY_OUTPUT
    )
    try:
        _write_json(replay_result, replay_output_path)
    except OSError as exc:
        print(
            f"ERROR: failed to write replay result to '{replay_output_path}': {exc}",
            file=sys.stderr,
        )
        return EXIT_FAILURE

    # --- Step 2: Run decision analysis ---
    try:
        analysis = run_replay_decision_analysis(trace_id)
    except ReplayDecisionError as exc:
        print(
            f"ERROR: decision analysis failed for trace_id='{trace_id}': {exc}",
            file=sys.stderr,
        )
        return EXIT_FAILURE

    # --- Step 3: Write analysis output ---
    analysis_output_path = (
        Path(args.analysis_output)
        if args.analysis_output
        else _OUTPUT_DIR / _DEFAULT_ANALYSIS_OUTPUT
    )
    try:
        _write_json(analysis, analysis_output_path)
    except OSError as exc:
        print(
            f"ERROR: failed to write analysis artifact to '{analysis_output_path}': {exc}",
            file=sys.stderr,
        )
        return EXIT_FAILURE

    # --- Step 4: Print summary and return exit code ---
    _print_summary(analysis)
    print(f"  replay_output        : {replay_output_path}")
    print(f"  analysis_output      : {analysis_output_path}")
    print("=" * 60)

    return _consistency_exit_code(analysis)


if __name__ == "__main__":
    raise SystemExit(main())
