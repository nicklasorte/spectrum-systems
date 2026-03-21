#!/usr/bin/env python3
"""Thin CLI for run-bundle validation decisions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.run_bundle_validator import validate_and_emit_decision


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a run bundle and emit a decision artifact.")
    parser.add_argument("--bundle", required=True, help="Path to run bundle directory")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    decision = validate_and_emit_decision(args.bundle)
    print(json.dumps(decision, indent=2, sort_keys=True))

    mapping = {
        "allow": 0,
        "require_rebuild": 1,
        "block": 2,
    }
    return mapping[decision["system_response"]]


if __name__ == "__main__":
    raise SystemExit(main())
