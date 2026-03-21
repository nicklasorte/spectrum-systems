#!/usr/bin/env python3
"""Run enforced execution followed by deterministic replay for a run bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.control_executor import execute_with_replay  # noqa: E402


_EXIT_CODES = {
    ("success", True): 0,
    ("failed", False): 1,
    ("indeterminate", False): 2,
}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic replay execution for a run bundle.")
    parser.add_argument("--bundle", required=True, help="Path to run bundle directory.")
    args = parser.parse_args(argv)

    try:
        replay_record = execute_with_replay(args.bundle)
    except (OSError, ValueError) as exc:
        print(f"ERROR: replay execution failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(replay_record, indent=2, sort_keys=True))

    replay_status = str(replay_record.get("replay_status") or "indeterminate")
    consistency_check_passed = bool(replay_record.get("consistency_check_passed"))
    return _EXIT_CODES.get((replay_status, consistency_check_passed), 2)


if __name__ == "__main__":
    raise SystemExit(main())
