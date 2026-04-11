#!/usr/bin/env python3
"""Run GOVERNED-KERNEL-24-01 deterministic governed execution kernel."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.governed_execution_kernel import (
    GovernedKernelError,
    run_governed_kernel_24_01,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="artifacts/governed_kernel_24_01",
        help="directory where governed kernel artifacts are written",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output_dir = Path(args.output_dir)
    try:
        outputs = run_governed_kernel_24_01(output_dir)
    except GovernedKernelError as exc:
        print(f"FAIL: {exc}")
        return 1

    summary = outputs["run_summary.json"]
    print(json.dumps({"status": summary["status"], "run_id": summary["run_id"], "output_dir": str(output_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
