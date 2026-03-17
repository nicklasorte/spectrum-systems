"""
Tests for the Evaluation & Evidence Spine (Prompt J).

Covers:
- evaluation_manifest.schema.json existence and self-validity
- contracts/examples/evaluation_manifest.json validates against schema
- Missing required fields are rejected
- Invalid status values are rejected
- Invalid readiness_level values are rejected
- Malformed evidence_refs are detected by the validation script
- governance/schemas/readiness_assessment.schema.json existence and self-validity
- governance/examples/evidence-bundle/readiness_assessment.json validates
- validate_evaluation_manifest script functions (validate_schema,
  validate_evidence_refs, validate_readiness_requirements, validate_manifest)
- Documentation files exist
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_evaluation_manifest import (  # noqa: E402
    validate_evidence_refs,
    validate_manifest,
    validate_readiness_requirements,
    validate_schema,
)

# ---------------------------------------------------------------------------
# Load schemas and examples once at module level
# ---------------------------------------------------------------------------

_EVAL_MANIFEST_SCHEMA: Dict[str, Any] = json.loads(
    (REPO_ROOT / "contracts" / "schemas" / "evaluation_manifest.schema.json").read_text(
        encoding="utf-8"
    )
)
_READINESS_ASSESSMENT_SCHEMA: Dict[str, Any] = json.loads(
    (
        REPO_ROOT / "governance" / "schemas" / "readiness_assessment.schema.json"
    ).read_text(encoding="utf-8")
)
_EVAL_MANIFEST_EXAMPLE: Dict[str, Any] = json.loads(
    (REPO_ROOT / "contracts" / "examples" / "evaluation_manifest.json").read_text(
        encoding="utf-8"
    )
)
_READINESS_ASSESSMENT_EXAMPLE: Dict[str, Any] = json.loads(
    (
        REPO_ROOT
        / "governance"
        / "examples"
        / "evidence-bundle"
        / "readiness_assessment.json"
    ).read_text(encoding="utf-8")
)


# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------


def test_evaluation_manifest_schema_exists() -> None:
    assert (
        REPO_ROOT / "contracts" / "schemas" / "evaluation_manifest.schema.json"
    ).is_file()


def test_readiness_assessment_schema_exists() -> None:
    assert (
        REPO_ROOT / "governance" / "schemas" / "readiness_assessment.schema.json"
    ).is_file()


def test_evaluation_manifest_example_exists() -> None:
    assert (
        REPO_ROOT / "contracts" / "examples" / "evaluation_manifest.json"
    ).is_file()


def test_readiness_assessment_example_exists() -> None:
    assert (
        REPO_ROOT
        / "governance"
        / "examples"
        / "evidence-bundle"
        / "readiness_assessment.json"
    ).is_file()


def test_evaluation_spine_doc_exists() -> None:
    assert (REPO_ROOT / "docs" / "evaluation-spine.md").is_file()


def test_evaluation_spine_report_exists() -> None:
    assert (
        REPO_ROOT / "docs" / "governance-reports" / "evaluation-spine-report.md"
    ).is_file()


def test_validate_evaluation_manifest_script_exists() -> None:
    assert (
        REPO_ROOT / "scripts" / "validate_evaluation_manifest.py"
    ).is_file()


# ---------------------------------------------------------------------------
# Schema self-validity
# ---------------------------------------------------------------------------


def test_evaluation_manifest_schema_is_valid_json_schema() -> None:
    Draft202012Validator.check_schema(_EVAL_MANIFEST_SCHEMA)


def test_readiness_assessment_schema_is_valid_json_schema() -> None:
    Draft202012Validator.check_schema(_READINESS_ASSESSMENT_SCHEMA)


# ---------------------------------------------------------------------------
# Valid example artifacts pass schema validation
# ---------------------------------------------------------------------------


def test_evaluation_manifest_example_is_valid() -> None:
    Draft202012Validator(_EVAL_MANIFEST_SCHEMA).validate(_EVAL_MANIFEST_EXAMPLE)


def test_readiness_assessment_example_is_valid() -> None:
    Draft202012Validator(_READINESS_ASSESSMENT_SCHEMA).validate(
        _READINESS_ASSESSMENT_EXAMPLE
    )


# ---------------------------------------------------------------------------
# Missing required fields are rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "artifact_type",
        "artifact_id",
        "artifact_version",
        "schema_version",
        "standards_version",
        "record_id",
        "run_id",
        "created_at",
        "created_by",
        "source_repo",
        "source_repo_version",
        "system_id",
        "evaluation_type",
        "evaluation_date",
        "evaluator",
        "criteria_applied",
        "artifact_set",
        "results_summary",
        "status",
        "readiness_level",
        "evidence_refs",
    ],
)
def test_evaluation_manifest_missing_required_field_rejected(field: str) -> None:
    instance = copy.deepcopy(_EVAL_MANIFEST_EXAMPLE)
    instance.pop(field, None)
    with pytest.raises(ValidationError):
        Draft202012Validator(_EVAL_MANIFEST_SCHEMA).validate(instance)


@pytest.mark.parametrize(
    "field",
    [
        "run_id",
        "system_id",
        "evaluated_at",
        "readiness_level",
        "evaluation_summary",
    ],
)
def test_readiness_assessment_missing_required_field_rejected(field: str) -> None:
    instance = copy.deepcopy(_READINESS_ASSESSMENT_EXAMPLE)
    instance.pop(field, None)
    with pytest.raises(ValidationError):
        Draft202012Validator(_READINESS_ASSESSMENT_SCHEMA).validate(instance)


# ---------------------------------------------------------------------------
# Invalid status values are rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_status", ["unknown", "ok", "error", "pending", ""])
def test_evaluation_manifest_invalid_status_rejected(bad_status: str) -> None:
    instance = copy.deepcopy(_EVAL_MANIFEST_EXAMPLE)
    instance["status"] = bad_status
    with pytest.raises(ValidationError):
        Draft202012Validator(_EVAL_MANIFEST_SCHEMA).validate(instance)


# ---------------------------------------------------------------------------
# Invalid readiness_level values are rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_readiness",
    ["not-ready", "approved", "complete", "ready", ""],
)
def test_evaluation_manifest_invalid_readiness_rejected(bad_readiness: str) -> None:
    instance = copy.deepcopy(_EVAL_MANIFEST_EXAMPLE)
    instance["readiness_level"] = bad_readiness
    with pytest.raises(ValidationError):
        Draft202012Validator(_EVAL_MANIFEST_SCHEMA).validate(instance)


@pytest.mark.parametrize(
    "bad_readiness",
    ["not-ready", "approved", "complete", ""],
)
def test_readiness_assessment_invalid_readiness_rejected(bad_readiness: str) -> None:
    instance = copy.deepcopy(_READINESS_ASSESSMENT_EXAMPLE)
    instance["readiness_level"] = bad_readiness
    with pytest.raises(ValidationError):
        Draft202012Validator(_READINESS_ASSESSMENT_SCHEMA).validate(instance)


# ---------------------------------------------------------------------------
# Invalid evidence_ref ref_type is rejected by schema
# ---------------------------------------------------------------------------


def test_evaluation_manifest_invalid_evidence_ref_type_rejected() -> None:
    instance = copy.deepcopy(_EVAL_MANIFEST_EXAMPLE)
    instance["evidence_refs"] = [{"ref_type": "bad_type", "ref_id": "x"}]
    with pytest.raises(ValidationError):
        Draft202012Validator(_EVAL_MANIFEST_SCHEMA).validate(instance)


# ---------------------------------------------------------------------------
# validate_evidence_refs — malformed refs detected
# ---------------------------------------------------------------------------


def test_validate_evidence_refs_missing_ref_type() -> None:
    instance: Dict[str, Any] = {"evidence_refs": [{"ref_id": "some-id"}]}
    errors = validate_evidence_refs(instance)
    assert any("ref_type" in e for e in errors)


def test_validate_evidence_refs_missing_ref_id() -> None:
    instance = {"evidence_refs": [{"ref_type": "run_manifest"}]}
    errors = validate_evidence_refs(instance)
    assert any("ref_id" in e for e in errors)


def test_validate_evidence_refs_not_a_list() -> None:
    instance = {"evidence_refs": "not-a-list"}
    errors = validate_evidence_refs(instance)
    assert any("array" in e for e in errors)


def test_validate_evidence_refs_non_object_entry() -> None:
    instance = {"evidence_refs": ["not-a-dict"]}
    errors = validate_evidence_refs(instance)
    assert any("object" in e for e in errors)


def test_validate_evidence_refs_ref_path_not_found(tmp_path: Path) -> None:
    instance = {
        "evidence_refs": [
            {"ref_type": "run_manifest", "ref_id": "x", "ref_path": "missing.json"}
        ]
    }
    errors = validate_evidence_refs(instance, bundle_path=tmp_path)
    assert any("missing.json" in e for e in errors)


def test_validate_evidence_refs_ref_path_found(tmp_path: Path) -> None:
    manifest_file = tmp_path / "run_manifest.json"
    manifest_file.write_text("{}", encoding="utf-8")
    instance = {
        "evidence_refs": [
            {
                "ref_type": "run_manifest",
                "ref_id": "x",
                "ref_path": "run_manifest.json",
            }
        ]
    }
    errors = validate_evidence_refs(instance, bundle_path=tmp_path)
    assert errors == []


# ---------------------------------------------------------------------------
# validate_schema function
# ---------------------------------------------------------------------------


def test_validate_schema_returns_empty_for_valid_instance() -> None:
    errors = validate_schema(_EVAL_MANIFEST_EXAMPLE)
    assert errors == []


def test_validate_schema_returns_errors_for_missing_fields() -> None:
    bad_instance: Dict[str, Any] = {"artifact_type": "evaluation_manifest"}
    errors = validate_schema(bad_instance)
    assert len(errors) > 0


def test_validate_schema_returns_errors_for_bad_artifact_id() -> None:
    instance = copy.deepcopy(_EVAL_MANIFEST_EXAMPLE)
    instance["artifact_id"] = "bad-id"  # does not match ^EVAL-[A-Z0-9._-]+$
    errors = validate_schema(instance)
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# validate_readiness_requirements function
# ---------------------------------------------------------------------------


def test_governance_ready_without_evidence_refs_fails() -> None:
    instance = copy.deepcopy(_EVAL_MANIFEST_EXAMPLE)
    instance["readiness_level"] = "governance-ready"
    instance["evidence_refs"] = []
    errors = validate_readiness_requirements(instance)
    assert any("governance-ready" in e for e in errors)


def test_decision_support_ready_without_evidence_refs_fails() -> None:
    instance = copy.deepcopy(_EVAL_MANIFEST_EXAMPLE)
    instance["readiness_level"] = "decision-support-ready"
    instance["evidence_refs"] = []
    errors = validate_readiness_requirements(instance)
    assert any("decision-support-ready" in e for e in errors)


def test_fail_status_without_criteria_applied_fails() -> None:
    instance = copy.deepcopy(_EVAL_MANIFEST_EXAMPLE)
    instance["status"] = "fail"
    instance["criteria_applied"] = []
    errors = validate_readiness_requirements(instance)
    assert any("criteria_applied" in e for e in errors)


def test_valid_instance_produces_no_readiness_errors() -> None:
    errors = validate_readiness_requirements(_EVAL_MANIFEST_EXAMPLE)
    assert errors == []


def test_internal_review_without_evidence_refs_is_ok() -> None:
    instance = copy.deepcopy(_EVAL_MANIFEST_EXAMPLE)
    instance["readiness_level"] = "internal-review"
    instance["evidence_refs"] = []
    errors = validate_readiness_requirements(instance)
    assert errors == []


# ---------------------------------------------------------------------------
# validate_manifest (end-to-end)
# ---------------------------------------------------------------------------


def test_validate_manifest_passes_for_valid_example(tmp_path: Path) -> None:
    manifest_file = tmp_path / "evaluation_manifest.json"
    manifest_file.write_text(
        json.dumps(_EVAL_MANIFEST_EXAMPLE), encoding="utf-8"
    )
    result = validate_manifest(manifest_file)
    assert result["status"] == "pass", result["errors"]


def test_validate_manifest_fails_for_missing_run_id(tmp_path: Path) -> None:
    instance = copy.deepcopy(_EVAL_MANIFEST_EXAMPLE)
    instance.pop("run_id")
    manifest_file = tmp_path / "eval.json"
    manifest_file.write_text(json.dumps(instance), encoding="utf-8")
    result = validate_manifest(manifest_file)
    assert result["status"] == "fail"
    assert any("run_id" in e for e in result["errors"])


def test_validate_manifest_fails_for_bad_json(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ not valid json", encoding="utf-8")
    result = validate_manifest(bad_file)
    assert result["status"] == "fail"
    assert any("Cannot load manifest" in e for e in result["errors"])


def test_validate_manifest_returns_evaluation_id_and_run_id(tmp_path: Path) -> None:
    manifest_file = tmp_path / "evaluation_manifest.json"
    manifest_file.write_text(
        json.dumps(_EVAL_MANIFEST_EXAMPLE), encoding="utf-8"
    )
    result = validate_manifest(manifest_file)
    assert result["evaluation_id"] == _EVAL_MANIFEST_EXAMPLE["artifact_id"]
    assert result["run_id"] == _EVAL_MANIFEST_EXAMPLE["run_id"]


def test_validate_manifest_with_bundle_path_missing_ref(tmp_path: Path) -> None:
    instance = copy.deepcopy(_EVAL_MANIFEST_EXAMPLE)
    # ref_path points to a file that does not exist in the bundle
    instance["evidence_refs"] = [
        {"ref_type": "run_manifest", "ref_id": "x", "ref_path": "run_manifest.json"}
    ]
    manifest_file = tmp_path / "eval.json"
    manifest_file.write_text(json.dumps(instance), encoding="utf-8")

    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    # run_manifest.json is NOT created in bundle_dir

    result = validate_manifest(manifest_file, bundle_path=bundle_dir)
    assert result["status"] == "fail"
    assert any("run_manifest.json" in e for e in result["errors"])
