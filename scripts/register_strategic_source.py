#!/usr/bin/env python3
"""Register a strategic raw source into strategic_knowledge/metadata/source_catalog.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.strategic_knowledge.catalog import register_source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-lake-root", required=True, type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-type", required=True)
    parser.add_argument("--source-path", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--status", default="registered")
    parser.add_argument("--tags", nargs="*", default=[])
    parser.add_argument("--metadata-json", default="{}")
    args = parser.parse_args()

    metadata = json.loads(args.metadata_json)
    source_catalog_path = args.data_lake_root / "strategic_knowledge" / "metadata" / "source_catalog.json"
    entry = register_source(
        source_catalog_path=source_catalog_path,
        source_id=args.source_id,
        source_type=args.source_type,
        source_path=args.source_path,
        title=args.title,
        tags=args.tags,
        status=args.status,
        metadata=metadata,
    )
    print(json.dumps(entry, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

