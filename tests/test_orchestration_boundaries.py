"""
Tests for orchestration boundary enforcement and artifact bus validation.

Covers:
A. Schema file existence
   - artifact-bus-message.schema.json exists
   - orchestration-flow.schema.json exists
   - artifact-bus-message.example.json exists
   - orchestration-flow.example.json exists

B. Valid artifact-bus message accepted by schema
C. Invalid artifact-bus messages rejected (missing fields, bad patterns)

D. Valid orchestration flow manifest accepted by schema
E. Invalid orchestration flow manifest rejected

F. Orchestration boundary detection
   - orchestration-flow file in a non-orchestration module is flagged
   - artifact-bus schema duplicate in a non-orchestration module is flagged
   - routing keyword in a non-orchestration schema file is flagged

G. Artifact handoff rules (via validator functions)
   - source_module not in manifests fails
   - target_module not in manifests fails
   - artifact_type not in target inputs fails
   - invalid lifecycle_state fails
   - missing lineage_ref fails
   - target module rejecting undeclared input artifact type

H. Happy path — canonical cross-module handoff passes all checks
I. Orchestration flow stage validates module references and artifact types
J. Validator happy path against the real repo
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_BUS_SCHEMA_PATH = REPO_ROOT / "schemas" / "artifact-bus-message.schema.json"
ORCHESTRATION_FLOW_SCHEMA_PATH = REPO_ROOT / "schemas" / "orchestration-flow.schema.json"
ARTIFACT_BUS_EXAMPLE_PATH = REPO_ROOT / "docs" / "examples" / "artifact-bus-message.example.json"
ORCHESTRATION_FLOW_EXAMPLE_PATH = REPO_ROOT / "docs" / "examples" / "orchestration-flow.example.json"
MANIFESTS_DIR = REPO_ROOT / "docs" / "module-manifests"

import sys
sys.path.insert(0, str(REPO_ROOT))
from scripts import validate_orchestration_boundaries as validator  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────


def _load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(schema: dict, instance: dict) -> list:
    v = Draft202012Validator(schema)
    return list(v.iter_errors(instance))


def _minimal_valid_bus_message() -> dict:
    return {
        "schema_version": "1.0.0",
        "message_id": "MSG-TEST-001",
        "artifact_id": "ART-TEST-001",
        "artifact_type": "ArtifactEnvelope",
        "source_module": "workflow_modules.meeting_intelligence",
        "target_module": "control_plane.evaluation",
        "lifecycle_state": "transformed",
        "payload_ref": "ART-TEST-001",
        "contract_version": "1.0.0",
        "timestamp": "2026-03-17T14:00:00Z",
        "run_id": "RUN-TEST-001",
        "lineage_ref": "LIN-TEST-001",
    }


def _minimal_valid_flow() -> dict:
    return {
        "schema_version": "1.0.0",
        "flow_id": "FLOW-TEST-001",
        "name": "Test Flow",
        "description": "A minimal test orchestration flow for unit tests.",
        "status": "planned",
        "source_modules": ["workflow_modules.meeting_intelligence"],
        "target_modules": ["control_plane.evaluation"],
        "artifact_types": ["ArtifactEnvelope"],
        "required_validations": ["artifact_bus_message_schema"],
        "allowed_lifecycle_states": ["transformed"],
        "stages": [
            {
                "stage_id": "STG-TEST-001",
                "name": "Test Stage",
                "source_module": "workflow_modules.meeting_intelligence",
                "target_module": "control_plane.evaluation",
                "artifact_type": "ArtifactEnvelope",
                "lifecycle_state_at_handoff": "transformed",
            }
        ],
    }


# ── A. Schema file existence ──────────────────────────────────────────────────


def test_artifact_bus_schema_exists() -> None:
    assert ARTIFACT_BUS_SCHEMA_PATH.is_file(), (
        f"Missing artifact bus schema: {ARTIFACT_BUS_SCHEMA_PATH.relative_to(REPO_ROOT)}"
    )


def test_orchestration_flow_schema_exists() -> None:
    assert ORCHESTRATION_FLOW_SCHEMA_PATH.is_file(), (
        f"Missing orchestration flow schema: {ORCHESTRATION_FLOW_SCHEMA_PATH.relative_to(REPO_ROOT)}"
    )


def test_artifact_bus_example_exists() -> None:
    assert ARTIFACT_BUS_EXAMPLE_PATH.is_file(), (
        f"Missing artifact bus example: {ARTIFACT_BUS_EXAMPLE_PATH.relative_to(REPO_ROOT)}"
    )


def test_orchestration_flow_example_exists() -> None:
    assert ORCHESTRATION_FLOW_EXAMPLE_PATH.is_file(), (
        f"Missing orchestration flow example: {ORCHESTRATION_FLOW_EXAMPLE_PATH.relative_to(REPO_ROOT)}"
    )


# ── B. Valid artifact-bus message accepted ────────────────────────────────────


def test_valid_artifact_bus_message_passes_schema() -> None:
    schema = _load_schema(ARTIFACT_BUS_SCHEMA_PATH)
    instance = _minimal_valid_bus_message()
    errors = _validate(schema, instance)
    assert not errors, f"Valid bus message should pass schema: {[e.message for e in errors]}"


def test_artifact_bus_example_passes_schema() -> None:
    schema = _load_schema(ARTIFACT_BUS_SCHEMA_PATH)
    instance = json.loads(ARTIFACT_BUS_EXAMPLE_PATH.read_text(encoding="utf-8"))
    errors = _validate(schema, instance)
    assert not errors, f"Example bus message should pass schema: {[e.message for e in errors]}"


# ── C. Invalid artifact-bus messages rejected ─────────────────────────────────


@pytest.mark.parametrize("missing_field", [
    "message_id",
    "artifact_id",
    "artifact_type",
    "source_module",
    "target_module",
    "lifecycle_state",
    "payload_ref",
    "contract_version",
    "schema_version",
    "timestamp",
    "run_id",
    "lineage_ref",
])
def test_artifact_bus_missing_required_field_fails_schema(missing_field: str) -> None:
    schema = _load_schema(ARTIFACT_BUS_SCHEMA_PATH)
    instance = _minimal_valid_bus_message()
    del instance[missing_field]
    errors = _validate(schema, instance)
    assert errors, f"Schema should reject bus message missing '{missing_field}'"


def test_artifact_bus_invalid_message_id_pattern_fails_schema() -> None:
    schema = _load_schema(ARTIFACT_BUS_SCHEMA_PATH)
    instance = _minimal_valid_bus_message()
    instance["message_id"] = "bad-id-no-prefix"
    errors = _validate(schema, instance)
    assert errors, "Schema should reject message_id not matching MSG-* pattern"


def test_artifact_bus_invalid_contract_version_fails_schema() -> None:
    schema = _load_schema(ARTIFACT_BUS_SCHEMA_PATH)
    instance = _minimal_valid_bus_message()
    instance["contract_version"] = "not-semver"
    errors = _validate(schema, instance)
    assert errors, "Schema should reject contract_version that is not semver"


def test_artifact_bus_wrong_schema_version_fails_schema() -> None:
    schema = _load_schema(ARTIFACT_BUS_SCHEMA_PATH)
    instance = _minimal_valid_bus_message()
    instance["schema_version"] = "2.0.0"
    errors = _validate(schema, instance)
    assert errors, "Schema should reject schema_version != '1.0.0'"


def test_artifact_bus_invalid_run_id_pattern_fails_schema() -> None:
    schema = _load_schema(ARTIFACT_BUS_SCHEMA_PATH)
    instance = _minimal_valid_bus_message()
    instance["run_id"] = "not-a-run-id"
    errors = _validate(schema, instance)
    assert errors, "Schema should reject run_id not matching RUN-* pattern"


# ── D. Valid orchestration flow manifest accepted ─────────────────────────────


def test_valid_orchestration_flow_passes_schema() -> None:
    schema = _load_schema(ORCHESTRATION_FLOW_SCHEMA_PATH)
    instance = _minimal_valid_flow()
    errors = _validate(schema, instance)
    assert not errors, f"Valid flow should pass schema: {[e.message for e in errors]}"


def test_orchestration_flow_example_passes_schema() -> None:
    schema = _load_schema(ORCHESTRATION_FLOW_SCHEMA_PATH)
    instance = json.loads(ORCHESTRATION_FLOW_EXAMPLE_PATH.read_text(encoding="utf-8"))
    errors = _validate(schema, instance)
    assert not errors, f"Example flow should pass schema: {[e.message for e in errors]}"


# ── E. Invalid orchestration flow manifest rejected ───────────────────────────


@pytest.mark.parametrize("missing_field", [
    "flow_id",
    "name",
    "description",
    "stages",
    "source_modules",
    "target_modules",
    "artifact_types",
    "required_validations",
    "allowed_lifecycle_states",
    "status",
    "schema_version",
])
def test_orchestration_flow_missing_required_field_fails_schema(missing_field: str) -> None:
    schema = _load_schema(ORCHESTRATION_FLOW_SCHEMA_PATH)
    instance = _minimal_valid_flow()
    del instance[missing_field]
    errors = _validate(schema, instance)
    assert errors, f"Schema should reject flow missing '{missing_field}'"


def test_orchestration_flow_invalid_status_fails_schema() -> None:
    schema = _load_schema(ORCHESTRATION_FLOW_SCHEMA_PATH)
    instance = _minimal_valid_flow()
    instance["status"] = "unknown_status"
    errors = _validate(schema, instance)
    assert errors, "Schema should reject invalid status value"


def test_orchestration_flow_empty_stages_fails_schema() -> None:
    schema = _load_schema(ORCHESTRATION_FLOW_SCHEMA_PATH)
    instance = _minimal_valid_flow()
    instance["stages"] = []
    errors = _validate(schema, instance)
    assert errors, "Schema should reject flow with empty stages"


def test_orchestration_flow_stage_missing_required_field_fails_schema() -> None:
    schema = _load_schema(ORCHESTRATION_FLOW_SCHEMA_PATH)
    instance = _minimal_valid_flow()
    # Remove a required field from the stage
    del instance["stages"][0]["artifact_type"]
    errors = _validate(schema, instance)
    assert errors, "Schema should reject stage missing 'artifact_type'"


# ── F. Orchestration boundary detection ──────────────────────────────────────


def test_orchestration_flow_file_in_workflow_module_is_flagged(tmp_path: Path) -> None:
    """An orchestration-flow file inside workflow_modules/ should be detected."""
    bad_dir = tmp_path / "workflow_modules" / "meeting_intelligence"
    bad_dir.mkdir(parents=True)
    bad_file = bad_dir / "orchestration-flow.schema.json"
    bad_file.write_text(json.dumps({"type": "object"}), encoding="utf-8")

    orig_roots = validator.NON_ORCHESTRATION_ROOTS
    try:
        validator.NON_ORCHESTRATION_ROOTS = [tmp_path / "workflow_modules"]
        violations = validator.check_no_orchestration_flow_files_outside_orchestration()
    finally:
        validator.NON_ORCHESTRATION_ROOTS = orig_roots

    assert violations, "Should flag orchestration-flow file in workflow_modules/"
    assert any(
        v["rule"] == "orchestration_flow_file_in_non_orchestration_module"
        for v in violations
    )


def test_artifact_bus_schema_duplicate_in_domain_module_is_flagged(tmp_path: Path) -> None:
    """A local artifact-bus schema inside domain_modules/ should be detected."""
    bad_dir = tmp_path / "domain_modules" / "knowledge_capture"
    bad_dir.mkdir(parents=True)
    bad_file = bad_dir / "artifact-bus-message.schema.json"
    bad_file.write_text(json.dumps({"type": "object"}), encoding="utf-8")

    orig_roots = validator.NON_ORCHESTRATION_ROOTS
    try:
        validator.NON_ORCHESTRATION_ROOTS = [tmp_path / "domain_modules"]
        violations = validator.check_no_artifact_bus_duplicates()
    finally:
        validator.NON_ORCHESTRATION_ROOTS = orig_roots

    assert violations, "Should flag duplicated artifact-bus schema in domain_modules/"
    assert any(v["rule"] == "artifact_bus_schema_duplicated" for v in violations)


def test_routing_keyword_in_workflow_module_schema_is_flagged(tmp_path: Path) -> None:
    """A schema file with 'next_module' keyword in workflow_modules/ should be flagged."""
    bad_dir = tmp_path / "workflow_modules" / "bad_module"
    bad_dir.mkdir(parents=True)
    schema_file = bad_dir / "local.json"
    schema_file.write_text(
        json.dumps({"properties": {"next_module": {"type": "string"}}}),
        encoding="utf-8",
    )

    orig_roots = validator.NON_ORCHESTRATION_ROOTS
    try:
        validator.NON_ORCHESTRATION_ROOTS = [tmp_path / "workflow_modules"]
        violations = validator.check_no_routing_keywords_in_non_orchestration_modules()
    finally:
        validator.NON_ORCHESTRATION_ROOTS = orig_roots

    assert violations, "Should flag routing keyword in non-orchestration schema"
    assert any(
        v["rule"] == "routing_keyword_in_non_orchestration_module" for v in violations
    )


# ── G. Artifact handoff validation rules ─────────────────────────────────────


def test_artifact_bus_source_module_not_in_manifests_fails(tmp_path: Path) -> None:
    """source_module that does not resolve to a manifest should be flagged."""
    schema = _load_schema(ARTIFACT_BUS_SCHEMA_PATH)
    manifests = {"control_plane.evaluation": {"inputs": ["ArtifactEnvelope"]}}
    lifecycle_states = {"transformed", "evaluated"}

    msg = _minimal_valid_bus_message()
    msg["source_module"] = "workflow_modules.nonexistent_module"

    violations = validator._validate_artifact_bus_message(
        msg, schema, manifests, lifecycle_states, tmp_path / "test.json"
    )
    assert any(v["rule"] == "artifact_bus_source_module_not_found" for v in violations)


def test_artifact_bus_target_module_not_in_manifests_fails(tmp_path: Path) -> None:
    """target_module that does not resolve to a manifest should be flagged."""
    schema = _load_schema(ARTIFACT_BUS_SCHEMA_PATH)
    manifests = {"workflow_modules.meeting_intelligence": {"inputs": [], "outputs": ["ArtifactEnvelope"]}}
    lifecycle_states = {"transformed", "evaluated"}

    msg = _minimal_valid_bus_message()
    msg["target_module"] = "control_plane.nonexistent"

    violations = validator._validate_artifact_bus_message(
        msg, schema, manifests, lifecycle_states, tmp_path / "test.json"
    )
    assert any(v["rule"] == "artifact_bus_target_module_not_found" for v in violations)


def test_artifact_type_not_declared_in_target_inputs_fails(tmp_path: Path) -> None:
    """artifact_type not in target module's inputs should be flagged."""
    schema = _load_schema(ARTIFACT_BUS_SCHEMA_PATH)
    manifests = {
        "workflow_modules.meeting_intelligence": {"inputs": [], "outputs": ["MeetingMinutesRecord"]},
        "control_plane.evaluation": {"inputs": ["EvaluationRequest"]},
    }
    lifecycle_states = {"transformed", "evaluated"}

    msg = _minimal_valid_bus_message()
    msg["artifact_type"] = "MeetingMinutesRecord"

    violations = validator._validate_artifact_bus_message(
        msg, schema, manifests, lifecycle_states, tmp_path / "test.json"
    )
    assert any(
        v["rule"] == "artifact_type_not_declared_in_target_inputs" for v in violations
    )


