#!/usr/bin/env python3
"""Run-bundle validation control loop CLI.

Flow:
validate bundle -> monitor record -> monitor summary -> budget decision.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.evaluation_budget_governor import (  # noqa: E402
    EvaluationBudgetGovernorError,
    run_validation_control_loop,
)

_EXIT_CODES = {
    "allow": 0,
    "warn": 0,
    "freeze": 1,
    "block": 2,
}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the evaluation control loop for a run bundle.")
    parser.add_argument("bundle", help="Path to run bundle directory.")
    parser.add_argument(
        "--emit-intermediate-dir",
        default=None,
        help="Optional directory to write artifact_validation_decision, monitor record, and monitor summary.",
    )
    args = parser.parse_args(argv)

    try:
        budget_decision = run_validation_control_loop(args.bundle)
    except (EvaluationBudgetGovernorError, ValueError, OSError) as exc:
        print(f"ERROR: control loop failed: {exc}", file=sys.stderr)
        return 2

    if args.emit_intermediate_dir:
        out = Path(args.emit_intermediate_dir)
        _write_json(out / "evaluation_budget_decision.json", budget_decision)

    print(json.dumps(budget_decision, indent=2, sort_keys=True))
    return _EXIT_CODES.get(budget_decision.get("system_response", "block"), 2)


if __name__ == "__main__":
    raise SystemExit(main())
