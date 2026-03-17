"""
Tests for lifecycle enforcement and the data backbone.

Covers:
A. Lifecycle enforcer
   - valid transition accepted
   - invalid transition rejected
   - unknown state rejected
   - missing required fields rejected

B. Canonical schemas (JSON Schema validation)
   - valid artifact_metadata accepted
   - invalid artifact_metadata rejected (missing fields / bad lifecycle_state)
   - valid lineage record accepted
   - valid evaluation_result accepted
   - invalid evaluation_result rejected
   - valid work_item accepted

C. Enforcement rules (artifact_emitter)
   - missing metadata fails
   - missing lineage fails
   - missing evaluation fails
   - action_required=True without work item fails
   - action_required=True with missing linked_work_item_id fails

D. Happy path
   artifact → evaluation → work item → resolution → re-evaluation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Paths to canonical schemas
ARTIFACT_METADATA_SCHEMA = REPO_ROOT / "shared" / "artifact_models" / "artifact_metadata.schema.json"
LINEAGE_SCHEMA = REPO_ROOT / "shared" / "lineage" / "lineage.schema.json"
EVALUATION_RESULT_SCHEMA = REPO_ROOT / "shared" / "evaluation" / "evaluation_result.schema.json"
WORK_ITEM_SCHEMA = REPO_ROOT / "shared" / "work_items" / "work_item.schema.json"

# Lifecycle definition paths
LIFECYCLE_STATES_PATH = REPO_ROOT / "control_plane" / "lifecycle" / "lifecycle_states.json"
LIFECYCLE_TRANSITIONS_PATH = REPO_ROOT / "control_plane" / "lifecycle" / "lifecycle_transitions.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_schema(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(schema: Dict[str, Any], instance: Dict[str, Any]) -> list:
    validator = jsonschema.Draft202012Validator(schema)
    return list(validator.iter_errors(instance))


# ---------------------------------------------------------------------------
# A. Lifecycle definition files exist and are well-formed
# ---------------------------------------------------------------------------

def test_lifecycle_states_file_exists() -> None:
    assert LIFECYCLE_STATES_PATH.is_file(), "lifecycle_states.json is missing"


def test_lifecycle_transitions_file_exists() -> None:
    assert LIFECYCLE_TRANSITIONS_PATH.is_file(), "lifecycle_transitions.json is missing"


def test_lifecycle_states_contains_required_states() -> None:
    doc = json.loads(LIFECYCLE_STATES_PATH.read_text(encoding="utf-8"))
    states = {s["state"] for s in doc["states"]}
    required = {"input", "transformed", "evaluated", "action_required", "in_progress", "resolved", "re_evaluated", "closed"}
    missing = required - states
    assert not missing, f"lifecycle_states.json missing states: {missing}"


def test_lifecycle_transitions_covers_core_paths() -> None:
    doc = json.loads(LIFECYCLE_TRANSITIONS_PATH.read_text(encoding="utf-8"))
    pairs = {(t["from"], t["to"]) for t in doc["transitions"]}
    required = {
        ("input", "transformed"),
        ("transformed", "evaluated"),
        ("evaluated", "action_required"),
        ("evaluated", "closed"),
        ("action_required", "in_progress"),
        ("in_progress", "resolved"),
        ("resolved", "re_evaluated"),
    }
    missing = required - pairs
    assert not missing, f"lifecycle_transitions.json missing transitions: {missing}"


# ---------------------------------------------------------------------------
# A. LifecycleEnforcer unit tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def enforcer():
    from control_plane.lifecycle.lifecycle_enforcer import LifecycleEnforcer
    return LifecycleEnforcer()


def test_valid_transition_input_to_transformed(enforcer) -> None:
    """input → transformed must succeed when required fields are present."""
    artifact = {
        "artifact_id": "ARTIFACT-001",
        "artifact_type": "engine_output",
        "module_origin": "test-engine",
        "run_id": "run-test-001",
    }
    enforcer.validate_transition(artifact, "input", "transformed")  # must not raise


def test_valid_transition_transformed_to_evaluated(enforcer) -> None:
    artifact = {
        "artifact_id": "ARTIFACT-001",
        "artifact_type": "engine_output",
        "run_id": "run-test-001",
    }
    enforcer.validate_transition(artifact, "transformed", "evaluated")  # must not raise


def test_valid_transition_evaluated_to_closed(enforcer) -> None:
    artifact = {
        "evaluation_id": "EVAL-001",
        "action_required": False,
        "rationale": "All criteria met, no action needed.",
    }
    enforcer.validate_transition(artifact, "evaluated", "closed")  # must not raise


def test_invalid_transition_input_to_evaluated_rejected(enforcer) -> None:
    """Skipping the 'transformed' state must be rejected."""
    from control_plane.lifecycle.lifecycle_enforcer import LifecycleViolationError
    artifact = {"artifact_id": "ARTIFACT-001", "artifact_type": "engine_output", "run_id": "run-001"}
    with pytest.raises(LifecycleViolationError, match="Invalid lifecycle transition"):
        enforcer.validate_transition(artifact, "input", "evaluated")


def test_invalid_transition_backward_rejected(enforcer) -> None:
    """Backward transitions (e.g. evaluated → input) must be rejected."""
    from control_plane.lifecycle.lifecycle_enforcer import LifecycleViolationError
    artifact = {"artifact_id": "ARTIFACT-001"}
    with pytest.raises(LifecycleViolationError, match="Invalid lifecycle transition"):
        enforcer.validate_transition(artifact, "evaluated", "input")


def test_unknown_state_rejected(enforcer) -> None:
    """An unrecognised state name must raise LifecycleViolationError."""
    from control_plane.lifecycle.lifecycle_enforcer import LifecycleViolationError
    artifact = {"artifact_id": "ARTIFACT-001"}
    with pytest.raises(LifecycleViolationError, match="Unknown lifecycle state"):
        enforcer.validate_transition(artifact, "nonexistent", "transformed")


def test_missing_required_fields_blocks_transition(enforcer) -> None:
    """A transition must be blocked when required fields are absent from the artifact."""
    from control_plane.lifecycle.lifecycle_enforcer import LifecycleViolationError
    # input → transformed requires artifact_id, artifact_type, module_origin, run_id
    artifact = {"artifact_id": "ARTIFACT-001"}  # missing artifact_type, module_origin, run_id
    with pytest.raises(LifecycleViolationError, match="missing required fields"):
        enforcer.validate_transition(artifact, "input", "transformed")


def test_allowed_next_states_from_evaluated(enforcer) -> None:
    allowed = enforcer.allowed_next_states("evaluated")
    assert "action_required" in allowed
    assert "closed" in allowed


def test_is_terminal_closed(enforcer) -> None:
    assert enforcer.is_terminal("closed") is True


def test_is_terminal_input(enforcer) -> None:
    assert enforcer.is_terminal("input") is False


# ---------------------------------------------------------------------------
# B. Canonical schema validation
# ---------------------------------------------------------------------------

class TestArtifactMetadataSchema:
    def _valid(self) -> Dict[str, Any]:
        return {
            "artifact_id": "ARTIFACT-001",
            "artifact_type": "engine_output",
            "module_origin": "test-engine",
            "created_at": "2026-03-17T00:00:00+00:00",
            "lifecycle_state": "input",
            "contract_version": "1.0.0",
            "schema_version": "1.0.0",
        }

    def test_valid_instance_passes(self) -> None:
        schema = _load_schema(ARTIFACT_METADATA_SCHEMA)
        errors = _validate(schema, self._valid())
        assert not errors, f"Valid metadata failed schema: {errors}"

    def test_missing_required_field_rejected(self) -> None:
        schema = _load_schema(ARTIFACT_METADATA_SCHEMA)
        instance = self._valid()
        del instance["lifecycle_state"]
        errors = _validate(schema, instance)
        assert errors, "Schema should reject metadata missing lifecycle_state"

    def test_invalid_lifecycle_state_rejected(self) -> None:
        schema = _load_schema(ARTIFACT_METADATA_SCHEMA)
        instance = self._valid()
        instance["lifecycle_state"] = "unknown_state"
        errors = _validate(schema, instance)
        assert errors, "Schema should reject an unknown lifecycle_state"

    def test_invalid_contract_version_format_rejected(self) -> None:
        schema = _load_schema(ARTIFACT_METADATA_SCHEMA)
        instance = self._valid()
        instance["contract_version"] = "not-semver"
        errors = _validate(schema, instance)
        assert errors, "Schema should reject non-semver contract_version"


class TestLineageSchema:
    def _valid(self) -> Dict[str, Any]:
        return {
            "artifact_id": "ARTIFACT-001",
            "parent_artifacts": [],
            "producing_module": "test-engine",
            "run_id": "run-test-001",
            "timestamp": "2026-03-17T00:00:00+00:00",
        }

    def test_valid_instance_passes(self) -> None:
        schema = _load_schema(LINEAGE_SCHEMA)
        errors = _validate(schema, self._valid())
        assert not errors

    def test_missing_run_id_rejected(self) -> None:
        schema = _load_schema(LINEAGE_SCHEMA)
        instance = self._valid()
        del instance["run_id"]
        errors = _validate(schema, instance)
        assert errors

    def test_with_parent_artifacts(self) -> None:
        schema = _load_schema(LINEAGE_SCHEMA)
        instance = self._valid()
        instance["parent_artifacts"] = ["PARENT-001", "PARENT-002"]
        errors = _validate(schema, instance)
        assert not errors


class TestEvaluationResultSchema:
    def _valid(self) -> Dict[str, Any]:
        return {
            "evaluation_id": "EVAL-001",
            "artifact_id": "ARTIFACT-001",
            "status": "pass",
            "action_required": False,
            "rationale": "All criteria met.",
        }

    def test_valid_instance_passes(self) -> None:
        schema = _load_schema(EVALUATION_RESULT_SCHEMA)
        errors = _validate(schema, self._valid())
        assert not errors

    def test_invalid_status_rejected(self) -> None:
        schema = _load_schema(EVALUATION_RESULT_SCHEMA)
        instance = self._valid()
        instance["status"] = "warning"  # not in enum
        errors = _validate(schema, instance)
        assert errors

    def test_missing_rationale_rejected(self) -> None:
        schema = _load_schema(EVALUATION_RESULT_SCHEMA)
        instance = self._valid()
        del instance["rationale"]
        errors = _validate(schema, instance)
        assert errors


class TestWorkItemSchema:
    def _valid(self) -> Dict[str, Any]:
        return {
            "work_item_id": "WI-ABC123",
            "source_artifact_id": "ARTIFACT-001",
            "status": "open",
            "priority": "high",
            "created_at": "2026-03-17T00:00:00+00:00",
        }

    def test_valid_instance_passes(self) -> None:
        schema = _load_schema(WORK_ITEM_SCHEMA)
        errors = _validate(schema, self._valid())
        assert not errors

    def test_invalid_priority_rejected(self) -> None:
        schema = _load_schema(WORK_ITEM_SCHEMA)
        instance = self._valid()
        instance["priority"] = "urgent"  # not in enum
        errors = _validate(schema, instance)
        assert errors

    def test_missing_source_artifact_id_rejected(self) -> None:
        schema = _load_schema(WORK_ITEM_SCHEMA)
        instance = self._valid()
        del instance["source_artifact_id"]
        errors = _validate(schema, instance)
        assert errors


# ---------------------------------------------------------------------------
# C. artifact_emitter factory and enforcement helpers
# ---------------------------------------------------------------------------

from shared.adapters.artifact_emitter import (  # noqa: E402
    create_artifact_metadata,
    create_evaluation_result,
    create_lineage_record,
    create_work_item,
    load_artifact_record,
    save_artifact_record,
    validate_action_required_has_work_item,
    validate_artifact_has_evaluation,
    validate_artifact_has_lineage,
    validate_artifact_has_metadata,
)


def test_create_artifact_metadata_valid() -> None:
    meta = create_artifact_metadata(
        artifact_id="ARTIFACT-001",
        artifact_type="engine_output",
        module_origin="test-engine",
        lifecycle_state="input",
        contract_version="1.0.0",
    )
    assert meta["artifact_id"] == "ARTIFACT-001"
    assert meta["lifecycle_state"] == "input"
    assert "created_at" in meta


def test_create_artifact_metadata_invalid_state() -> None:
    with pytest.raises(ValueError, match="lifecycle_state"):
        create_artifact_metadata(
            artifact_id="ARTIFACT-001",
            artifact_type="engine_output",
            module_origin="test-engine",
            lifecycle_state="nonexistent",
            contract_version="1.0.0",
        )


def test_create_artifact_metadata_empty_artifact_id() -> None:
    with pytest.raises(ValueError, match="artifact_id"):
        create_artifact_metadata(
            artifact_id="",
            artifact_type="engine_output",
            module_origin="test-engine",
            lifecycle_state="input",
            contract_version="1.0.0",
        )


def test_create_lineage_record_valid() -> None:
    record = create_lineage_record(
        artifact_id="ARTIFACT-001",
        parent_artifacts=["PARENT-001"],
        producing_module="test-engine",
        run_id="run-001",
    )
    assert record["artifact_id"] == "ARTIFACT-001"
    assert record["parent_artifacts"] == ["PARENT-001"]
    assert "timestamp" in record


def test_create_evaluation_result_no_action() -> None:
    result = create_evaluation_result(
        artifact_id="ARTIFACT-001",
        status="pass",
        action_required=False,
        rationale="All checks passed.",
    )
    assert result["action_required"] is False
    assert result["linked_work_item_id"] is None


def test_create_evaluation_result_action_required_needs_work_item() -> None:
    with pytest.raises(ValueError, match="linked_work_item_id"):
        create_evaluation_result(
            artifact_id="ARTIFACT-001",
            status="fail",
            action_required=True,
            rationale="Contract drift detected.",
        )


def test_create_evaluation_result_action_required_with_work_item() -> None:
    result = create_evaluation_result(
        artifact_id="ARTIFACT-001",
        status="fail",
        action_required=True,
        rationale="Contract drift detected.",
        linked_work_item_id="WI-ABCD",
    )
    assert result["linked_work_item_id"] == "WI-ABCD"


def test_create_work_item_valid() -> None:
    wi = create_work_item(
        source_artifact_id="ARTIFACT-001",
        priority="high",
    )
    assert wi["status"] == "open"
    assert "work_item_id" in wi


def test_create_work_item_invalid_priority() -> None:
    with pytest.raises(ValueError, match="priority"):
        create_work_item(source_artifact_id="ARTIFACT-001", priority="urgent")


# ---------------------------------------------------------------------------
# C. Persistence helpers (tmp_path fixtures)
# ---------------------------------------------------------------------------

def test_save_and_load_artifact_record(tmp_path: Path) -> None:
    record = {"artifact_id": "ARTIFACT-001", "lifecycle_state": "input"}
    path = save_artifact_record("artifacts", "ARTIFACT-001", record, data_root=tmp_path)
    assert path.is_file()
    loaded = load_artifact_record("artifacts", "ARTIFACT-001", data_root=tmp_path)
    assert loaded["artifact_id"] == "ARTIFACT-001"


def test_load_nonexistent_record_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_artifact_record("artifacts", "MISSING-001", data_root=tmp_path)


def test_save_unknown_store_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown store"):
        save_artifact_record("unknown_store", "ID-001", {}, data_root=tmp_path)


# ---------------------------------------------------------------------------
# C. Enforcement rules
# ---------------------------------------------------------------------------

def test_missing_metadata_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no metadata record"):
        validate_artifact_has_metadata("ARTIFACT-001", data_root=tmp_path)


def test_missing_lineage_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no lineage record"):
        validate_artifact_has_lineage("ARTIFACT-001", data_root=tmp_path)


def test_missing_evaluation_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no evaluation result"):
        validate_artifact_has_evaluation("ARTIFACT-001", data_root=tmp_path)


def test_action_required_without_work_item_fails(tmp_path: Path) -> None:
    evaluation = {
        "evaluation_id": "EVAL-001",
        "artifact_id": "ARTIFACT-001",
        "status": "fail",
        "action_required": True,
        "rationale": "Issue found.",
        "linked_work_item_id": "WI-MISSING",
    }
    # work item record does not exist in the store
    with pytest.raises(ValueError, match="work item 'WI-MISSING' does not exist"):
        validate_action_required_has_work_item(evaluation, data_root=tmp_path)


def test_action_required_missing_linked_id_fails(tmp_path: Path) -> None:
    evaluation = {
        "evaluation_id": "EVAL-001",
        "artifact_id": "ARTIFACT-001",
        "status": "fail",
        "action_required": True,
        "rationale": "Issue found.",
        "linked_work_item_id": None,
    }
    with pytest.raises(ValueError, match="linked_work_item_id is missing"):
        validate_action_required_has_work_item(evaluation, data_root=tmp_path)


def test_no_action_required_passes_work_item_check(tmp_path: Path) -> None:
    evaluation = {
        "evaluation_id": "EVAL-001",
        "artifact_id": "ARTIFACT-001",
        "status": "pass",
        "action_required": False,
        "rationale": "All good.",
        "linked_work_item_id": None,
    }
    # Must not raise
    validate_action_required_has_work_item(evaluation, data_root=tmp_path)


# ---------------------------------------------------------------------------
# D. Happy path: artifact → evaluation → work item → resolution → re-evaluation
# ---------------------------------------------------------------------------

def test_happy_path_full_lifecycle(tmp_path: Path) -> None:
    """Exercise the complete lifecycle path end-to-end using the emitter and enforcer."""
    from control_plane.lifecycle.lifecycle_enforcer import LifecycleEnforcer

    enforcer = LifecycleEnforcer()
    artifact_id = "ARTIFACT-HAPPY-001"

    # 1. Emit artifact metadata (input stage)
    meta = create_artifact_metadata(
        artifact_id=artifact_id,
        artifact_type="engine_output",
        module_origin="test-engine",
        lifecycle_state="input",
        contract_version="1.0.0",
        run_id="run-happy-001",
    )
    save_artifact_record("artifacts", artifact_id, meta, data_root=tmp_path)

    # 2. Emit lineage
    lineage = create_lineage_record(
        artifact_id=artifact_id,
        parent_artifacts=[],
        producing_module="test-engine",
        run_id="run-happy-001",
    )
    save_artifact_record("lineage", artifact_id, lineage, data_root=tmp_path)

    # 3. Validate metadata and lineage present
    validate_artifact_has_metadata(artifact_id, data_root=tmp_path)
    validate_artifact_has_lineage(artifact_id, data_root=tmp_path)

    # 4. Transition input → transformed
    artifact_doc = {**meta, "module_origin": "test-engine"}
    enforcer.validate_transition(artifact_doc, "input", "transformed")

    # 5. Transition transformed → evaluated
    enforcer.validate_transition(artifact_doc, "transformed", "evaluated")

    # 6. Emit evaluation result (action required)
    wi = create_work_item(source_artifact_id=artifact_id, priority="high")
    save_artifact_record("work_items", wi["work_item_id"], wi, data_root=tmp_path)

    eval_result = create_evaluation_result(
        artifact_id=artifact_id,
        status="fail",
        action_required=True,
        rationale="Contract drift detected during evaluation.",
        linked_work_item_id=wi["work_item_id"],
    )
    save_artifact_record("evaluations", artifact_id, eval_result, data_root=tmp_path)

    # 7. Enforce: action_required → work item must exist
    validate_action_required_has_work_item(eval_result, data_root=tmp_path)

    # 8. Transition evaluated → action_required
    eval_artifact_doc = {
        "evaluation_id": eval_result["evaluation_id"],
        "action_required": True,
        "linked_work_item_id": wi["work_item_id"],
    }
    enforcer.validate_transition(eval_artifact_doc, "evaluated", "action_required")

    # 9. Transition action_required → in_progress
    wi_doc = {**wi, "source_artifact_id": artifact_id}
    enforcer.validate_transition(wi_doc, "action_required", "in_progress")

    # 10. Resolve: transition in_progress → resolved
    wi["status"] = "resolved"
    wi["resolution_notes"] = "Contract updated to match canonical version."
    enforcer.validate_transition(wi, "in_progress", "resolved")

    # 11. Transition resolved → re_evaluated
    enforcer.validate_transition(artifact_doc, "resolved", "re_evaluated")

    # 12. Re-evaluation passes: re_evaluated → closed
    reeval_doc = {
        "evaluation_id": "EVAL-REEVAL-001",
        "action_required": False,
        "rationale": "Contract drift resolved. All criteria now met.",
    }
    enforcer.validate_transition(reeval_doc, "re_evaluated", "closed")

    # 13. Confirm closed is terminal
    assert enforcer.is_terminal("closed") is True
