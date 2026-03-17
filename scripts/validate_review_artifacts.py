#!/usr/bin/env python3
"""
Validate review artifact JSON files against the canonical review-artifact schema.

Validates that every review artifact under docs/reviews/, design-reviews/, and
docs/review-actions/ conforms to schemas/review-artifact.schema.json.

Usage:
    python scripts/validate_review_artifacts.py                   # scan all known review dirs
    python scripts/validate_review_artifacts.py <file.json> ...   # validate specific files
    python scripts/validate_review_artifacts.py --dirs <dir> ...  # validate a specific directory
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

_BASE_DIR = Path(__file__).resolve().parents[1]
_SCHEMA_PATH = _BASE_DIR / "schemas" / "review-artifact.schema.json"

# Directories that may contain review artifact JSON files
_DEFAULT_REVIEW_DIRS = [
    _BASE_DIR / "docs" / "reviews",
    _BASE_DIR / "design-reviews",
    _BASE_DIR / "docs" / "review-actions",
]


def load_schema() -> Dict[str, Any]:
    """Load the canonical review-artifact JSON Schema."""
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_review_artifact(
    instance: Dict[str, Any],
    schema: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Validate a review artifact instance against the schema.

    Returns a list of human-readable error strings (empty list means valid).
    """
    if schema is None:
        schema = load_schema()
    validator = Draft202012Validator(schema)
    errors: List[str] = []
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        path = list(error.path)
        location = f"[{'.'.join(str(p) for p in path)}]" if path else "[root]"
        errors.append(f"Schema error at {location}: {error.message}")
    return errors


def validate_file(path: Path, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load and validate a single review artifact JSON file.

    Returns a result dict with keys: ``file``, ``review_id``, ``status``,
    and ``errors``.
    """
    try:
        instance: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "file": str(path),
            "review_id": "unknown",
            "status": "fail",
            "errors": [f"Cannot load file: {exc}"],
        }

    # Only validate files that look like review artifacts (have review_id or source)
    if not isinstance(instance, dict):
        return {
            "file": str(path),
            "review_id": "unknown",
            "status": "skip",
            "errors": ["Not a JSON object — skipping"],
        }

    # Skip JSON files that are clearly not review artifacts
    if "review_id" not in instance and "source" not in instance and "findings" not in instance:
        return {
            "file": str(path),
            "review_id": "unknown",
            "status": "skip",
            "errors": [],
        }

    errors = validate_review_artifact(instance, schema)
    return {
        "file": str(path),
        "review_id": instance.get("review_id", "unknown"),
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def discover_review_artifacts(directories: List[Path]) -> List[Path]:
    """Find all JSON files in the given directories (non-recursive for top level)."""
    paths: List[Path] = []
    for directory in directories:
        if directory.is_dir():
            paths.extend(sorted(directory.glob("*.json")))
    return paths


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate review artifact JSON files against the canonical schema."
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

    if not _SCHEMA_PATH.is_file():
        print(f"ERROR: Review artifact schema not found at {_SCHEMA_PATH}", file=sys.stderr)
        return 1

    schema = load_schema()

    if args.files:
        paths = [Path(f).resolve() for f in args.files]
    elif args.dirs:
        paths = discover_review_artifacts([Path(d) for d in args.dirs])
    else:
        paths = discover_review_artifacts(_DEFAULT_REVIEW_DIRS)

    if not paths:
        print("No review artifact JSON files found to validate.")
        return 0

    results = [validate_file(p, schema) for p in paths]
    validated = [r for r in results if r["status"] != "skip"]
    failures = [r for r in validated if r["status"] == "fail"]

    for result in results:
        if result["status"] == "skip":
            continue
        if result["status"] == "pass":
            print(f"PASS  {result['file']}")
        else:
            print(f"FAIL  {result['file']}")
            for error in result["errors"]:
                print(f"      - {error}")

    if not validated:
        print("No review artifact files matched the schema (no files with review_id/source/findings).")
        return 0

    if failures:
        print(f"\n{len(failures)} of {len(validated)} file(s) failed review artifact validation.")
        return 1

    print(f"\nAll {len(validated)} review artifact(s) passed validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
