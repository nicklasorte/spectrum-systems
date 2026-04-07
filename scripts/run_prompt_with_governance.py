#!/usr/bin/env python3
"""Run prompt preflight governance checks before prompt execution stub."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run governance preflight before prompt execution."
    )
    parser.add_argument("prompt_file", type=Path, help="Prompt file path")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Stub execute mode: print prompt body after passing preflight.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if not args.prompt_file.is_file():
        print(f"ERROR: prompt file not found: {args.prompt_file}", file=sys.stderr)
        return 1

    checker = Path(__file__).with_name("check_governance_compliance.py")
    cmd = [sys.executable, str(checker), "--file", str(args.prompt_file)]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)

    if result.returncode != 0:
        print("BLOCKED: governance preflight failed; prompt execution stopped.")
        return result.returncode

    if args.execute:
        print("PRECHECK PASSED: executing prompt (stub output below).")
        print(args.prompt_file.read_text(encoding="utf-8"))
    else:
        print("PRECHECK PASSED: prompt ready for execution.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
