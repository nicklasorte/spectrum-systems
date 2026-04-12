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
from spectrum_systems.modules.runtime.execution_contracts import (  # noqa: E402
    evaluate_execution_contracts,
    to_artifact,
)

_EXIT_CODES = {
    "allow": 0,
    "require_review": 1,
    "deny": 2,
}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run enforced execution for a run bundle.")
    parser.add_argument("--bundle", required=True, help="Path to run bundle directory.")
    parser.add_argument("--changed-file", action="append", default=[], help="Changed file path; required at least once.")
    parser.add_argument("--commit-sha", default="", help="Execution commit SHA.")
    parser.add_argument("--pr-number", default="", help="Execution PR number.")
    parser.add_argument("--tests-passed", action="store_true", help="Flag indicating required tests passed.")
    args = parser.parse_args(argv)

    contract = evaluate_execution_contracts(
        changed_files=args.changed_file,
        commit_sha=args.commit_sha,
        pr_number=args.pr_number,
        tests_passed=bool(args.tests_passed),
    )
    if contract.status != "passed":
        print(json.dumps(to_artifact(contract), indent=2, sort_keys=True))
        return 2

    try:
        enforcement_result = execute_with_enforcement(args.bundle)
    except (OSError, ValueError) as exc:
        print(f"ERROR: enforced execution failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(enforcement_result, indent=2, sort_keys=True))
    return _EXIT_CODES.get(enforcement_result.get("final_status", "deny"), 2)


if __name__ == "__main__":
    raise SystemExit(main())
