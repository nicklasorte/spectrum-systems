"""Tests for the work item schema, generator script, and generated output."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "work-item.schema.json"
OUTPUT_JSON = REPO_ROOT / "governance" / "work-items" / "work-items.json"
GENERATOR_SCRIPT = REPO_ROOT / "scripts" / "generate_work_items.py"

VALID_SEVERITIES = {"critical", "high", "medium", "low"}
VALID_STATUSES = {"open", "in-progress", "resolved", "deferred"}
VALID_SOURCE_TYPES = {"review", "evaluation", "observability"}
WI_ID_PATTERN = r"^WI-[0-9]{4}$"


# ---------------------------------------------------------------------------
# Schema file existence and structural validity
# ---------------------------------------------------------------------------


def test_work_item_schema_exists() -> None:
    assert SCHEMA_PATH.is_file(), "schemas/work-item.schema.json is missing"


def test_work_item_schema_is_valid_json() -> None:
    assert SCHEMA_PATH.is_file()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema.get("type") == "object"
    assert "properties" in schema
    assert "required" in schema


def test_work_item_schema_required_fields() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    required = set(schema.get("required", []))
    expected_required = {
        "work_item_id",
        "source_type",
        "source_id",
        "title",
        "description",
        "severity",
        "category",
        "status",
        "priority_score",
        "created_at",
        "updated_at",
    }
    missing = expected_required - required
    assert not missing, f"Work item schema missing required fields: {missing}"


def test_work_item_schema_valid_item_passes() -> None:
    """A well-formed work item must validate against the schema."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    item = {
        "work_item_id": "WI-0001",
        "source_type": "review",
        "source_id": "2026-03-15-ecosystem-constitution-audit",
        "repo": "nicklasorte/spectrum-systems",
        "finding_id": "RC-1",
        "title": "Remove production Python package from governance repo",
        "description": "spectrum_systems/study_runner/ violates CLAUDE.md boundary.",
        "severity": "critical",
        "category": "architecture-boundary",
        "status": "open",
        "priority_score": 100,
        "blocking": True,
        "created_at": "2026-03-15",
        "updated_at": "2026-03-17",
        "due_date": "2026-03-30",
        "related_artifacts": ["spectrum_systems/", "run_study.py"],
        "suggested_issue_title": "Remove production Python package from governance repo",
        "suggested_labels": ["architecture", "priority-critical"],
    }
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(item))
    assert not errors, f"Valid item failed schema validation: {errors}"


def test_work_item_schema_rejects_invalid_severity() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    item = {
        "work_item_id": "WI-0001",
        "source_type": "review",
        "source_id": "test-review",
        "title": "Test item",
        "description": "A test description.",
        "severity": "INVALID",
        "category": "governance",
        "status": "open",
        "priority_score": 50,
        "created_at": "2026-03-17",
        "updated_at": "2026-03-17",
    }
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(item))
    assert errors, "Schema should reject invalid severity"


def test_work_item_schema_rejects_invalid_status() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    item = {
        "work_item_id": "WI-0001",
        "source_type": "review",
        "source_id": "test-review",
        "title": "Test item",
        "description": "A test description.",
        "severity": "high",
        "category": "governance",
        "status": "pending",  # not in enum
        "priority_score": 50,
        "created_at": "2026-03-17",
        "updated_at": "2026-03-17",
    }
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(item))
    assert errors, "Schema should reject invalid status 'pending'"


def test_work_item_schema_rejects_out_of_range_priority() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    item = {
        "work_item_id": "WI-0001",
        "source_type": "review",
        "source_id": "test-review",
        "title": "Test item",
        "description": "A test description.",
        "severity": "high",
        "category": "governance",
        "status": "open",
        "priority_score": 999,  # out of range
        "created_at": "2026-03-17",
        "updated_at": "2026-03-17",
    }
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(item))
    assert errors, "Schema should reject priority_score > 100"


# ---------------------------------------------------------------------------
# Generator script
# ---------------------------------------------------------------------------


def test_generator_script_exists() -> None:
    assert GENERATOR_SCRIPT.is_file(), "scripts/generate_work_items.py is missing"


def test_generator_script_dry_run() -> None:
    """--dry-run must print valid JSON to stdout without writing files."""
    result = subprocess.run(
        [sys.executable, str(GENERATOR_SCRIPT), "--dry-run"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=True,
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "work_items" in output
    assert isinstance(output["work_items"], list)
    assert output["total_items"] == len(output["work_items"])


def test_generator_produces_outputs() -> None:
    """Running the script should create work-items.json and work-items-summary.md."""
    summary_path = REPO_ROOT / "governance" / "work-items" / "work-items-summary.md"

    subprocess.run(
        [sys.executable, str(GENERATOR_SCRIPT)],
        check=True,
        cwd=str(REPO_ROOT),
    )

    assert OUTPUT_JSON.is_file(), "work-items.json was not created"
    assert summary_path.is_file(), "work-items-summary.md was not created"


# ---------------------------------------------------------------------------
# Generated output file
# ---------------------------------------------------------------------------


def _load_output() -> dict:
    assert OUTPUT_JSON.is_file(), "governance/work-items/work-items.json is missing — run generate_work_items.py"
    return json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))


