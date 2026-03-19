#!/usr/bin/env python3
"""CLI for the Stage-Aware Decision Gating Engine (BN.3).

Evaluates an SLO enforcement decision artifact in the context of a named
pipeline stage and determines whether execution may proceed, must halt, or
may proceed only in explicitly permitted warning states.

Exit codes
----------
0   proceed
1   proceed_with_warning
2   halt
3   malformed input / schema / execution error

Usage
-----
    python scripts/run_slo_gating.py <enforcement_decision.json> [--stage STAGE]

Examples
--------
    # Gate an enforcement decision using the stage embedded in the artifact
    python scripts/run_slo_gating.py outputs/slo_enforcement_decision.json

    # Override stage to synthesis (decision-bearing)
    python scripts/run_slo_gating.py outputs/slo_enforcement_decision.json --stage synthesis

    # Non-decision-bearing stage (warnings allowed)
    python scripts/run_slo_gating.py outputs/slo_enforcement_decision.json --stage observe

    # Write gating decision to a custom path
    python scripts/run_slo_gating.py outputs/slo_enforcement_decision.json \\
        --output /tmp/gating_decision.json

    # Show stage posture diagnostics (no artifact required)
    python scripts/run_slo_gating.py --show-stage-posture
    python scripts/run_slo_gating.py --show-stage-posture --stage synthesis
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.decision_gating import (  # noqa: E402
    KNOWN_STAGES,
    OUTCOME_HALT,
    OUTCOME_PROCEED,
    OUTCOME_PROCEED_WITH_WARNING,
    describe_stage_gating_posture,
    run_slo_gating,
    summarize_gating_decision,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXIT_PROCEED = 0
EXIT_PROCEED_WITH_WARNING = 1
EXIT_HALT = 2
EXIT_ERROR = 3

_OUTPUT_DIR = _REPO_ROOT / "outputs"
_DEFAULT_OUTPUT_FILENAME = "slo_gating_decision.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_artifact(path: Path) -> Any:
    """Load JSON from *path*."""
    return json.loads(path.read_text(encoding="utf-8"))


def _write_decision(decision: Dict[str, Any], output_path: Path) -> None:
    """Write the gating decision artifact as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(decision, indent=2), encoding="utf-8")


def _outcome_exit_code(gating_outcome: str, has_schema_errors: bool) -> int:
    """Map a gating outcome (and optional schema errors) to an exit code."""
    if has_schema_errors:
        return EXIT_ERROR
    if gating_outcome == OUTCOME_PROCEED:
        return EXIT_PROCEED
    if gating_outcome == OUTCOME_PROCEED_WITH_WARNING:
        return EXIT_PROCEED_WITH_WARNING
    if gating_outcome == OUTCOME_HALT:
        return EXIT_HALT
    return EXIT_ERROR


def _print_show_stage_posture(stage: Optional[str]) -> int:
    """Print stage gating posture diagnostics; return exit code 0."""
    if stage:
        posture = describe_stage_gating_posture(stage)
        print(f"Stage gating posture for '{stage}':")
        for k, v in posture.items():
            print(f"  {k:<24}: {v}")
    else:
        print("Stage gating postures (all stages):")
        for s in sorted(KNOWN_STAGES):
            posture = describe_stage_gating_posture(s)
            print(
                f"  {s:<12}  warnings_allowed={posture['warnings_allowed']!s:<5}  "
                f"decision_bearing={posture['decision_bearing']!s:<5}  "
                f"({posture['gating_posture']})"
            )
    return EXIT_PROCEED


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the SLO gating CLI.

    Returns the exit code (0/1/2/3).
    """
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate an SLO enforcement decision artifact in the context of a "
            "named pipeline stage and determine whether execution may proceed."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "enforcement_decision_path",
        nargs="?",
        default=None,
        help=(
            "Path to the enforcement decision JSON file to gate. "
            "Not required when using --show-stage-posture."
        ),
    )
    parser.add_argument(
        "--stage",
        choices=sorted(KNOWN_STAGES),
        default=None,
        help=(
            "Pipeline stage to gate against. "
            "When not provided the stage embedded in the enforcement artifact's "
            "'enforcement_scope' field is used."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            f"Output path for the gating decision artifact. "
            f"Defaults to outputs/{_DEFAULT_OUTPUT_FILENAME}."
        ),
    )
    parser.add_argument(
        "--show-stage-posture",
        action="store_true",
        default=False,
        help=(
            "Show the gating posture for the given --stage (or all stages if "
            "no --stage is given) and exit. Does not require an artifact path."
        ),
    )

    args = parser.parse_args(argv)

    # Diagnostics mode — no artifact required.
    if args.show_stage_posture:
        return _print_show_stage_posture(args.stage)

    # Gating mode requires an artifact path.
    if args.enforcement_decision_path is None:
        print(
            "ERROR: enforcement_decision_path is required for gating. "
            "Use --show-stage-posture for diagnostics.",
            file=sys.stderr,
        )
        parser.print_usage(sys.stderr)
        return EXIT_ERROR

    decision_path = Path(args.enforcement_decision_path)
    if not decision_path.exists():
        print(f"ERROR: enforcement decision path not found: {decision_path}", file=sys.stderr)
        return EXIT_ERROR

    try:
        raw_input = _load_artifact(decision_path)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to load enforcement decision JSON: {exc}", file=sys.stderr)
        return EXIT_ERROR

    # Run gating
    result = run_slo_gating(raw_input, stage=args.stage)

    # Print human-readable summary
    print(summarize_gating_decision(result))

    # Write gating decision artifact
    output_path = Path(args.output) if args.output else _OUTPUT_DIR / _DEFAULT_OUTPUT_FILENAME
    try:
        _write_decision(result["gating_decision"], output_path)
        print(f"  output_path              : {output_path}")
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to write gating decision artifact: {exc}", file=sys.stderr)
        return EXIT_ERROR

    schema_errors: List[str] = result.get("schema_errors") or []
    return _outcome_exit_code(result["gating_outcome"], bool(schema_errors))


if __name__ == "__main__":
    sys.exit(main())
