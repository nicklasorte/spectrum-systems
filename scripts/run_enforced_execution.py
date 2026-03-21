#!/usr/bin/env python3
"""Run enforced execution pipeline for run bundles.

Flow:
bundle validation -> monitor record -> monitor summary -> budget decision -> enforcement.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.control_executor import (  # noqa: E402
    execute_with_enforcement,
)

_EXIT_CODES = {
    "allow": 0,
    "warn": 0,
    "freeze": 1,
    "block": 2,
}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run enforced execution for a run bundle.")
    parser.add_argument("--bundle", required=True, help="Path to run bundle directory.")
    args = parser.parse_args(argv)

    try:
        enforcement_result = execute_with_enforcement(args.bundle)
    except (OSError, ValueError) as exc:
        print(f"ERROR: enforced execution failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(enforcement_result, indent=2, sort_keys=True))
    return _EXIT_CODES.get(enforcement_result.get("enforcement_action", "block"), 2)


if __name__ == "__main__":
    raise SystemExit(main())
