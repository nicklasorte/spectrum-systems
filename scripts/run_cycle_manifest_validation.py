#!/usr/bin/env python3
"""Validate a cycle manifest (schema + semantic invariants)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.orchestration.cycle_manifest_validator import CycleManifestError, validate_cycle_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a cycle manifest artifact.")
    parser.add_argument("manifest_path", help="Path to cycle_manifest JSON artifact")
    args = parser.parse_args()

    path = Path(args.manifest_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: manifest not found: {path}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in {path}: {exc}", file=sys.stderr)
        return 2

    if not isinstance(payload, dict):
        print("ERROR: manifest root must be a JSON object", file=sys.stderr)
        return 2

    try:
        validate_cycle_manifest(payload)
    except CycleManifestError as exc:
        print(f"ERROR: cycle manifest validation failed: {exc}", file=sys.stderr)
        return 1

    print(f"OK: cycle manifest valid: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
