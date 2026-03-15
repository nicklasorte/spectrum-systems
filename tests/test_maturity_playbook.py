import json
from pathlib import Path

import jsonschema


REPO_ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_PATH = REPO_ROOT / "docs" / "level-0-to-20-playbook.md"
RUBRIC_PATH = REPO_ROOT / "docs" / "review-maturity-rubric.md"
TRACKER_PATH = REPO_ROOT / "ecosystem" / "maturity-tracker.json"
TRACKER_SCHEMA_PATH = REPO_ROOT / "ecosystem" / "maturity-tracker.schema.json"
DESIGN_REVIEW_STANDARD_PATH = REPO_ROOT / "docs" / "design-review-standard.md"
README_PATH = REPO_ROOT / "README.md"


def test_playbook_exists() -> None:
    assert PLAYBOOK_PATH.exists(), "Maturity playbook document must exist"


def test_rubric_exists() -> None:
    assert RUBRIC_PATH.exists(), "Maturity review rubric must exist"


def test_tracker_files_exist() -> None:
    assert TRACKER_PATH.exists(), "Maturity tracker JSON must exist"
    assert TRACKER_SCHEMA_PATH.exists(), "Maturity tracker schema must exist"


def test_tracker_validates_against_schema() -> None:
    tracker = json.loads(TRACKER_PATH.read_text())
    schema = json.loads(TRACKER_SCHEMA_PATH.read_text())
    jsonschema.validate(tracker, schema)
    for record in tracker:
        assert 0 <= record["current_level"] <= 20
        assert 0 <= record["target_level_next"] <= 20
        assert record["target_level_next"] >= record["current_level"]


def test_design_review_standard_references_maturity_section() -> None:
    content = DESIGN_REVIEW_STANDARD_PATH.read_text()
    assert "Maturity Assessment" in content


def test_readme_references_playbook_or_rubric() -> None:
    content = README_PATH.read_text()
    assert "level-0-to-20-playbook.md" in content or "review-maturity-rubric.md" in content
