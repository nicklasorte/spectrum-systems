#!/usr/bin/env python3
"""Validate a strategic knowledge artifact and emit a governed decision artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.strategic_knowledge.validator import validate_strategic_knowledge_artifact

EXIT_CODES = {
    "allow": 0,
    "require_review": 3,
    "require_rebuild": 2,
    "block": 1,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-path", required=True, type=Path, help="Path to candidate strategic artifact JSON.")
    parser.add_argument(
        "--data-lake-root",
        required=True,
        type=Path,
        help="Data lake root containing strategic_knowledge metadata/lineage directories.",
    )
    args = parser.parse_args()

    if not args.artifact_path.exists():
        print(f"ERROR: artifact path does not exist: {args.artifact_path}", file=sys.stderr)
        return 2

    try:
        artifact = json.loads(args.artifact_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: artifact JSON parse failed at {args.artifact_path}: {exc}", file=sys.stderr)
        return 2

    try:
        decision = validate_strategic_knowledge_artifact(
            artifact=artifact,
            data_lake_root=args.data_lake_root,
        )
    except ValueError as exc:
        print(f"ERROR: validation gate rejected input: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(decision, indent=2))
    return EXIT_CODES[decision["system_response"]]


if __name__ == "__main__":
    raise SystemExit(main())
