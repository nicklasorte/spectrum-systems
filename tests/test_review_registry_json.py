import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Dict, List

import jsonschema
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "docs" / "reviews" / "review-registry.json"
SCHEMA_PATH = REPO_ROOT / "docs" / "reviews" / "review-registry.schema.json"
MARKDOWN_REGISTRY_PATH = REPO_ROOT / "docs" / "review-registry.md"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _load_registry() -> List[dict]:
    assert REGISTRY_PATH.is_file(), "docs/reviews/review-registry.json is missing"
    with REGISTRY_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    assert isinstance(data, list), "Registry must be a JSON array"
    return data


def _parse_markdown_registry() -> Dict[str, dict]:
    assert MARKDOWN_REGISTRY_PATH.is_file(), "docs/review-registry.md is missing"
    content = MARKDOWN_REGISTRY_PATH.read_text(encoding="utf-8").splitlines()
    entries: Dict[str, dict] = {}

    header_index = next(
        (idx for idx, line in enumerate(content) if line.strip().startswith("| Review Date")),
        None,
    )
    if header_index is None:
        return entries

    for line in content[header_index + 2 :]:
        if not line.strip().startswith("|"):
            break
        if line.strip().startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 8:
            continue

        def _extract_path(cell: str) -> str:
            match = re.search(r"\[([^\]]+)\]\([^)]+\)", cell)
            return match.group(1) if match else cell

        follow_up_cell = cells[7]
        follow_up_due_date = None
        follow_up_trigger = follow_up_cell
        match = re.match(r"(?P<date>\d{4}-\d{2}-\d{2})\s*/\s*(?P<trigger>.+)", follow_up_cell)
        if match:
            follow_up_due_date = match.group("date")
            follow_up_trigger = match.group("trigger").strip()

        artifact_path = _extract_path(cells[4])
        entries[artifact_path] = {
            "review_date": cells[0],
            "repo": cells[1],
            "reviewer": cells[2],
            "artifact_path": artifact_path,
            "action_tracker_path": _extract_path(cells[5]),
            "status": cells[6],
            "follow_up_due_date": follow_up_due_date,
            "follow_up_trigger": follow_up_trigger,
        }

    return entries


def test_registry_validates_against_schema() -> None:
    registry = _load_registry()
    assert SCHEMA_PATH.is_file(), "docs/reviews/review-registry.schema.json is missing"
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(registry), key=lambda err: err.json_path)
    if errors:
        formatted = "\n".join(f"{err.json_path or '$'}: {err.message}" for err in errors)
        pytest.fail(f"Schema validation errors:\n{formatted}")


def test_artifact_paths_exist() -> None:
    registry = _load_registry()
    for entry in registry:
        path = REPO_ROOT / entry["artifact_path"]
        assert path.is_file(), f"Artifact missing: {entry['artifact_path']}"


def test_action_tracker_paths_exist() -> None:
    registry = _load_registry()
    for entry in registry:
        path = REPO_ROOT / entry["action_tracker_path"]
        assert path.is_file(), f"Action tracker missing: {entry['action_tracker_path']}"


def test_review_ids_are_unique() -> None:
    registry = _load_registry()
    ids = [entry["review_id"] for entry in registry]
    duplicates = [rid for rid, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate review_id values found: {', '.join(duplicates)}"


def test_follow_up_due_dates_are_iso_when_present() -> None:
    registry = _load_registry()
    for entry in registry:
        due = entry.get("follow_up_due_date")
        if due is None:
            continue
        assert DATE_PATTERN.match(due), f"follow_up_due_date must be YYYY-MM-DD: {entry}"
        iso_date = date.fromisoformat(due)
        assert isinstance(iso_date, date)


def test_markdown_registry_aligns_with_json() -> None:
    markdown_entries = _parse_markdown_registry()
    registry = _load_registry()

    for entry in registry:
        markdown_entry = markdown_entries.get(entry["artifact_path"])
        if markdown_entry is None:
            continue

        assert markdown_entry["review_date"] == entry["review_date"], f"Date mismatch for {entry['review_id']}"
        assert markdown_entry["repo"] == entry["repo"], f"Repo mismatch for {entry['review_id']}"
        assert markdown_entry["reviewer"] == entry["reviewer"], f"Reviewer mismatch for {entry['review_id']}"
        assert markdown_entry["status"] == entry["status"], f"Status mismatch for {entry['review_id']}"
        assert markdown_entry["action_tracker_path"] == entry["action_tracker_path"], f"Action tracker mismatch for {entry['review_id']}"

        md_due = markdown_entry.get("follow_up_due_date")
        json_due = entry.get("follow_up_due_date")
        assert md_due == json_due, f"follow_up_due_date mismatch for {entry['review_id']}"

        md_trigger = markdown_entry.get("follow_up_trigger", "").strip()
        assert md_trigger == entry["follow_up_trigger"], f"follow_up_trigger mismatch for {entry['review_id']}"
