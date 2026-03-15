import json
import subprocess
from pathlib import Path

import jsonschema
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_SLUG = "2026-03-14-claude-review-automation"
EXAMPLE_ACTIONS_PATH = REPO_ROOT / "design-reviews" / f"{EXAMPLE_SLUG}.actions.json"
EXAMPLE_MARKDOWN_PATH = REPO_ROOT / "design-reviews" / f"{EXAMPLE_SLUG}.md"
REQUIRED_FIELDS = ("id", "severity", "category", "title", "description")
REQUIRED_FINDING_FIELDS = ("recommended_action", "files_affected", "create_issue")
SCHEMA_PATH = REPO_ROOT / "design-reviews" / "claude-review.schema.json"


def _load_example() -> dict:
    assert EXAMPLE_ACTIONS_PATH.is_file(), "2026-03-14-claude-review-automation.actions.json is missing"
    with EXAMPLE_ACTIONS_PATH.open(encoding="utf-8") as handle:
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
        pytest.fail(f"Schema validation errors:\\n{formatted}")


def test_example_pairing_and_alignment() -> None:
    payload = _load_example()
    metadata = payload["review_metadata"]

    assert EXAMPLE_MARKDOWN_PATH.is_file(), "Example markdown review is missing"
    assert metadata["review_id"] == EXAMPLE_SLUG
    assert metadata["source_artifact"] == f"design-reviews/{EXAMPLE_SLUG}.md"
    assert metadata["actions_artifact"] == f"design-reviews/{EXAMPLE_SLUG}.actions.json"
    assert EXAMPLE_ACTIONS_PATH.is_file(), "Example actions file is missing"

    result = subprocess.run(
        [
            "python",
            "scripts/validate_review_alignment.py",
            f"design-reviews/{EXAMPLE_SLUG}.md",
            f"design-reviews/{EXAMPLE_SLUG}.actions.json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Alignment validation failed:\\nSTDOUT: {result.stdout}\\nSTDERR: {result.stderr}"
