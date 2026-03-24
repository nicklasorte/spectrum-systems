#!/usr/bin/env python3
"""Run deterministic control-loop chaos scenarios and emit JSON summary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.control_loop_chaos import (  # noqa: E402
    ControlLoopChaosError,
    run_chaos_scenarios_from_file,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic control-loop chaos tests for evaluation control decisions."
    )
    parser.add_argument(
        "--scenarios",
        default="tests/fixtures/control_loop_chaos_scenarios.json",
        help="Path to scenario fixture JSON array.",
    )
    parser.add_argument(
        "--output",
        default="outputs/control_loop_chaos/evaluation_control_chaos_summary.json",
        help="Path to write summary artifact JSON.",
    )
    args = parser.parse_args(argv)

    try:
        summary = run_chaos_scenarios_from_file(
            scenarios_path=Path(args.scenarios),
            output_path=Path(args.output),
        )
    except (ControlLoopChaosError, OSError, ValueError) as exc:
        print(f"ERROR: control-loop chaos test run failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if int(summary.get("fail_count", 1)) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
