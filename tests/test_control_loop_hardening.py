"""
Tests for Control Loop Hardening (evaluation → work item contract, review artifact
schema, eval directory usage, and validation scripts).

Covers:
- Evaluation manifest schema accepts new action_required / linked_work_item_id / rationale fields
- Evaluation manifest schema accepts "partial" as a valid status
- validate_evaluation_contract.py enforces contract rules
- schemas/review-artifact.schema.json exists and is valid JSON Schema
- A well-formed review artifact passes schema validation
- A review artifact with missing required fields is rejected
- scripts/validate_review_artifacts.py exists and runs
- eval/ is the canonical directory; evals/ has a deprecation notice
- docs/artifact-lifecycle.md exists and contains key lifecycle stages
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

# ---------------------------------------------------------------------------
# Load schemas and examples once at module level
# ---------------------------------------------------------------------------

_EVAL_MANIFEST_SCHEMA_PATH = (
    REPO_ROOT / "contracts" / "schemas" / "evaluation_manifest.schema.json"
)
_EVAL_MANIFEST_EXAMPLE_PATH = (
    REPO_ROOT / "contracts" / "examples" / "evaluation_manifest.json"
)
_REVIEW_ARTIFACT_SCHEMA_PATH = REPO_ROOT / "schemas" / "review-artifact.schema.json"

_EVAL_MANIFEST_SCHEMA: Dict[str, Any] = json.loads(
    _EVAL_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8")
)
_EVAL_MANIFEST_EXAMPLE: Dict[str, Any] = json.loads(
    _EVAL_MANIFEST_EXAMPLE_PATH.read_text(encoding="utf-8")
)


# ---------------------------------------------------------------------------
# A. Evaluation manifest schema — new control-loop fields
# ---------------------------------------------------------------------------


def test_evaluation_manifest_schema_accepts_action_required_true() -> None:
    """action_required=true with linked_work_item_id should be valid."""
    instance = copy.deepcopy(_EVAL_MANIFEST_EXAMPLE)
    instance["action_required"] = True
    instance["linked_work_item_id"] = "WI-0001"
    Draft202012Validator(_EVAL_MANIFEST_SCHEMA).validate(instance)


def test_evaluation_manifest_schema_accepts_action_required_false_with_rationale() -> None:
    """action_required=false with rationale should be valid."""
    instance = copy.deepcopy(_EVAL_MANIFEST_EXAMPLE)
    instance["action_required"] = False
    instance["linked_work_item_id"] = None
    instance["rationale"] = "All criteria passed; no corrective action needed."
    Draft202012Validator(_EVAL_MANIFEST_SCHEMA).validate(instance)


def test_evaluation_manifest_schema_accepts_partial_status() -> None:
    """'partial' must be a valid status enum value."""
    instance = copy.deepcopy(_EVAL_MANIFEST_EXAMPLE)
    instance["status"] = "partial"
    Draft202012Validator(_EVAL_MANIFEST_SCHEMA).validate(instance)


def test_evaluation_manifest_example_still_valid_after_schema_update() -> None:
    """The existing example (with new fields) must still pass schema validation."""
    Draft202012Validator(_EVAL_MANIFEST_SCHEMA).validate(_EVAL_MANIFEST_EXAMPLE)


def test_evaluation_manifest_example_has_action_required() -> None:
    """The example manifest must include the new action_required field."""
    assert "action_required" in _EVAL_MANIFEST_EXAMPLE, (
        "contracts/examples/evaluation_manifest.json must include action_required"
    )


def test_evaluation_manifest_schema_rejects_non_boolean_action_required() -> None:
    """action_required must be a boolean, not a string."""
    instance = copy.deepcopy(_EVAL_MANIFEST_EXAMPLE)
    instance["action_required"] = "yes"
    with pytest.raises(ValidationError):
        Draft202012Validator(_EVAL_MANIFEST_SCHEMA).validate(instance)


# ---------------------------------------------------------------------------
# A. validate_evaluation_contract.py — contract enforcement
# ---------------------------------------------------------------------------


from validate_evaluation_contract import validate_contract  # noqa: E402


def test_contract_passes_for_action_required_true_with_work_item() -> None:
    instance = {
        "artifact_id": "EVAL-TEST-001",
        "action_required": True,
        "linked_work_item_id": "WI-0001",
    }
    errors = validate_contract(instance)
    assert errors == []


def test_contract_passes_for_action_required_false_with_rationale() -> None:
    instance = {
        "artifact_id": "EVAL-TEST-002",
        "action_required": False,
        "rationale": "All checks passed; no action needed.",
    }
    errors = validate_contract(instance)
    assert errors == []


def test_contract_fails_when_action_required_missing() -> None:
    """Missing action_required must produce a contract error."""
    instance = {"artifact_id": "EVAL-TEST-003"}
    errors = validate_contract(instance)
    assert any("action_required" in e for e in errors)


def test_contract_fails_when_action_required_true_but_no_work_item() -> None:
    """action_required=true without a work item ID must fail."""
    instance = {
        "artifact_id": "EVAL-TEST-004",
        "action_required": True,
        "linked_work_item_id": None,
    }
    errors = validate_contract(instance)
    assert any("linked_work_item_id" in e for e in errors)


def test_contract_fails_when_action_required_true_and_work_item_empty() -> None:
    """action_required=true with an empty string work item ID must fail."""
    instance = {
        "artifact_id": "EVAL-TEST-005",
        "action_required": True,
        "linked_work_item_id": "",
    }
    errors = validate_contract(instance)
    assert any("linked_work_item_id" in e for e in errors)


def test_contract_fails_when_action_required_false_but_no_rationale() -> None:
    """action_required=false without rationale must fail."""
    instance = {
        "artifact_id": "EVAL-TEST-006",
        "action_required": False,
    }
    errors = validate_contract(instance)
    assert any("rationale" in e for e in errors)


def test_contract_fails_when_action_required_false_and_rationale_empty() -> None:
    """action_required=false with empty rationale must fail."""
    instance = {
        "artifact_id": "EVAL-TEST-007",
        "action_required": False,
        "rationale": "   ",
    }
    errors = validate_contract(instance)
    assert any("rationale" in e for e in errors)


def test_validate_evaluation_contract_script_exists() -> None:
    assert (REPO_ROOT / "scripts" / "validate_evaluation_contract.py").is_file()


def test_validate_evaluation_contract_script_runs_on_example() -> None:
    """The script must exit 0 for the existing valid example."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "validate_evaluation_contract.py"),
         str(_EVAL_MANIFEST_EXAMPLE_PATH)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"validate_evaluation_contract.py failed on example:\n{result.stdout}\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# C. Review artifact schema
