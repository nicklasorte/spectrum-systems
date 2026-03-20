#!/usr/bin/env python3
"""CLI for the BT — Evaluation Budget Governor.

Ingests an evaluation_monitor_summary artifact, enforces the evaluation
budget policy, and emits a schema-validated evaluation_budget_decision
artifact.

Exit codes
----------
0   allow           – system is healthy; proceed normally
1   allow_with_warning / require_review – proceed with caution or human review required
2   freeze_changes / block_release – changes must stop; error state

Usage
-----
    python scripts/run_evaluation_budget_governor.py \\
        --input path/to/evaluation_monitor_summary.json \\
        [--output-dir path/to/output/] \\
        [--thresholds path/to/thresholds.json]

Examples
--------
    python scripts/run_evaluation_budget_governor.py \\
        --input outputs/evaluation_monitor/evaluation_monitor_summary.json \\
        --output-dir outputs/evaluation_budget_governor/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.evaluation_budget_governor import (  # noqa: E402
    EvaluationBudgetGovernorError,
    InvalidSummaryError,
    run_budget_governor,
)

# ---------------------------------------------------------------------------
# Exit code constants
# ---------------------------------------------------------------------------

EXIT_ALLOW = 0
EXIT_CAUTION = 1
EXIT_ERROR = 2

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_OUTPUT_DIR = _REPO_ROOT / "outputs" / "evaluation_budget_governor"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(artifact: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(artifact, fh, indent=2)
    print(f"Written: {path}")


def _load_thresholds(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        print(f"ERROR: thresholds file not found: {path}", file=sys.stderr)
        sys.exit(EXIT_ERROR)
    try:
        with p.open(encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"ERROR: failed to parse thresholds JSON: {exc}", file=sys.stderr)
        sys.exit(EXIT_ERROR)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the Evaluation Budget Governor CLI.

    Returns the exit code (0=allow, 1=caution, 2=error/blocked).
    """
    parser = argparse.ArgumentParser(
        description=(
            "Ingest an evaluation_monitor_summary artifact and emit a governed "
            "evaluation_budget_decision artifact."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="PATH",
        help="Path to an evaluation_monitor_summary JSON file.",
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
    parser.add_argument(
        "--thresholds",
        default=None,
        metavar="PATH",
        help=(
            "Optional path to a JSON file containing policy threshold overrides. "
            "Keys must match threshold names defined in evaluation_budget_governor.py."
        ),
    )

    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir) if args.output_dir else _DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    thresholds = _load_thresholds(args.thresholds) if args.thresholds else None

    # --- Execute governor ---
    try:
        decision = run_budget_governor(args.input, thresholds=thresholds)
    except InvalidSummaryError as exc:
        print(f"ERROR: invalid evaluation_monitor_summary: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except EvaluationBudgetGovernorError as exc:
        print(f"ERROR: budget governor failure: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:  # noqa: BLE001
        print(
            f"ERROR: unexpected failure ({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        return EXIT_ERROR

    # --- Write decision artifact ---
    decision_path = output_dir / "evaluation_budget_decision.json"
    try:
        _write_json(decision, decision_path)
    except OSError as exc:
        print(
            f"ERROR: failed to write decision to '{decision_path}': {exc}",
            file=sys.stderr,
        )
        return EXIT_ERROR

    # --- Print console summary ---
    print(
        f"\nEvaluation Budget Decision\n"
        f"  Decision ID:      {decision['decision_id']}\n"
        f"  Summary ID:       {decision['summary_id']}\n"
        f"  Status:           {decision['status']}\n"
        f"  System response:  {decision['system_response']}\n"
        f"  Created at:       {decision['created_at']}"
    )

    if decision["triggered_thresholds"]:
        print("  Triggered thresholds:")
        for t in decision["triggered_thresholds"]:
            print(f"    - {t}")

    print("  Reasons:")
    for r in decision["reasons"]:
        print(f"    - {r}")

    print("  Required actions:")
    for a in decision["required_actions"]:
        print(f"    - {a}")

    # --- Determine exit code ---
    system_response = decision["system_response"]

    if system_response in ("freeze_changes", "block_release"):
        print(
            f"\nExit 2: system response requires halt "
            f"(system_response={system_response})",
            file=sys.stderr,
        )
        return EXIT_ERROR

    if system_response in ("allow_with_warning", "require_review"):
        print(
            f"\nExit 1: caution or review required "
            f"(system_response={system_response})",
            file=sys.stderr,
        )
        return EXIT_CAUTION

    return EXIT_ALLOW


if __name__ == "__main__":
    sys.exit(main())
