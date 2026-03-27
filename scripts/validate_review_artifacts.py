#!/usr/bin/env python3
"""Repo-level review artifact validator.

This wrapper provides a single authoritative path by reusing the canonical
pairwise validator (`scripts/validate_review_artifact.py`) for every discovered
review artifact JSON + markdown pair.

Usage:
    python scripts/validate_review_artifacts.py
    python scripts/validate_review_artifacts.py <file.json> ...
    python scripts/validate_review_artifacts.py --dirs <dir> ...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from validate_review_artifact import validate_markdown_metadata, validate_review_json

_BASE_DIR = Path(__file__).resolve().parents[1]

_DEFAULT_REVIEW_DIRS = [
    _BASE_DIR / "docs" / "reviews",
    _BASE_DIR / "design-reviews",
    _BASE_DIR / "docs" / "review-actions",
]

_CANONICAL_REVIEW_KEYS = {
    "review_id",
    "module",
    "review_type",
    "review_date",
    "reviewer",
    "decision",
    "trust_assessment",
    "status",
    "scope",
    "related_plan",
    "critical_findings",
    "required_fixes",
    "watch_items",
    "failure_mode_summary",
}


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        return data
    return None


def _is_canonical_review_artifact(path: Path) -> bool:
    if path.name.endswith(".failure.json") or path.name.endswith(".schema.json"):
        return False
    payload = _load_json(path)
    if payload is None:
        return False
    return _CANONICAL_REVIEW_KEYS.issubset(payload.keys())


def discover_review_artifacts(directories: list[Path]) -> list[Path]:
    paths: list[Path] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            if _is_canonical_review_artifact(path):
                paths.append(path)
    return paths


def _markdown_pair(path: Path) -> Path:
    return path.with_suffix(".md")


def validate_artifact_pair(path: Path) -> dict[str, Any]:
    json_errors = validate_review_json(path)

    markdown_path = _markdown_pair(path)
    markdown_errors: list[str]
    if markdown_path.is_file():
        markdown_errors = validate_markdown_metadata(markdown_path)
    else:
        markdown_errors = [f"missing markdown companion: {markdown_path}"]

    errors = [f"JSON: {e}" for e in json_errors] + [f"MARKDOWN: {e}" for e in markdown_errors]

    payload = _load_json(path) or {}
    return {
        "file": str(path),
        "review_id": payload.get("review_id", "unknown"),
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate governed review artifacts via canonical pairwise validator logic."
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Path(s) to review artifact JSON file(s). If omitted, scans default review directories.",
    )
    parser.add_argument(
        "--dirs",
        nargs="*",
        metavar="DIR",
        help="Override directories to scan for review artifact JSON files.",
    )
    args = parser.parse_args(argv)

    if args.files:
        paths = [Path(f).resolve() for f in args.files]
    elif args.dirs:
        paths = discover_review_artifacts([Path(d).resolve() for d in args.dirs])
    else:
        paths = discover_review_artifacts(_DEFAULT_REVIEW_DIRS)

    if not paths:
        print("No canonical review artifact JSON files found to validate.")
        return 0

    results = [validate_artifact_pair(path) for path in paths]
    failures = [result for result in results if result["status"] == "fail"]

    for result in results:
        if result["status"] == "pass":
            print(f"PASS  {result['file']}")
            continue
        print(f"FAIL  {result['file']}")
        for error in result["errors"]:
            print(f"      - {error}")

    if failures:
        print(f"\n{len(failures)} of {len(results)} file(s) failed review artifact validation.")
        return 1

    print(f"\nAll {len(results)} review artifact(s) passed validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