def test_output_structure() -> None:
    output = _load_output()
    assert "schema_version" in output
    assert "generated_at" in output
    assert "total_items" in output
    assert "work_items" in output
    assert isinstance(output["work_items"], list)
    assert output["total_items"] == len(output["work_items"])


def test_output_is_non_empty() -> None:
    output = _load_output()
    assert output["total_items"] > 0, "work-items.json must contain at least one work item"


def test_output_work_item_ids_are_unique() -> None:
    output = _load_output()
    ids = [item["work_item_id"] for item in output["work_items"]]
    assert len(ids) == len(set(ids)), "Duplicate work_item_id values found"


def test_output_work_item_ids_are_sequential() -> None:
    """IDs must follow WI-0001, WI-0002, … pattern without gaps."""
    import re

    output = _load_output()
    for idx, item in enumerate(output["work_items"], start=1):
        expected = f"WI-{idx:04d}"
        assert item["work_item_id"] == expected, (
            f"Expected {expected} but got {item['work_item_id']} at position {idx}"
        )


def test_output_all_items_have_required_fields() -> None:
    output = _load_output()
    required = {
        "work_item_id",
        "source_type",
        "source_id",
        "title",
        "description",
        "severity",
        "category",
        "status",
        "priority_score",
        "created_at",
        "updated_at",
    }
    for item in output["work_items"]:
        missing = required - item.keys()
        assert not missing, f"Work item {item.get('work_item_id')} missing fields: {missing}"


def test_output_severities_are_valid() -> None:
    output = _load_output()
    for item in output["work_items"]:
        assert item["severity"] in VALID_SEVERITIES, (
            f"{item['work_item_id']}: invalid severity '{item['severity']}'"
        )


def test_output_statuses_are_valid() -> None:
    output = _load_output()
    for item in output["work_items"]:
        assert item["status"] in VALID_STATUSES, (
            f"{item['work_item_id']}: invalid status '{item['status']}'"
        )


def test_output_source_types_are_valid() -> None:
    output = _load_output()
    for item in output["work_items"]:
        assert item["source_type"] in VALID_SOURCE_TYPES, (
            f"{item['work_item_id']}: invalid source_type '{item['source_type']}'"
        )


def test_output_priority_scores_in_range() -> None:
    output = _load_output()
    for item in output["work_items"]:
        score = item.get("priority_score", -1)
        assert 1 <= score <= 100, (
            f"{item['work_item_id']}: priority_score {score} out of range [1, 100]"
        )


def test_output_sorted_by_priority() -> None:
    """Items must be sorted by priority_score descending."""
    output = _load_output()
    scores = [item["priority_score"] for item in output["work_items"]]
    assert scores == sorted(scores, reverse=True), "work-items.json is not sorted by priority_score desc"


def test_output_all_items_validate_against_schema() -> None:
    """Every work item in the output must validate against the work-item schema."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    output = _load_output()
    errors_found: list[str] = []
    for item in output["work_items"]:
        item_errors = list(validator.iter_errors(item))
        for err in item_errors:
            errors_found.append(f"{item.get('work_item_id')}: {err.json_path}: {err.message}")
    assert not errors_found, "Schema validation errors in work-items.json:\n" + "\n".join(errors_found)


def test_output_has_critical_items() -> None:
    """At least one critical work item must be present given the existing review artifacts."""
    output = _load_output()
    critical = [item for item in output["work_items"] if item["severity"] == "critical"]
    assert critical, "Expected at least one critical work item from existing review artifacts"


def test_output_source_ids_non_empty() -> None:
    output = _load_output()
    for item in output["work_items"]:
        assert item.get("source_id", "").strip(), (
            f"{item['work_item_id']}: source_id must be non-empty"
        )


def test_output_no_duplicate_source_finding_pairs() -> None:
    """No two work items should have the same (source_id, finding_id) pair."""
    output = _load_output()
    seen: set[tuple[str, str]] = set()
    for item in output["work_items"]:
        key = (item.get("source_id", ""), item.get("finding_id", ""))
        if key[1]:  # only check items with a finding_id
            assert key not in seen, (
                f"Duplicate (source_id, finding_id) pair {key} in {item['work_item_id']}"
            )
            seen.add(key)
