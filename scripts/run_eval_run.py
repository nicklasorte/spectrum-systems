#!/usr/bin/env python3
"""Run a governed eval_run artifact and emit eval run execution JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.evaluation.eval_engine import run_eval_run  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a governed eval_run artifact")
    parser.add_argument("--run", required=True, help="Path to eval_run JSON")
    parser.add_argument("--cases", required=True, help="Path to JSON array of eval_case artifacts")
    parser.add_argument("--output", help="Optional output path for eval run execution JSON")
    args = parser.parse_args(argv)

    eval_run = json.loads(Path(args.run).read_text(encoding="utf-8"))
    eval_cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))

    output = run_eval_run(eval_run, eval_cases)
    text = json.dumps(output, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
