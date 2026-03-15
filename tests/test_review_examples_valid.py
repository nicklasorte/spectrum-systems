import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_REVIEW_PATH = REPO_ROOT / "design-reviews" / "example-claude-review.actions.json"
REQUIRED_FIELDS = ("id", "severity", "category", "title", "description")


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
