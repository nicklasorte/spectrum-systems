#!/usr/bin/env python3
"""Initialize/verify the governed strategic knowledge layout in spectrum-data-lake."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.strategic_knowledge.pathing import required_data_lake_dirs

README_TEXT = {
    "strategic_knowledge/raw": "# Raw Strategic Sources\n\nDurable raw source files (books, transcripts, slides).\n",
    "strategic_knowledge/processed": "# Processed Strategic Knowledge\n\nSchema-governed extracted artifacts emitted by spectrum-systems extractors.\n",
    "strategic_knowledge/indexes": "# Strategic Knowledge Indexes\n\nDeterministic indexes for retrieval and discovery.\n",
    "strategic_knowledge/metadata": "# Strategic Knowledge Metadata\n\nCatalog and extraction manifests for source/artifact bookkeeping.\n",
    "strategic_knowledge/lineage": "# Strategic Knowledge Lineage\n\nLineage manifests linking artifacts back to source evidence and runs.\n",
}

DEFAULT_JSON_FILES = {
    "strategic_knowledge/metadata/source_catalog.json": {
        "schema_version": "1.0.0",
        "catalog_version": "1.0.0",
        "updated_at": "1970-01-01T00:00:00Z",
        "sources": []
    },
    "strategic_knowledge/metadata/extraction_manifest.json": {
        "schema_version": "1.0.0",
        "manifest_version": "1.0.0",
        "updated_at": "1970-01-01T00:00:00Z",
        "runs": []
    },
    "strategic_knowledge/lineage/lineage_manifest.json": {
        "schema_version": "1.0.0",
        "manifest_version": "1.0.0",
        "updated_at": "1970-01-01T00:00:00Z",
        "lineage_records": []
    },
}


def init_data_lake(data_lake_root: Path) -> None:
    for rel in required_data_lake_dirs():
        (data_lake_root / rel).mkdir(parents=True, exist_ok=True)

    for rel, content in README_TEXT.items():
        readme_path = data_lake_root / rel / "README.md"
        if not readme_path.exists():
            readme_path.write_text(content, encoding="utf-8")

    for rel, payload in DEFAULT_JSON_FILES.items():
        path = data_lake_root / rel
        if not path.exists():
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-lake-root", required=True, type=Path)
    args = parser.parse_args()

    init_data_lake(args.data_lake_root)
    print(f"Initialized strategic knowledge scaffold at {args.data_lake_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