# ---------------------------------------------------------------------------


def _load_review_schema() -> Dict[str, Any]:
    return json.loads(_REVIEW_ARTIFACT_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_review_artifact_schema_exists() -> None:
    assert _REVIEW_ARTIFACT_SCHEMA_PATH.is_file(), (
        "schemas/review-artifact.schema.json is missing"
    )


def test_review_artifact_schema_is_valid_json_schema() -> None:
    schema = _load_review_schema()
    Draft202012Validator.check_schema(schema)


def test_review_artifact_valid_instance_passes() -> None:
    schema = _load_review_schema()
    instance = {
        "review_id": "2026-03-17-governance-audit",
        "source": "claude",
        "timestamp": "2026-03-17T12:00:00Z",
        "repo": "nicklasorte/spectrum-systems",
        "scope": "governance architecture",
        "findings": [
            {
                "id": "F-1",
                "severity": "high",
                "category": "governance",
                "description": "Missing evaluation contract enforcement.",
            }
        ],
        "recommendations": [
            {
                "id": "REC-1",
                "statement": "Add validate_evaluation_contract.py to CI.",
                "priority": "high",
                "related_findings": ["F-1"],
            }
        ],
        "related_work_items": ["WI-0001"],
    }
    Draft202012Validator(schema).validate(instance)


@pytest.mark.parametrize(
    "missing_field",
    ["review_id", "source", "timestamp", "repo", "scope", "findings", "recommendations"],
)
def test_review_artifact_missing_required_field_rejected(missing_field: str) -> None:
    schema = _load_review_schema()
    instance = {
        "review_id": "2026-03-17-governance-audit",
        "source": "claude",
        "timestamp": "2026-03-17T12:00:00Z",
        "repo": "nicklasorte/spectrum-systems",
        "scope": "governance architecture",
        "findings": [],
        "recommendations": [],
    }
    instance.pop(missing_field)
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(instance)


def test_review_artifact_invalid_source_rejected() -> None:
    schema = _load_review_schema()
    instance = {
        "review_id": "2026-03-17-governance-audit",
        "source": "robot",  # invalid
        "timestamp": "2026-03-17T12:00:00Z",
        "repo": "nicklasorte/spectrum-systems",
        "scope": "governance architecture",
        "findings": [],
        "recommendations": [],
    }
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(instance)


def test_review_artifact_invalid_finding_severity_rejected() -> None:
    schema = _load_review_schema()
    instance = {
        "review_id": "2026-03-17-governance-audit",
        "source": "human",
        "timestamp": "2026-03-17T12:00:00Z",
        "repo": "nicklasorte/spectrum-systems",
        "scope": "governance architecture",
        "findings": [
            {
                "id": "F-1",
                "severity": "extreme",  # invalid
                "category": "governance",
                "description": "Some finding.",
            }
        ],
        "recommendations": [],
    }
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(instance)


def test_review_artifact_work_item_id_pattern_enforced() -> None:
    """related_work_items must follow WI-NNNN pattern."""
    schema = _load_review_schema()
    instance = {
        "review_id": "2026-03-17-test",
        "source": "system",
        "timestamp": "2026-03-17T12:00:00Z",
        "repo": "nicklasorte/spectrum-systems",
        "scope": "test",
        "findings": [],
        "recommendations": [],
        "related_work_items": ["WI-BAD"],  # invalid pattern
    }
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(instance)


# ---------------------------------------------------------------------------
# C. validate_review_artifacts.py script
# ---------------------------------------------------------------------------


def test_validate_review_artifacts_script_exists() -> None:
    assert (REPO_ROOT / "scripts" / "validate_review_artifacts.py").is_file()


def test_validate_review_artifacts_script_runs(tmp_path: Path) -> None:
    """Script should run without crashing on an empty directory."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "validate_review_artifacts.py"),
         "--dirs", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"validate_review_artifacts.py failed:\n{result.stdout}\n{result.stderr}"
    )


def test_validate_review_artifacts_passes_valid_file(tmp_path: Path) -> None:
    """Script must exit 0 for a canonical review artifact with markdown pair."""
    review = {
        "review_id": "REV-TEST-REPO-VALIDATOR",
        "module": "validator",
        "review_type": "repo_level",
        "review_date": "2026-03-27",
        "reviewer": "Codex",
        "decision": "FAIL",
        "trust_assessment": "medium",
        "status": "final",
        "scope": ["scripts/validate_review_artifacts.py"],
        "related_plan": "docs/review-actions/PLAN-PQX-FIX-REVIEW-VALIDATOR-ALIGNMENT-2026-03-27.md",
        "critical_findings": [
            {
                "id": "F-001",
                "severity": "low",
                "file": "scripts/validate_review_artifacts.py",
                "function": "main",
                "failure_mode": "Synthetic finding for validator script test.",
                "impact": "Synthetic impact.",
                "minimal_fix": "Synthetic fix.",
            }
        ],
        "required_fixes": [
            {
                "fix_id": "FIX-001",
                "description": "Synthetic required fix.",
                "priority": "P2",
            }
        ],
        "watch_items": ["Synthetic watch item"],
        "failure_mode_summary": "Synthetic summary",
    }
    review_file = tmp_path / "test-review.json"
    review_file.write_text(json.dumps(review), encoding="utf-8")

    markdown_file = tmp_path / "test-review.md"
    markdown_file.write_text(
        """---
module: validator
review_type: repo_level
review_date: 2026-03-27
reviewer: Codex
decision: FAIL
trust_assessment: medium
status: final
related_plan: docs/review-actions/PLAN-PQX-FIX-REVIEW-VALIDATOR-ALIGNMENT-2026-03-27.md
---

## Scope
- test

## Decision
- test

## Trust Assessment
- test

## Critical Findings
- test

## Required Fixes
- test

## Optional Improvements
- test

## Failure Mode Summary
- test
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "validate_review_artifacts.py"),
         str(review_file)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"Validation failed for valid review artifact:\n{result.stdout}\n{result.stderr}"
    )


