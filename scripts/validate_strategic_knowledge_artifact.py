#!/usr/bin/env python3
"""Validate a strategic knowledge artifact and emit a governed decision artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.strategic_knowledge.validation_loader import (  # noqa: E402
    load_artifact_payload,
    load_artifact_registry_payload,
    load_source_catalog_payload,
)
from spectrum_systems.modules.strategic_knowledge.validator import validate_strategic_knowledge_artifact  # noqa: E402

EXIT_CODES = {
    "allow": 0,
    "require_review": 0,
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
    parser.add_argument("--trace-id", type=str, default=None, help="Optional trace identifier override.")
    parser.add_argument("--span-id", type=str, default=None, help="Optional span identifier override.")
    args = parser.parse_args()

    try:
        artifact = load_artifact_payload(args.artifact_path)
        source_catalog = load_source_catalog_payload(args.data_lake_root)
        artifact_registry = load_artifact_registry_payload(args.data_lake_root)
        decision = validate_strategic_knowledge_artifact(
            artifact,
            {
                "source_catalog": source_catalog,
                "artifact_registry": artifact_registry,
                "trace_id": args.trace_id,
                "span_id": args.span_id,
            },
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"ERROR: artifact JSON parse failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(decision, indent=2))
    return EXIT_CODES[decision["system_response"]]


if __name__ == "__main__":
    raise SystemExit(main())
