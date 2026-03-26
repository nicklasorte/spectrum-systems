#!/usr/bin/env python3
"""Validate review artifact JSON payloads and markdown review metadata frontmatter."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "review_artifact.schema.json"
REQUIRED_MARKDOWN_FIELDS = (
    "module",
    "review_type",
    "review_date",
    "reviewer",
    "decision",
    "trust_assessment",
    "status",
    "related_plan",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_review_json(path: Path) -> list[str]:
    schema = load_json(SCHEMA_PATH)
    instance = load_json(path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    return [f"{list(error.path) or ['root']}: {error.message}" for error in errors]


def parse_frontmatter(markdown_text: str) -> dict[str, str] | None:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", markdown_text, re.DOTALL)
    if not match:
        return None

    values: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def validate_markdown_metadata(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    metadata = parse_frontmatter(text)
    if metadata is None:
        return ["missing YAML frontmatter block"]

    errors: list[str] = []
    for field in REQUIRED_MARKDOWN_FIELDS:
        value = metadata.get(field, "")
        if not value:
            errors.append(f"missing required metadata field: {field}")

    if metadata.get("decision") not in {"PASS", "FAIL"}:
        errors.append("decision must be PASS or FAIL")
    if metadata.get("trust_assessment") not in {"high", "medium", "low"}:
        errors.append("trust_assessment must be high, medium, or low")
    if metadata.get("status") not in {"final"}:
        errors.append("status must be final")
    if metadata.get("review_date") and not re.match(r"^\d{4}-\d{2}-\d{2}$", metadata["review_date"]):
        errors.append("review_date must use YYYY-MM-DD")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate review artifact files.")
    parser.add_argument("json_file", type=Path, nargs="?", help="Path to review artifact JSON file")
    parser.add_argument("--markdown", type=Path, help="Path to markdown review file")
    args = parser.parse_args(argv)

    if not SCHEMA_PATH.is_file():
        print(f"ERROR: missing schema at {SCHEMA_PATH}", file=sys.stderr)
        return 1

    if args.json_file is None and args.markdown is None:
        parser.error("provide a JSON file and/or --markdown file")

    errors: list[str] = []

    if args.json_file is not None:
        json_errors = validate_review_json(args.json_file)
        errors.extend([f"JSON: {message}" for message in json_errors])

    if args.markdown is not None:
        markdown_errors = validate_markdown_metadata(args.markdown)
        errors.extend([f"MARKDOWN: {message}" for message in markdown_errors])

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    print("PASS: review artifact validation succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