def test_validate_review_artifacts_fails_invalid_file(tmp_path: Path) -> None:
    """Script must exit non-zero for an invalid canonical review artifact."""
    bad_review = {
        "review_id": "REV-TEST-REPO-INVALID",
        "module": "validator",
        "review_type": "repo_level",
        "review_date": "2026-03-27",
        "reviewer": "Codex",
        "decision": "FAIL",
        "trust_assessment": "medium",
        "status": "final",
        "scope": ["scripts/validate_review_artifacts.py"],
        "related_plan": "docs/review-actions/PLAN-PQX-FIX-REVIEW-VALIDATOR-ALIGNMENT-2026-03-27.md",
        "critical_findings": [],
        "required_fixes": [],
        "watch_items": [],
        "failure_mode_summary": "",
    }
    bad_file = tmp_path / "bad-review.json"
    bad_file.write_text(json.dumps(bad_review), encoding="utf-8")

    bad_markdown = tmp_path / "bad-review.md"
    bad_markdown.write_text("---\nmodule: validator\n---\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "validate_review_artifacts.py"),
         str(bad_file)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode != 0, (
        "validate_review_artifacts.py should fail for invalid review artifact"
    )


# ---------------------------------------------------------------------------
# B. eval/ is canonical; evals/ has deprecation notice
# ---------------------------------------------------------------------------


def test_eval_dir_exists_and_is_canonical() -> None:
    eval_dir = REPO_ROOT / "eval"
    assert eval_dir.is_dir(), "eval/ directory must exist"
    readme = eval_dir / "README.md"
    assert readme.is_file(), "eval/README.md must exist"
    content = readme.read_text(encoding="utf-8")
    assert "canonical" in content.lower(), (
        "eval/README.md must identify eval/ as the canonical evaluation directory"
    )


def test_evals_dir_has_deprecation_notice() -> None:
    evals_dir = REPO_ROOT / "evals"
    assert evals_dir.is_dir(), "evals/ directory must exist (for deprecation notice)"
    framework = evals_dir / "evals-framework.md"
    assert framework.is_file(), "evals/evals-framework.md must exist"
    content = framework.read_text(encoding="utf-8").lower()
    assert "deprecated" in content, (
        "evals/evals-framework.md must contain a deprecation notice"
    )


# ---------------------------------------------------------------------------
# D. Artifact lifecycle doc
# ---------------------------------------------------------------------------


def test_artifact_lifecycle_doc_exists() -> None:
    assert (REPO_ROOT / "docs" / "artifact-lifecycle.md").is_file(), (
        "docs/artifact-lifecycle.md must exist"
    )


def test_artifact_lifecycle_doc_contains_key_stages() -> None:
    content = (REPO_ROOT / "docs" / "artifact-lifecycle.md").read_text(encoding="utf-8")
    for stage in ["input", "transformation", "evaluation", "work item", "resolution", "re-evaluation"]:
        assert stage.lower() in content.lower(), (
            f"docs/artifact-lifecycle.md must mention the '{stage}' lifecycle stage"
        )


def test_artifact_lifecycle_doc_references_validation_scripts() -> None:
    content = (REPO_ROOT / "docs" / "artifact-lifecycle.md").read_text(encoding="utf-8")
    assert "validate_evaluation_contract.py" in content
    assert "validate_review_artifacts.py" in content
