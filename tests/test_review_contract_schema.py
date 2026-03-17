"""
Tests for standards/review-contract.schema.json

Covers:
  - Schema file exists and is valid JSON
  - Required top-level fields are declared
  - Verdict enum contains exactly GO, GO_WITH_FIXES, NO_GO
  - Finding category enum contains all required values
  - Finding severity enum contains critical, high, medium, low
  - Fix type enum contains patch, refactor, redesign
  - Failure scenario likelihood/impact enums are valid
  - Valid review output passes schema validation
  - Missing required fields fail schema validation
  - Invalid verdict fails schema validation
  - Invalid finding severity fails schema validation
  - Invalid finding category fails schema validation
  - Invalid fix_type fails schema validation
  - Minimal valid document (empty findings list) passes
  - Empty findings list with all other required fields passes
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "standards" / "review-contract.schema.json"
SAMPLE_OUTPUT_PATH = REPO_ROOT / "reviews" / "output" / "sample.json"

_REQUIRED_TOP_LEVEL_FIELDS = [
    "review_id",
    "scope_id",
    "review_type",
    "reviewed_at",
    "verdict",
    "findings",
]

_VALID_VERDICTS = {"GO", "GO_WITH_FIXES", "NO_GO"}
_VALID_SEVERITIES = {"critical", "high", "medium", "low"}
_VALID_CATEGORIES = {
    "architecture",
    "contract",
    "validation",
    "alignment",
    "extraction-quality",
    "silent-failure",
    "golden-path",
    "traceability",
    "test",
}
_VALID_FIX_TYPES = {"patch", "refactor", "redesign"}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_sample() -> dict:
    return json.loads(SAMPLE_OUTPUT_PATH.read_text(encoding="utf-8"))


def validate(instance: dict) -> list[str]:
    schema = load_schema()
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        errors.append(error.message)
    return errors


# ─── Schema file integrity ────────────────────────────────────────────────────

class TestSchemaFileIntegrity:
    def test_schema_file_exists(self) -> None:
        assert SCHEMA_PATH.is_file(), f"Schema file not found at {SCHEMA_PATH}"

    def test_schema_is_valid_json(self) -> None:
        content = SCHEMA_PATH.read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert isinstance(parsed, dict)

    def test_schema_has_required_property(self) -> None:
        schema = load_schema()
        assert "required" in schema
        for field in _REQUIRED_TOP_LEVEL_FIELDS:
            assert field in schema["required"], (
                f"Field '{field}' missing from schema required list"
            )

    def test_verdict_enum_is_correct(self) -> None:
        schema = load_schema()
        verdict_enum = set(schema["properties"]["verdict"]["enum"])
        assert verdict_enum == _VALID_VERDICTS

    def test_finding_severity_enum_is_correct(self) -> None:
        schema = load_schema()
        severity_enum = set(
            schema["$defs"]["finding"]["properties"]["severity"]["enum"]
        )
        assert severity_enum == _VALID_SEVERITIES

    def test_finding_category_enum_is_correct(self) -> None:
        schema = load_schema()
        category_enum = set(
            schema["$defs"]["finding"]["properties"]["category"]["enum"]
        )
        assert category_enum == _VALID_CATEGORIES

    def test_finding_fix_type_enum_is_correct(self) -> None:
        schema = load_schema()
        fix_type_enum = set(
            schema["$defs"]["finding"]["properties"]["fix_type"]["enum"]
        )
        assert fix_type_enum == _VALID_FIX_TYPES

    def test_failure_scenario_likelihood_enum(self) -> None:
        schema = load_schema()
        likelihood_enum = set(
            schema["$defs"]["failure_scenario"]["properties"]["likelihood"]["enum"]
        )
        assert likelihood_enum == {"high", "medium", "low"}

    def test_failure_scenario_impact_enum(self) -> None:
        schema = load_schema()
        impact_enum = set(
            schema["$defs"]["failure_scenario"]["properties"]["impact"]["enum"]
        )
        assert impact_enum == {"high", "medium", "low"}


# ─── Valid documents ──────────────────────────────────────────────────────────

class TestValidDocuments:
    def test_sample_output_passes(self) -> None:
        assert SAMPLE_OUTPUT_PATH.is_file(), (
            f"Sample output not found at {SAMPLE_OUTPUT_PATH}"
        )
        errors = validate(load_sample())
        assert errors == [], f"Validation errors: {errors}"

    def test_minimal_valid_document_passes(self) -> None:
        minimal = {
            "review_id": "rev-test-scope-2026-01-01",
            "scope_id": "test_scope",
            "review_type": "architecture",
            "reviewed_at": "2026-01-01T00:00:00Z",
            "verdict": "GO",
            "findings": [],
        }
        errors = validate(minimal)
        assert errors == [], f"Validation errors: {errors}"

    def test_go_with_fixes_verdict_passes(self) -> None:
        doc = {
            "review_id": "rev-test-2026-01-01",
            "scope_id": "test",
            "review_type": "contract",
            "reviewed_at": "2026-01-01T00:00:00Z",
            "verdict": "GO_WITH_FIXES",
            "findings": [],
        }
        errors = validate(doc)
        assert errors == []

    def test_no_go_verdict_passes(self) -> None:
        doc = {
            "review_id": "rev-test-2026-01-01",
            "scope_id": "test",
            "review_type": "contract",
            "reviewed_at": "2026-01-01T00:00:00Z",
            "verdict": "NO_GO",
            "findings": [],
        }
        errors = validate(doc)
        assert errors == []

    def test_document_with_all_finding_categories_passes(self) -> None:
        findings = [
            {
                "finding_id": f"F-{str(i + 1).zfill(3)}",
                "severity": "low",
                "category": cat,
                "title": f"Finding in {cat}",
                "why_it_matters": "It matters.",
                "recommended_fix": "Fix it.",
                "fix_type": "patch",
                "downstream_risk": "Some risk.",
                "priority_rank": i + 1,
            }
            for i, cat in enumerate(sorted(_VALID_CATEGORIES))
        ]
        doc = {
            "review_id": "rev-all-cats-2026-01-01",
            "scope_id": "all_categories",
            "review_type": "architecture",
            "reviewed_at": "2026-01-01T00:00:00Z",
            "verdict": "GO",
            "findings": findings,
        }
        errors = validate(doc)
        assert errors == [], f"Validation errors: {errors}"

    def test_document_with_failure_scenarios_passes(self) -> None:
        doc = {
            "review_id": "rev-fs-2026-01-01",
            "scope_id": "test",
            "review_type": "architecture",
            "reviewed_at": "2026-01-01T00:00:00Z",
            "verdict": "GO",
            "findings": [],
            "failure_scenarios": [
                {
                    "scenario_id": "FS-001",
                    "description": "A known failure scenario.",
                    "likelihood": "medium",
                    "impact": "high",
                    "mitigation": "Apply mitigation X.",
                }
            ],
        }
        errors = validate(doc)
        assert errors == []

    def test_document_with_priority_fix_stack_passes(self) -> None:
        doc = {
            "review_id": "rev-pfs-2026-01-01",
            "scope_id": "test",
            "review_type": "architecture",
            "reviewed_at": "2026-01-01T00:00:00Z",
            "verdict": "GO_WITH_FIXES",
            "findings": [],
            "priority_fix_stack": ["F-001", "F-002"],
            "minimum_bar_to_proceed": "F-001 must be resolved.",
        }
        errors = validate(doc)
        assert errors == []


# ─── Invalid documents ────────────────────────────────────────────────────────

class TestInvalidDocuments:
    def _base_doc(self) -> dict:
        return {
            "review_id": "rev-test-2026-01-01",
            "scope_id": "test",
            "review_type": "architecture",
            "reviewed_at": "2026-01-01T00:00:00Z",
            "verdict": "GO",
            "findings": [],
        }

    @pytest.mark.parametrize("field", _REQUIRED_TOP_LEVEL_FIELDS)
    def test_missing_required_field_fails(self, field: str) -> None:
        doc = self._base_doc()
        del doc[field]
        errors = validate(doc)
        assert len(errors) > 0, f"Expected failure when '{field}' is missing"

    def test_invalid_verdict_fails(self) -> None:
        doc = {**self._base_doc(), "verdict": "MAYBE"}
        errors = validate(doc)
        assert len(errors) > 0

    @pytest.mark.parametrize("severity", ["extreme", "blocker", "info", ""])
    def test_invalid_finding_severity_fails(self, severity: str) -> None:
        doc = {
            **self._base_doc(),
            "findings": [
                {
                    "finding_id": "F-001",
                    "severity": severity,
                    "category": "architecture",
                    "title": "Test finding",
                    "why_it_matters": "Matters.",
                    "recommended_fix": "Fix it.",
                    "fix_type": "patch",
                    "downstream_risk": "Risk.",
                    "priority_rank": 1,
                }
            ],
        }
        errors = validate(doc)
        assert len(errors) > 0, f"Expected failure for invalid severity '{severity}'"

    def test_invalid_finding_category_fails(self) -> None:
        doc = {
            **self._base_doc(),
            "findings": [
                {
                    "finding_id": "F-001",
                    "severity": "high",
                    "category": "not-a-real-category",
                    "title": "Test finding",
                    "why_it_matters": "Matters.",
                    "recommended_fix": "Fix it.",
                    "fix_type": "patch",
                    "downstream_risk": "Risk.",
                    "priority_rank": 1,
                }
            ],
        }
        errors = validate(doc)
        assert len(errors) > 0

    def test_invalid_fix_type_fails(self) -> None:
        doc = {
            **self._base_doc(),
            "findings": [
                {
                    "finding_id": "F-001",
                    "severity": "high",
                    "category": "architecture",
                    "title": "Test finding",
                    "why_it_matters": "Matters.",
                    "recommended_fix": "Fix it.",
                    "fix_type": "hotfix",
                    "downstream_risk": "Risk.",
                    "priority_rank": 1,
                }
            ],
        }
        errors = validate(doc)
        assert len(errors) > 0

    def test_finding_missing_why_it_matters_fails(self) -> None:
        doc = {
            **self._base_doc(),
            "findings": [
                {
                    "finding_id": "F-001",
                    "severity": "high",
                    "category": "architecture",
                    "title": "Test finding",
                    # Missing why_it_matters
                    "recommended_fix": "Fix it.",
                    "fix_type": "patch",
                    "downstream_risk": "Risk.",
                    "priority_rank": 1,
                }
            ],
        }
        errors = validate(doc)
        assert len(errors) > 0

    def test_finding_negative_priority_rank_fails(self) -> None:
        doc = {
            **self._base_doc(),
            "findings": [
                {
                    "finding_id": "F-001",
                    "severity": "high",
                    "category": "architecture",
                    "title": "Test finding",
                    "why_it_matters": "Matters.",
                    "recommended_fix": "Fix it.",
                    "fix_type": "patch",
                    "downstream_risk": "Risk.",
                    "priority_rank": 0,  # Must be >= 1
                }
            ],
        }
        errors = validate(doc)
        assert len(errors) > 0

    def test_additional_top_level_property_fails(self) -> None:
        doc = {**self._base_doc(), "unexpected_field": "should not be allowed"}
        errors = validate(doc)
        assert len(errors) > 0
