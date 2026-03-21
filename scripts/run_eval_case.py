#!/usr/bin/env python3
"""Run a single eval_case artifact and emit eval_result JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.evaluation.eval_engine import run_eval_case  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a governed eval_case artifact")
    parser.add_argument("--case", required=True, help="Path to eval_case JSON")
    parser.add_argument("--output", help="Optional output path for eval_result JSON")
    args = parser.parse_args(argv)

    eval_case = json.loads(Path(args.case).read_text(encoding="utf-8"))
    result = run_eval_case(eval_case)

    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
