#!/usr/bin/env python3
"""
Validate that finding identifiers stay aligned between a markdown Claude review
and its paired JSON actions file.

Usage:
  python scripts/validate_review_alignment.py path/to/review.md path/to/review.actions.json
"""

import json
import re
import sys
from pathlib import Path
from typing import Set


FINDING_PATTERN = re.compile(r"\[F-(\d+)\]")


def extract_markdown_ids(markdown_path: Path) -> Set[str]:
    text = markdown_path.read_text()
    return {f"F-{match}" for match in FINDING_PATTERN.findall(text)}


def extract_json_ids(json_path: Path) -> Set[str]:
    data = json.loads(json_path.read_text())
    findings = data.get("findings", [])
    return {item["id"] for item in findings if isinstance(item, dict) and "id" in item}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip())
        return 1

    md_path = Path(sys.argv[1])
    json_path = Path(sys.argv[2])

    if not md_path.is_file():
        print(f"Markdown file not found: {md_path}")
        return 1
    if not json_path.is_file():
        print(f"JSON file not found: {json_path}")
        return 1

    try:
        markdown_ids = extract_markdown_ids(md_path)
    except Exception as exc:  # pragma: no cover
        print(f"Error reading markdown: {exc}")
        return 1

    try:
        json_ids = extract_json_ids(json_path)
    except Exception as exc:  # pragma: no cover
        print(f"Error reading JSON: {exc}")
        return 1

    missing_in_json = sorted(markdown_ids - json_ids)
    missing_in_markdown = sorted(json_ids - markdown_ids)

    if missing_in_json or missing_in_markdown:
        if missing_in_json:
            print("IDs present in markdown but missing in JSON:", ", ".join(missing_in_json))
        if missing_in_markdown:
            print("IDs present in JSON but missing in markdown:", ", ".join(missing_in_markdown))
        return 1

    print(f"Success: matched {len(markdown_ids)} finding IDs between {md_path} and {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
