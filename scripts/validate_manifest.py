#!/usr/bin/env python3
"""Validate contracts/standards-manifest.json for completeness and strict key integrity."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.governance import validate_manifest_completeness

DEFAULT_MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate standards manifest completeness.")
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Path to standards-manifest.json (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest)
    manifest = _load_json(manifest_path)
    result = validate_manifest_completeness(manifest)

    output = {
        "manifest": str(manifest_path),
        "valid": result["valid"],
        "errors": result["errors"],
        "missing_fields": result["missing_fields"],
        "invalid_entries": result["invalid_entries"],
    }
    print(json.dumps(output, indent=2, sort_keys=True))

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
