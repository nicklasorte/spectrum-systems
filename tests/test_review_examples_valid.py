import json
import re
from collections import Counter
from pathlib import Path

import jsonschema
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_REVIEW_PATH = REPO_ROOT / "design-reviews" / "example-claude-review.actions.json"
REQUIRED_FIELDS = ("id", "severity", "category", "title", "description")
REQUIRED_FINDING_FIELDS = ("recommended_action", "files_affected", "create_issue")
SCHEMA_PATH = REPO_ROOT / "design-reviews" / "claude-review.schema.json"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _load_example() -> dict:
    assert EXAMPLE_REVIEW_PATH.is_file(), "example-claude-review.actions.json is missing"
    with EXAMPLE_REVIEW_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def test_example_review_actions_structure() -> None:
    payload = _load_example()
    assert "findings" in payload, "findings list missing from example review actions"
    assert isinstance(payload["findings"], list), "findings must be a list"
    for finding in payload["findings"]:
        assert isinstance(finding, dict), "Each finding must be an object"
        for field in REQUIRED_FIELDS:
            assert field in finding, f"Missing '{field}' in finding: {finding}"
            assert finding[field], f"Field '{field}' must be non-empty"
        for field in REQUIRED_FINDING_FIELDS:
            assert field in finding, f"Missing '{field}' in finding: {finding}"
        assert isinstance(finding["create_issue"], bool), "create_issue must be a boolean"

        recommended = finding["recommended_action"]
        if isinstance(recommended, str):
            assert recommended.strip(), "recommended_action string must be non-empty"
        else:
            assert isinstance(recommended, list) and recommended, "recommended_action must be string or non-empty list"
            assert all(isinstance(item, str) and item.strip() for item in recommended), "recommended_action list items must be non-empty strings"

        files_affected = finding["files_affected"]
        if isinstance(files_affected, str):
            assert files_affected.strip(), "files_affected string must be non-empty"
        else:
            assert isinstance(files_affected, list) and files_affected, "files_affected must be string or non-empty list"
            assert all(isinstance(item, str) and item.strip() for item in files_affected), "files_affected list items must be non-empty strings"


def test_example_actions_matches_summary() -> None:
    payload = _load_example()
    assert payload["summary"]["gaps"], "Summary gaps must not be empty"


def test_example_actions_validates_against_schema() -> None:
    payload = _load_example()
    assert SCHEMA_PATH.is_file(), "claude-review.schema.json is missing"
    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        schema = json.load(handle)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.json_path)
    if errors:
        formatted = "\n".join(f"{err.json_path or '$'}: {err.message}" for err in errors)
        pytest.fail(f"Schema validation errors:\n{formatted}")


def test_example_markdown_and_json_ids_align() -> None:
    markdown_path = REPO_ROOT / "design-reviews" / "example-claude-review.md"
    assert markdown_path.is_file(), "example markdown review is missing"
    md_text = markdown_path.read_text(encoding="utf-8")
    md_ids = [f"F-{match}" for match in re.findall(r"\[F-(\d+)\]", md_text)]

    json_ids = [item["id"] for item in _load_example().get("findings", []) if "id" in item]

    json_duplicates = sorted([id_ for id_, count in Counter(json_ids).items() if count > 1])

    assert not json_duplicates, f"Duplicate finding IDs in JSON: {', '.join(json_duplicates)}"
    assert set(md_ids) == set(json_ids), "Finding IDs must match between markdown and JSON artifacts"


def test_due_dates_use_iso_format() -> None:
    payload = _load_example()
    due_dates = []
    for finding in payload.get("findings", []):
        if "due_date" in finding:
            due_dates.append(("finding", finding.get("id"), finding["due_date"]))
    for action in payload.get("actions", []):
        if "due_date" in action:
            due_dates.append(("action", action.get("id"), action["due_date"]))

    follow_up_due = payload.get("follow_up", {}).get("next_review_due")
    if follow_up_due:
        due_dates.append(("follow_up", "next_review_due", follow_up_due))

    assert due_dates, "Expected at least one due_date in example review artifacts"
    for item_type, identifier, due_date in due_dates:
        assert DATE_PATTERN.match(due_date), f"{item_type} {identifier} due_date must use YYYY-MM-DD format"