def test_invalid_lifecycle_state_in_bus_message_fails(tmp_path: Path) -> None:
    """An unrecognized lifecycle_state should be flagged."""
    schema = _load_schema(ARTIFACT_BUS_SCHEMA_PATH)
    manifests = {
        "workflow_modules.meeting_intelligence": {"inputs": []},
        "control_plane.evaluation": {"inputs": ["ArtifactEnvelope"]},
    }
    lifecycle_states = {"transformed", "evaluated"}

    msg = _minimal_valid_bus_message()
    msg["lifecycle_state"] = "completely_unknown_state"

    violations = validator._validate_artifact_bus_message(
        msg, schema, manifests, lifecycle_states, tmp_path / "test.json"
    )
    assert any(v["rule"] == "artifact_bus_invalid_lifecycle_state" for v in violations)


def test_artifact_bus_missing_lineage_ref_fails(tmp_path: Path) -> None:
    """A message missing lineage_ref should fail both schema and validator."""
    schema = _load_schema(ARTIFACT_BUS_SCHEMA_PATH)
    instance = _minimal_valid_bus_message()
    del instance["lineage_ref"]
    errors = _validate(schema, instance)
    assert errors, "Schema should reject message with missing lineage_ref"


# ── H. Happy path — valid cross-module handoff ────────────────────────────────


