"""
Tests for the SMA-01 v2 3LS Measurement + Loop Observability Layer contracts.

Covers positive and negative validation for:
- 3ls_system_measurement_record
- 3ls_loop_run_record
- 3ls_handoff_record
- 3ls_surface_coverage_record
- 3ls_failure_recurrence_record
- 3ls_trust_gap_closure_record
- 3ls_replayability_record
- 3ls_scope_risk_record
- 3ls_operator_debuggability_record

These artifacts measure system behavior. They do NOT grant authority,
replace control decisions, or perform enforcement. Tests assert authority-safe
shape and fail-closed behavior.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import load_example, load_schema, validate_artifact


MEASUREMENT_CONTRACTS = [
    "3ls_system_measurement_record",
    "3ls_loop_run_record",
    "3ls_handoff_record",
    "3ls_surface_coverage_record",
    "3ls_failure_recurrence_record",
    "3ls_trust_gap_closure_record",
    "3ls_replayability_record",
    "3ls_scope_risk_record",
    "3ls_operator_debuggability_record",
]


# ─────────────────────────────────────────────────────────────────────────────
# Positive validation
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", MEASUREMENT_CONTRACTS)
def test_example_validates(name: str) -> None:
    instance = load_example(name)
    validate_artifact(instance, name)


@pytest.mark.parametrize("name", MEASUREMENT_CONTRACTS)
def test_authority_scope_is_observation_only(name: str) -> None:
    instance = load_example(name)
    assert instance["authority_scope"] == "observation_only", (
        f"{name} must declare authority_scope='observation_only' to prevent "
        "authority leakage."
    )


@pytest.mark.parametrize("name", MEASUREMENT_CONTRACTS)
def test_schema_version_is_pinned(name: str) -> None:
    schema = load_schema(name)
    assert schema["properties"]["schema_version"]["const"] == "1.0.0"


@pytest.mark.parametrize("name", MEASUREMENT_CONTRACTS)
def test_artifact_type_is_const(name: str) -> None:
    schema = load_schema(name)
    assert schema["properties"]["artifact_type"]["const"] == name


# ─────────────────────────────────────────────────────────────────────────────
# Negative validation: missing required fields
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", MEASUREMENT_CONTRACTS)
def test_missing_artifact_type_fails(name: str) -> None:
    instance = load_example(name)
    instance.pop("artifact_type", None)
    with pytest.raises(ValidationError):
        validate_artifact(instance, name)


@pytest.mark.parametrize("name", MEASUREMENT_CONTRACTS)
def test_missing_schema_version_fails(name: str) -> None:
    instance = load_example(name)
    instance.pop("schema_version", None)
    with pytest.raises(ValidationError):
        validate_artifact(instance, name)


@pytest.mark.parametrize("name", MEASUREMENT_CONTRACTS)
def test_missing_authority_scope_fails(name: str) -> None:
    instance = load_example(name)
    instance.pop("authority_scope", None)
    with pytest.raises(ValidationError):
        validate_artifact(instance, name)


@pytest.mark.parametrize("name", MEASUREMENT_CONTRACTS)
def test_authority_scope_must_be_observation_only(name: str) -> None:
    """Authority leakage prevention: non-observation_only values must be rejected."""
    instance = load_example(name)
    instance["authority_scope"] = "decision_authority"
    with pytest.raises(ValidationError):
        validate_artifact(instance, name)


# ─────────────────────────────────────────────────────────────────────────────
# 3ls_system_measurement_record
# ─────────────────────────────────────────────────────────────────────────────

def test_system_measurement_invalid_system_enum_fails() -> None:
    instance = load_example("3ls_system_measurement_record")
    instance["system"] = "NOT_A_SYSTEM"
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_system_measurement_record")


def test_system_measurement_unknown_dimension_fails() -> None:
    instance = load_example("3ls_system_measurement_record")
    instance["measurement_dimensions"] = ["invented_dimension"]
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_system_measurement_record")


def test_system_measurement_uncovered_requires_gaps() -> None:
    instance = load_example("3ls_system_measurement_record")
    instance["coverage_status"] = "uncovered"
    instance["gaps"] = []
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_system_measurement_record")


def test_system_measurement_covered_requires_evidence() -> None:
    instance = load_example("3ls_system_measurement_record")
    instance["coverage_status"] = "covered"
    instance["evidence_refs"] = []
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_system_measurement_record")


# ─────────────────────────────────────────────────────────────────────────────
# 3ls_loop_run_record
# ─────────────────────────────────────────────────────────────────────────────

def test_loop_run_complete_requires_all_downstream_refs() -> None:
    instance = load_example("3ls_loop_run_record")
    instance["enforcement_ref"] = None
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_loop_run_record")


def test_loop_run_partial_requires_first_failure_system() -> None:
    instance = load_example("3ls_loop_run_record")
    instance["loop_status"] = "partial"
    instance["execution_ref"] = None
    instance["eval_ref"] = None
    instance["policy_ref"] = None
    instance["decision_ref"] = None
    instance["enforcement_ref"] = None
    instance["first_failure_system"] = None
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_loop_run_record")


def test_loop_run_partial_with_first_failure_system_passes() -> None:
    instance = load_example("3ls_loop_run_record")
    instance["loop_status"] = "partial"
    instance["execution_ref"] = None
    instance["eval_ref"] = None
    instance["policy_ref"] = None
    instance["decision_ref"] = None
    instance["enforcement_ref"] = None
    instance["first_failure_system"] = "PQX"
    validate_artifact(instance, "3ls_loop_run_record")


def test_loop_run_failed_requires_first_failure_system() -> None:
    instance = load_example("3ls_loop_run_record")
    instance["loop_status"] = "failed"
    instance["first_failure_system"] = None
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_loop_run_record")


def test_loop_run_invalid_status_fails() -> None:
    instance = load_example("3ls_loop_run_record")
    instance["loop_status"] = "kinda_done"
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_loop_run_record")


# ─────────────────────────────────────────────────────────────────────────────
# 3ls_handoff_record
# ─────────────────────────────────────────────────────────────────────────────

def test_handoff_complete_requires_downstream_ref() -> None:
    instance = load_example("3ls_handoff_record")
    instance["downstream_artifact_ref"] = None
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_handoff_record")


def test_handoff_blocked_requires_reason_codes() -> None:
    instance = load_example("3ls_handoff_record")
    instance["handoff_status"] = "blocked"
    instance["downstream_artifact_ref"] = None
    instance["reason_codes"] = []
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_handoff_record")


def test_handoff_failed_requires_reason_codes() -> None:
    instance = load_example("3ls_handoff_record")
    instance["handoff_status"] = "failed"
    instance["downstream_artifact_ref"] = None
    instance["reason_codes"] = []
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_handoff_record")


def test_handoff_pending_allows_no_downstream_ref() -> None:
    instance = load_example("3ls_handoff_record")
    instance["handoff_status"] = "pending"
    instance["downstream_artifact_ref"] = None
    validate_artifact(instance, "3ls_handoff_record")


def test_handoff_invalid_status_fails() -> None:
    instance = load_example("3ls_handoff_record")
    instance["handoff_status"] = "maybe"
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_handoff_record")


def test_handoff_invalid_system_pattern_fails() -> None:
    instance = load_example("3ls_handoff_record")
    instance["from_system"] = "lowercase"
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_handoff_record")


# ─────────────────────────────────────────────────────────────────────────────
# 3ls_surface_coverage_record
# ─────────────────────────────────────────────────────────────────────────────

def test_surface_coverage_governed_without_mapped_targets_fails() -> None:
    instance = load_example("3ls_surface_coverage_record")
    instance["governed_surfaces"] = ["contracts/schemas/some.schema.json"]
    instance["mapped_test_targets"] = []
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_surface_coverage_record")


def test_surface_coverage_ratio_out_of_range_fails() -> None:
    instance = load_example("3ls_surface_coverage_record")
    instance["coverage_ratio"] = 1.5
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_surface_coverage_record")


def test_surface_coverage_no_governed_surfaces_passes() -> None:
    instance = load_example("3ls_surface_coverage_record")
    instance["governed_surfaces"] = []
    instance["mapped_test_targets"] = []
    instance["coverage_ratio"] = 0.0
    validate_artifact(instance, "3ls_surface_coverage_record")


# ─────────────────────────────────────────────────────────────────────────────
# 3ls_failure_recurrence_record
# ─────────────────────────────────────────────────────────────────────────────

def test_failure_recurrence_count_below_one_fails() -> None:
    instance = load_example("3ls_failure_recurrence_record")
    instance["recurrence_count"] = 0
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_failure_recurrence_record")


def test_failure_recurrence_unknown_class_fails() -> None:
    instance = load_example("3ls_failure_recurrence_record")
    instance["failure_class"] = "totally_made_up"
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_failure_recurrence_record")


def test_failure_recurrence_invalid_fingerprint_fails() -> None:
    instance = load_example("3ls_failure_recurrence_record")
    instance["recurrence_fingerprint"] = "not-a-fingerprint"
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_failure_recurrence_record")


def test_failure_recurrence_empty_affected_systems_fails() -> None:
    instance = load_example("3ls_failure_recurrence_record")
    instance["affected_systems"] = []
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_failure_recurrence_record")


# ─────────────────────────────────────────────────────────────────────────────
# 3ls_trust_gap_closure_record
# ─────────────────────────────────────────────────────────────────────────────

def test_trust_gap_invalid_status_fails() -> None:
    instance = load_example("3ls_trust_gap_closure_record")
    instance["status"] = "improving_a_bit"
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_trust_gap_closure_record")


def test_trust_gap_unknown_gap_type_fails() -> None:
    instance = load_example("3ls_trust_gap_closure_record")
    instance["trust_gap_type"] = "invented_gap"
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_trust_gap_closure_record")


def test_trust_gap_negative_count_fails() -> None:
    instance = load_example("3ls_trust_gap_closure_record")
    instance["current_gap_count"] = -1
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_trust_gap_closure_record")


# ─────────────────────────────────────────────────────────────────────────────
# 3ls_replayability_record
# ─────────────────────────────────────────────────────────────────────────────

def test_replayability_available_requires_replay_refs() -> None:
    instance = load_example("3ls_replayability_record")
    instance["replay_available"] = True
    instance["replay_refs"] = []
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_replayability_record")


def test_replayability_unavailable_requires_gap_reason() -> None:
    instance = load_example("3ls_replayability_record")
    instance["replay_available"] = False
    instance["replay_refs"] = []
    instance["replay_gap_reason"] = None
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_replayability_record")


def test_replayability_unavailable_with_gap_reason_passes() -> None:
    instance = load_example("3ls_replayability_record")
    instance["replay_available"] = False
    instance["replay_refs"] = []
    instance["replay_gap_reason"] = "no replay harness wired for this system"
    validate_artifact(instance, "3ls_replayability_record")


# ─────────────────────────────────────────────────────────────────────────────
# 3ls_scope_risk_record
# ─────────────────────────────────────────────────────────────────────────────

def test_scope_risk_workflows_schemas_scripts_must_classify_high_or_critical() -> None:
    instance = load_example("3ls_scope_risk_record")
    instance["workflows_changed"] = True
    instance["schemas_changed"] = True
    instance["scripts_changed"] = True
    instance["scope_level"] = "low"
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_scope_risk_record")


def test_scope_risk_workflows_schemas_scripts_high_passes() -> None:
    instance = load_example("3ls_scope_risk_record")
    instance["workflows_changed"] = True
    instance["schemas_changed"] = True
    instance["scripts_changed"] = True
    instance["scope_level"] = "high"
    validate_artifact(instance, "3ls_scope_risk_record")


def test_scope_risk_invalid_level_fails() -> None:
    instance = load_example("3ls_scope_risk_record")
    instance["scope_level"] = "moderate"
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_scope_risk_record")


# ─────────────────────────────────────────────────────────────────────────────
# 3ls_operator_debuggability_record
# ─────────────────────────────────────────────────────────────────────────────

def test_operator_debug_single_artifact_requires_refs() -> None:
    instance = load_example("3ls_operator_debuggability_record")
    instance["single_artifact_debuggable"] = True
    instance["required_artifact_refs"] = []
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_operator_debuggability_record")


def test_operator_debug_unknown_failure_class_fails() -> None:
    instance = load_example("3ls_operator_debuggability_record")
    instance["failure_class"] = "made_up"
    with pytest.raises(ValidationError):
        validate_artifact(instance, "3ls_operator_debuggability_record")


# ─────────────────────────────────────────────────────────────────────────────
# Manifest registration
# ─────────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[1]
STANDARDS_MANIFEST = REPO_ROOT / "contracts" / "standards-manifest.json"


@pytest.mark.parametrize("name", MEASUREMENT_CONTRACTS)
def test_contract_registered_in_standards_manifest(name: str) -> None:
    manifest = json.loads(STANDARDS_MANIFEST.read_text(encoding="utf-8"))
    types = {c["artifact_type"] for c in manifest["contracts"]}
    assert name in types, (
        f"{name} must be registered in contracts/standards-manifest.json"
    )


@pytest.mark.parametrize("name", MEASUREMENT_CONTRACTS)
def test_contract_example_path_resolves(name: str) -> None:
    manifest = json.loads(STANDARDS_MANIFEST.read_text(encoding="utf-8"))
    entry = next(
        (c for c in manifest["contracts"] if c["artifact_type"] == name), None
    )
    assert entry is not None, f"Manifest entry missing for {name}"
    example_path = REPO_ROOT / entry["example_path"]
    assert example_path.exists(), f"Example file missing for {name}: {example_path}"
