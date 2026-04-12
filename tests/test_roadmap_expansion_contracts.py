import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import load_example, load_schema, validate_artifact


REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "config" / "roadmap_expansion_policy.json"
CANONICAL_OWNERS = {"RIL", "CDE", "TLC", "PQX", "FRE", "SEL", "PRG"}


def _load_policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _policy_sha256() -> str:
    payload = POLICY_PATH.read_bytes()
    return hashlib.sha256(payload).hexdigest()


def test_roadmap_step_contract_schema_validates_example() -> None:
    validate_artifact(load_example("roadmap_step_contract"), "roadmap_step_contract")


def test_roadmap_step_contract_rejects_missing_required_field() -> None:
    instance = load_example("roadmap_step_contract")
    instance.pop("owner", None)
    with pytest.raises(ValidationError):
        validate_artifact(instance, "roadmap_step_contract")


def test_roadmap_step_contract_rejects_invalid_enums() -> None:
    instance = load_example("roadmap_step_contract")
    instance["realization_mode"] = "freeform_mode"
    with pytest.raises(ValidationError):
        validate_artifact(instance, "roadmap_step_contract")


def test_roadmap_expansion_trace_schema_validates_example() -> None:
    validate_artifact(load_example("roadmap_expansion_trace"), "roadmap_expansion_trace")


def test_roadmap_expansion_trace_rejects_missing_field_trace_metadata() -> None:
    instance = load_example("roadmap_expansion_trace")
    instance["field_trace"][0].pop("rule_id", None)
    with pytest.raises(ValidationError):
        validate_artifact(instance, "roadmap_expansion_trace")


def test_roadmap_expansion_policy_has_required_top_level_structure() -> None:
    policy = _load_policy()
    required_keys = {
        "policy_id",
        "policy_version",
        "description",
        "owner_defaults",
        "forbidden_ownership_crossings",
        "default_forbidden_patterns",
        "default_downstream_compatibility",
        "acceptance_check_templates",
    }
    assert required_keys.issubset(policy.keys())


def test_roadmap_expansion_policy_has_owner_mappings_for_canonical_owners() -> None:
    policy = _load_policy()
    owner_defaults = policy["owner_defaults"]
    assert CANONICAL_OWNERS.issubset(owner_defaults.keys())

    for owner in CANONICAL_OWNERS:
        mapping = owner_defaults[owner]
        for required_key in (
            "allowed_module_prefixes",
            "allowed_test_prefixes",
            "default_contract_locations",
            "default_acceptance_check_templates",
        ):
            assert required_key in mapping
            assert isinstance(mapping[required_key], list)
            assert mapping[required_key], f"{owner}.{required_key} must not be empty"


def test_examples_are_consistent_with_schema_and_policy_hash() -> None:
    step = load_example("roadmap_step_contract")
    trace = load_example("roadmap_expansion_trace")

    validate_artifact(step, "roadmap_step_contract")
    validate_artifact(trace, "roadmap_expansion_trace")

    expected_hash = _policy_sha256()
    assert step["expansion_policy_hash"] == expected_hash
    assert trace["expansion_policy_hash"] == expected_hash


def test_rax_upstream_input_schema_validates_example() -> None:
    validate_artifact(load_example("rax_upstream_input_envelope"), "rax_upstream_input_envelope")


def test_rax_upstream_input_rejects_missing_required_field() -> None:
    instance = load_example("rax_upstream_input_envelope")
    instance.pop("source_authority_ref", None)
    with pytest.raises(ValidationError):
        validate_artifact(instance, "rax_upstream_input_envelope")


def test_rax_upstream_input_rejects_invalid_owner_enum() -> None:
    instance = load_example("rax_upstream_input_envelope")
    instance["owner"] = "UNKNOWN"
    with pytest.raises(ValidationError):
        validate_artifact(instance, "rax_upstream_input_envelope")


def test_rax_upstream_input_rejects_malformed_step_id() -> None:
    instance = load_example("rax_upstream_input_envelope")
    instance["step_id"] = "invalid step"
    with pytest.raises(ValidationError):
        validate_artifact(instance, "rax_upstream_input_envelope")


def test_rax_assurance_audit_record_schema_validates_example() -> None:
    validate_artifact(load_example("rax_assurance_audit_record"), "rax_assurance_audit_record")


def test_roadmap_step_contract_rejects_empty_acceptance_checks() -> None:
    instance = load_example("roadmap_step_contract")
    instance["acceptance_checks"] = []
    with pytest.raises(ValidationError):
        validate_artifact(instance, "roadmap_step_contract")


def test_roadmap_step_contract_rejects_runtime_realization_without_entrypoints() -> None:
    instance = load_example("roadmap_step_contract")
    instance["realization_mode"] = "runtime_realization"
    instance["runtime_entrypoints"] = []
    with pytest.raises(ValidationError):
        validate_artifact(instance, "roadmap_step_contract")


def test_roadmap_step_contract_schema_is_strict_no_additional_properties() -> None:
    schema = load_schema("roadmap_step_contract")
    validator = Draft202012Validator(schema)
    instance = load_example("roadmap_step_contract")
    instance["non_canonical"] = "unexpected"
    with pytest.raises(ValidationError):
        validator.validate(instance)


def test_rax_feedback_loop_contract_examples_validate() -> None:
    for name in (
        "rax_failure_pattern_record",
        "rax_failure_eval_candidate",
        "rax_feedback_loop_record",
        "rax_health_snapshot",
        "rax_drift_signal_record",
        "rax_unknown_state_record",
        "rax_pre_certification_alignment_record",
        "rax_adversarial_pattern_candidate",
        "rax_conflict_arbitration_record",
        "rax_judgment_record",
        "rax_trend_report",
        "rax_trust_posture_snapshot",
        "rax_improvement_recommendation_record",
        "rax_eval_candidate_admission_record",
        "rax_promotion_hard_gate_record",
    ):
        validate_artifact(load_example(name), name)


def test_rax_control_readiness_requires_structured_change_conditions() -> None:
    instance = load_example("rax_control_readiness_record")
    instance.pop("conditions_under_which_ready_changes", None)
    with pytest.raises(ValidationError):
        validate_artifact(instance, "rax_control_readiness_record")


def test_rax_control_readiness_requires_replay_identity() -> None:
    instance = load_example("rax_control_readiness_record")
    instance.pop("replay_identity", None)
    with pytest.raises(ValidationError):
        validate_artifact(instance, "rax_control_readiness_record")
