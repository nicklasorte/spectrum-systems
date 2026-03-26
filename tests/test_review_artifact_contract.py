from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from scripts.validate_review_artifact import validate_markdown_metadata

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "review_artifact.schema.json"
EXAMPLE_PATH = REPO_ROOT / "contracts" / "examples" / "review_artifact.json"


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_example() -> dict:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def _validate(instance: dict) -> list[str]:
    validator = Draft202012Validator(_load_schema())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.path))
    return [f"{list(error.path) or ['root']}: {error.message}" for error in errors]


def test_review_artifact_example_validates() -> None:
    assert _validate(_load_example()) == []


@pytest.mark.parametrize(
    "field",
    [
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
    ],
)
def test_review_artifact_missing_required_fields_fails(field: str) -> None:
    instance = _load_example()
    instance.pop(field, None)
    assert _validate(instance), f"expected validation errors when missing {field}"


def test_review_artifact_invalid_enums_fail() -> None:
    instance = _load_example()
    instance["decision"] = "MAYBE"
    instance["trust_assessment"] = "UNSURE"
    instance["status"] = "pending"
    errors = _validate(instance)
    assert errors
    assert any("decision" in error for error in errors)
    assert any("trust_assessment" in error for error in errors)
    assert any("status" in error for error in errors)


def test_review_artifact_findings_require_canonical_fields() -> None:
    instance = _load_example()
    del instance["critical_findings"][0]["file"]
    errors = _validate(instance)
    assert errors
    assert any("file" in error for error in errors)




def test_review_artifact_finding_shape_is_canonical_and_legacy_free() -> None:
    instance = _load_example()
    finding = instance["critical_findings"][0]

    required_canonical_fields = {
        "id",
        "severity",
        "file",
        "function",
        "failure_mode",
        "impact",
        "minimal_fix",
    }
    assert required_canonical_fields.issubset(finding.keys())

    legacy_fields = {
        "finding_id",
        "title",
        "description",
        "why_dangerous",
        "location",
        "failure_scenario",
        "optional_improvements",
    }
    assert legacy_fields.isdisjoint(finding.keys())
    assert "optional_improvements" not in instance
    assert "watch_items" in instance and isinstance(instance["watch_items"], list)


def test_review_artifact_status_and_trust_assessment_use_canonical_values() -> None:
    instance = _load_example()
    assert instance["status"] == "final"
    assert instance["trust_assessment"] in {"high", "medium", "low"}

def test_markdown_review_metadata_validation(tmp_path: Path) -> None:
    review_md = tmp_path / "2026-03-23-governed_prompt_queue-codex_review.md"
    review_md.write_text(
        """---
module: governed_prompt_queue
review_type: codex_review
review_date: 2026-03-23
reviewer: Codex
decision: FAIL
trust_assessment: medium
status: final
related_plan: docs/review-actions/PLAN-REVIEW-ARTIFACT-STANDARD-2026-03-23.md
---

## Scope
- contracts/schemas/review_artifact.schema.json
""",
        encoding="utf-8",
    )
    assert validate_markdown_metadata(review_md) == []

    invalid_md = tmp_path / "2026-03-23-governed_prompt_queue-invalid.md"
    invalid_md.write_text(
        """---
module: governed_prompt_queue
review_type: codex_review
review_date: 2026/03/23
reviewer: Codex
decision: MAYBE
trust_assessment: NO
status: open
---
""",
        encoding="utf-8",
    )
    errors = validate_markdown_metadata(invalid_md)
    assert errors
    assert any("related_plan" in error for error in errors)
    assert any("decision" in error for error in errors)
    assert any("trust_assessment" in error for error in errors)
    assert any("status" in error for error in errors)
    assert any("review_date" in error for error in errors)