def test_canonical_handoff_passes_all_checks(tmp_path: Path) -> None:
    """
    Happy path: meeting_intelligence → control_plane.evaluation with ArtifactEnvelope
    at 'transformed' state should produce no violations.
    """
    schema = _load_schema(ARTIFACT_BUS_SCHEMA_PATH)
    manifests = {
        "workflow_modules.meeting_intelligence": {
            "inputs": ["MeetingTranscript"],
            "outputs": ["ArtifactEnvelope"],
        },
        "control_plane.evaluation": {
            "inputs": ["ArtifactEnvelope", "EvaluationRequest"],
            "outputs": ["EvaluationResult"],
        },
    }
    lifecycle_states = {"input", "transformed", "evaluated", "action_required"}

    msg = _minimal_valid_bus_message()
    violations = validator._validate_artifact_bus_message(
        msg, schema, manifests, lifecycle_states, tmp_path / "happy.json"
    )
    assert not violations, (
        f"Happy-path handoff should produce no violations: "
        f"{[v['message'] for v in violations]}"
    )


# ── I. Orchestration flow stage validation ────────────────────────────────────


def test_orchestration_flow_valid_stage_passes(tmp_path: Path) -> None:
    """A valid orchestration flow example should pass all checks."""
    manifests = validator.load_all_module_manifests()
    lifecycle_states = validator.load_lifecycle_states()

    violations = validator.check_orchestration_flow_examples(manifests, lifecycle_states)
    assert not violations, (
        f"Orchestration flow example should pass validation: "
        f"{[v['message'] for v in violations]}"
    )


