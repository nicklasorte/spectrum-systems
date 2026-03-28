#!/usr/bin/env python3
"""Thin CLI runner for VAL-02 fail-closed exhaustive test."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.governance.fail_closed_exhaustive_test import (
    run_fail_closed_exhaustive_test,
)


def _load_input(path: Path | None) -> dict:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input payload must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VAL-02 fail-closed exhaustive seam test")
    parser.add_argument("--input", type=Path, default=None, help="Optional JSON object path for input_refs")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path for fail_closed_exhaustive_result artifact",
    )
    args = parser.parse_args()

    input_refs = _load_input(args.input)
    result = run_fail_closed_exhaustive_test(input_refs)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(str(args.output))

    return 0 if result.get("final_status") == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
