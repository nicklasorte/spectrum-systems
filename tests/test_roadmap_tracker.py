import json
from pathlib import Path

import jsonschema


REPO_ROOT = Path(__file__).resolve().parents[1]
ROADMAP_MD = REPO_ROOT / "docs" / "100-step-roadmap.md"
TRACKER_JSON = REPO_ROOT / "ecosystem" / "roadmap-tracker.json"
TRACKER_SCHEMA = REPO_ROOT / "ecosystem" / "roadmap-tracker.schema.json"
README_PATH = REPO_ROOT / "README.md"
CLAUDE_PROTOCOL = REPO_ROOT / "CLAUDE_REVIEW_PROTOCOL.md"
ROADMAP_AUTHORITY = REPO_ROOT / "docs" / "roadmaps" / "roadmap_authority.md"


def test_roadmap_and_tracker_files_exist() -> None:
    assert ROADMAP_MD.is_file(), "docs/100-step-roadmap.md is missing"
    assert TRACKER_JSON.is_file(), "ecosystem/roadmap-tracker.json is missing"
    assert TRACKER_SCHEMA.is_file(), "ecosystem/roadmap-tracker.schema.json is missing"


def test_tracker_validates_against_schema() -> None:
    with TRACKER_SCHEMA.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    with TRACKER_JSON.open(encoding="utf-8") as handle:
        tracker = json.load(handle)
    jsonschema.validate(instance=tracker, schema=schema)


def test_step_numbers_are_unique() -> None:
    with TRACKER_JSON.open(encoding="utf-8") as handle:
        tracker = json.load(handle)
    steps = [entry.get("step_number") for entry in tracker if isinstance(entry, dict)]
    assert len(steps) == len(set(steps)), "step_number values must be unique"


def test_readme_references_roadmap() -> None:
    content = README_PATH.read_text(encoding="utf-8")
    assert "100-step roadmap" in content.lower(), "README must reference the roadmap"


def test_claude_protocol_references_tracker() -> None:
    content = CLAUDE_PROTOCOL.read_text(encoding="utf-8")
    assert "roadmap-tracker.json" in content, "CLAUDE_REVIEW_PROTOCOL must reference roadmap-tracker.json"


def test_tracker_surface_does_not_override_roadmap_authority_bridge() -> None:
    content = ROADMAP_AUTHORITY.read_text(encoding="utf-8")
    assert "docs/roadmaps/system_roadmap.md" in content
    assert "docs/roadmap/system_roadmap.md" in content