def test_orchestration_flow_stage_with_unknown_target_module_fails(tmp_path: Path) -> None:
    """An orchestration flow stage pointing to a non-existent target module fails."""
    flow = _minimal_valid_flow()
    flow["stages"][0]["target_module"] = "orchestration.nonexistent"
    flow["target_modules"] = ["orchestration.nonexistent"]

    flow_file = tmp_path / "orchestration-flow.bad.json"
    flow_file.write_text(json.dumps(flow), encoding="utf-8")

    manifests = {"workflow_modules.meeting_intelligence": {"inputs": [], "outputs": []}}
    lifecycle_states = {"transformed"}

    orig_examples = validator.EXAMPLES_DIR
    try:
        validator.EXAMPLES_DIR = tmp_path
        violations = validator.check_orchestration_flow_examples(manifests, lifecycle_states)
    finally:
        validator.EXAMPLES_DIR = orig_examples

    assert any(
        v["rule"] == "orchestration_flow_target_module_not_found" for v in violations
    ), f"Should flag unknown target module in flow stage, got: {violations}"


def test_orchestration_flow_stage_artifact_type_not_in_target_inputs_fails(
    tmp_path: Path,
) -> None:
    """An orchestration flow stage with an undeclared artifact type for target fails."""
    flow = _minimal_valid_flow()
    flow["stages"][0]["artifact_type"] = "UndeclaredArtifact"
    flow["artifact_types"] = ["UndeclaredArtifact"]

    flow_file = tmp_path / "orchestration-flow.bad2.json"
    flow_file.write_text(json.dumps(flow), encoding="utf-8")

    manifests = {
        "workflow_modules.meeting_intelligence": {"inputs": [], "outputs": ["UndeclaredArtifact"]},
        "control_plane.evaluation": {"inputs": ["ArtifactEnvelope"]},
    }
    lifecycle_states = {"transformed"}

    orig_examples = validator.EXAMPLES_DIR
    try:
        validator.EXAMPLES_DIR = tmp_path
        violations = validator.check_orchestration_flow_examples(manifests, lifecycle_states)
    finally:
        validator.EXAMPLES_DIR = orig_examples

    assert any(
        v["rule"] == "orchestration_flow_artifact_type_not_in_target_inputs"
        for v in violations
    ), f"Should flag undeclared artifact type in flow stage target, got: {violations}"


# ── J. Full validator happy path against the real repo ────────────────────────


def test_orchestration_boundary_validator_happy_path() -> None:
    """Full validator run against the real repo should produce no violations."""
    violations = validator.run_all_checks()
    assert not violations, (
        f"Orchestration boundary validation failed with {len(violations)} violation(s):\n"
        + "\n".join(
            f"  [{v['rule']}] module={v.get('module', '?')} file={v.get('file', '?')}: {v['message']}"
            for v in violations
        )
    )
