import hashlib
import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.rax_assurance import (
    assure_rax_input,
    assure_rax_output,
    build_rax_assurance_audit_record,
    evaluate_rax_control_readiness,
)
from spectrum_systems.modules.runtime.rax_expander import expand_to_step_contract
from spectrum_systems.modules.runtime.rax_model import RAXModelError, load_compact_roadmap_step, normalize_compact_roadmap_step


REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "config" / "roadmap_expansion_policy.json"


def _load_policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _policy_hash() -> str:
    return hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()


def _valid_input_assurance_kwargs(upstream: dict) -> dict:
    return {
        "policy": _load_policy(),
        "expected_policy_hash": _policy_hash(),
        "trace": {
            "artifact_type": "roadmap_expansion_trace",
            "step_id": upstream["step_id"],
            "expansion_version": "1.1.0",
            "expansion_policy_hash": _policy_hash(),
            "field_trace": [
                {
                    "field_name": "target_modules",
                    "source_type": "expansion_policy",
                    "source_ref": "config/roadmap_expansion_policy.json#owner_defaults.PQX.allowed_module_prefixes",
                    "rule_id": "MODULE_PREFIX_BY_OWNER",
                    "notes": "Module targets are constrained to policy-declared prefixes.",
                },
                {
                    "field_name": "target_tests",
                    "source_type": "expansion_policy",
                    "source_ref": "config/roadmap_expansion_policy.json#owner_defaults.PQX.allowed_test_prefixes",
                    "rule_id": "TEST_PREFIX_BY_OWNER",
                    "notes": "Test targets are constrained to policy-declared prefixes.",
                },
                {
                    "field_name": "acceptance_checks",
                    "source_type": "expansion_policy",
                    "source_ref": "config/roadmap_expansion_policy.json#acceptance_check_templates",
                    "rule_id": "ACCEPTANCE_BY_TEMPLATE",
                    "notes": "Acceptance checks are derived from approved templates.",
                },
                {
                    "field_name": "forbidden_patterns",
                    "source_type": "governance_rule",
                    "source_ref": "AGENTS.md#Canonical runtime rules",
                    "rule_id": "FAIL_CLOSED_DEFAULT_PATTERNS",
                    "notes": "Forbidden patterns include fail-closed defaults.",
                },
                {
                    "field_name": "downstream_compatibility",
                    "source_type": "expansion_policy",
                    "source_ref": "config/roadmap_expansion_policy.json#default_downstream_compatibility",
                    "rule_id": "DOWNSTREAM_COMPATIBILITY_DEFAULTS",
                    "notes": "Compatibility defaults are policy-bound.",
                },
            ],
        },
        "freshness_records": {upstream["input_freshness_ref"]: {"is_fresh": True}},
        "provenance_records": {upstream["input_provenance_ref"]: {"trusted": True}},
        "source_version_authority": {upstream["source_authority_ref"]: upstream["source_version"]},
        "repo_root": REPO_ROOT,
    }


def test_canonical_model_normalization_is_deterministic() -> None:
    upstream = load_example("rax_upstream_input_envelope")
    upstream["depends_on"] = ["RAX-INTERFACE-24-02", "RAX-INTERFACE-24-00"]
    model = normalize_compact_roadmap_step(upstream)
    assert model.depends_on == ("RAX-INTERFACE-24-00", "RAX-INTERFACE-24-02")


def test_canonical_model_fails_closed_for_missing_required_field() -> None:
    upstream = load_example("rax_upstream_input_envelope")
    upstream.pop("intent", None)
    with pytest.raises(RAXModelError):
        normalize_compact_roadmap_step(upstream)


def test_canonical_model_rejects_lossy_dependency_normalization() -> None:
    upstream = load_example("rax_upstream_input_envelope")
    upstream["depends_on"] = ["RAX-INTERFACE-24-00", " RAX-INTERFACE-24-00 "]
    with pytest.raises(RAXModelError, match="normalization ambiguity"):
        normalize_compact_roadmap_step(upstream)


def test_expansion_is_deterministic_with_same_input_and_policy() -> None:
    upstream = load_example("rax_upstream_input_envelope")
    model = load_compact_roadmap_step(upstream)
    policy = _load_policy()

    contract_a, trace_a = expand_to_step_contract(model, policy=policy, policy_path=POLICY_PATH)
    contract_b, trace_b = expand_to_step_contract(model, policy=policy, policy_path=POLICY_PATH)

    assert contract_a == contract_b
    assert trace_a == trace_b
    assert contract_a["expansion_policy_hash"] == _policy_hash()


def test_expansion_fails_when_required_owner_mapping_missing() -> None:
    upstream = load_example("rax_upstream_input_envelope")
    model = load_compact_roadmap_step(upstream)
    policy = _load_policy()
    policy["owner_defaults"].pop("PQX", None)

    with pytest.raises(Exception):
        expand_to_step_contract(model, policy=policy, policy_path=POLICY_PATH)


def test_every_derived_field_has_trace_entry() -> None:
    upstream = load_example("rax_upstream_input_envelope")
    model = load_compact_roadmap_step(upstream)
    contract, trace = expand_to_step_contract(model, policy=_load_policy(), policy_path=POLICY_PATH)

    traced_fields = {entry["field_name"] for entry in trace["field_trace"]}
    for field in ("target_modules", "target_tests", "acceptance_checks", "forbidden_patterns", "downstream_compatibility"):
        assert field in traced_fields

    validate_artifact(contract, "roadmap_step_contract")
    validate_artifact(trace, "roadmap_expansion_trace")


def test_input_assurance_classifies_stale_reference() -> None:
    upstream = load_example("rax_upstream_input_envelope")
    kwargs = _valid_input_assurance_kwargs(upstream)
    kwargs["freshness_records"] = {}
    result = assure_rax_input(upstream, **kwargs)
    assert result["passed"] is False
    assert result["failure_classification"] == "stale_reference"


def test_input_assurance_rejects_weak_intent_and_blocks_pass() -> None:
    upstream = load_example("rax_upstream_input_envelope")
    upstream["intent"] = "todo todo todo todo"
    result = assure_rax_input(upstream, **_valid_input_assurance_kwargs(upstream))
    assert result["passed"] is False
    assert result["failure_classification"] == "invalid_input"
    assert any("semantic_intent_insufficient" in detail for detail in result["details"])


def test_input_assurance_rejects_owner_intent_contradiction() -> None:
    upstream = load_example("rax_upstream_input_envelope")
    upstream["owner"] = "PRG"
    upstream["intent"] = "Directly execute runtime entrypoint changes in production for this batch."
    result = assure_rax_input(upstream, **_valid_input_assurance_kwargs(upstream))
    assert result["passed"] is False
    assert result["failure_classification"] == "ownership_violation"
    assert any("owner_intent_contradiction" in detail for detail in result["details"])


def test_input_assurance_requires_trace_presence() -> None:
    upstream = load_example("rax_upstream_input_envelope")
    kwargs = _valid_input_assurance_kwargs(upstream)
    kwargs["trace"] = None
    result = assure_rax_input(upstream, **kwargs)
    assert result["passed"] is False
    assert result["failure_classification"] == "trace_tampering"
    assert "missing_required_expansion_trace" in result["details"]


def test_input_assurance_rejects_invalid_trace_contents() -> None:
    upstream = load_example("rax_upstream_input_envelope")
    kwargs = _valid_input_assurance_kwargs(upstream)
    kwargs["trace"]["field_trace"] = kwargs["trace"]["field_trace"][:-1]
    result = assure_rax_input(upstream, **kwargs)
    assert result["passed"] is False
    assert result["failure_classification"] == "trace_tampering"


def test_input_assurance_detects_source_version_drift() -> None:
    upstream = load_example("rax_upstream_input_envelope")
    kwargs = _valid_input_assurance_kwargs(upstream)
    kwargs["source_version_authority"] = {upstream["source_authority_ref"]: "9.9.9"}
    result = assure_rax_input(upstream, **kwargs)
    assert result["passed"] is False
    assert result["failure_classification"] == "stale_reference"
    assert any("source_version_drift" in detail for detail in result["details"])


def test_output_assurance_rejects_unresolvable_runtime_entrypoint() -> None:
    step_contract = load_example("roadmap_step_contract")
    step_contract["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.rax_model:missing_func"]
    result = assure_rax_output(step_contract, repo_root=REPO_ROOT, policy=_load_policy())
    assert result["passed"] is False
    assert result["failure_classification"] == "downstream_incompatible"


def test_output_assurance_rejects_owner_target_contradiction() -> None:
    step_contract = load_example("roadmap_step_contract")
    step_contract["owner"] = "PRG"
    step_contract["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.rax_model:load_compact_roadmap_step"]
    step_contract["target_modules"] = ["spectrum_systems/modules/runtime/rax_assurance.py"]
    result = assure_rax_output(step_contract, repo_root=REPO_ROOT, policy=_load_policy())
    assert result["passed"] is False
    assert result["failure_classification"] == "downstream_incompatible"
    assert any("owner_target_contradiction" in detail for detail in result["details"])


def test_output_assurance_rejects_weak_acceptance_checks() -> None:
    step_contract = load_example("roadmap_step_contract")
    step_contract["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.rax_model:load_compact_roadmap_step"]
    step_contract["acceptance_checks"] = [{"check_id": "schema_validation_passes", "description": "TODO maybe", "required": True}]
    result = assure_rax_output(step_contract, repo_root=REPO_ROOT, policy=_load_policy())
    assert result["passed"] is False
    assert result["failure_classification"] == "invalid_output"
    assert any("weak_acceptance_check" in detail for detail in result["details"])


def test_output_assurance_detects_regression_against_baseline() -> None:
    step_contract = load_example("roadmap_step_contract")
    baseline = load_example("roadmap_step_contract")
    step_contract["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.rax_model:load_compact_roadmap_step"]
    baseline["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.rax_model:load_compact_roadmap_step"]
    baseline["acceptance_checks"].append(
        {
            "check_id": "runtime_entrypoints_resolvable",
            "description": "Runtime entrypoints must be validated as resolvable for deterministic execution safety.",
            "required": True,
        }
    )
    result = assure_rax_output(step_contract, repo_root=REPO_ROOT, policy=_load_policy(), prior_accepted_baseline=baseline)
    assert result["passed"] is False
    assert result["failure_classification"] == "downstream_incompatible"
    assert any("regression_detected" in detail for detail in result["details"])


def test_assurance_audit_record_is_complete_and_outcome_enum_bound() -> None:
    input_assurance = {"passed": True, "details": ["ok"], "failure_classification": "none", "stop_condition_triggered": False}
    output_assurance = {"passed": True, "details": ["ok"], "failure_classification": "none", "stop_condition_triggered": False}
    audit = build_rax_assurance_audit_record(
        roadmap_id="SYSTEM-ROADMAP-2026",
        step_id="RAX-INTERFACE-24-01",
        input_assurance=input_assurance,
        output_assurance=output_assurance,
    )
    assert audit["acceptance_decision"] in {"accept_candidate", "hold_candidate", "block_candidate"}
    validate_artifact(audit, "rax_assurance_audit_record")


def test_assurance_audit_requires_counter_evidence_when_failure_exists() -> None:
    input_assurance = {
        "passed": False,
        "details": ["owner_intent_contradiction: owner=PRG cannot claim runtime execution"],
        "failure_classification": "ownership_violation",
        "stop_condition_triggered": False,
    }
    output_assurance = {
        "passed": True,
        "details": [],
        "failure_classification": "none",
        "stop_condition_triggered": False,
    }
    audit = build_rax_assurance_audit_record(
        roadmap_id="SYSTEM-ROADMAP-2026",
        step_id="RAX-INTERFACE-24-01",
        input_assurance=input_assurance,
        output_assurance=output_assurance,
    )
    assert audit["counter_evidence"]
    assert audit["stop_condition_triggered"] is True


def test_weak_output_fails_closed() -> None:
    step_contract = load_example("roadmap_step_contract")
    step_contract["acceptance_checks"] = []
    result = assure_rax_output(step_contract, repo_root=REPO_ROOT, policy=_load_policy())
    assert result["passed"] is False
    assert result["stop_condition_triggered"] is True



def test_assurance_control_readiness_wrapper_emits_record() -> None:
    readiness = evaluate_rax_control_readiness(
        batch="RAX-EVAL-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary={
            "required_eval_types": ["rax_trace_integrity"],
            "present_eval_types": [],
            "missing_required_eval_types": ["rax_trace_integrity"],
            "overall_result": "fail",
        },
        eval_results=[],
        required_eval_coverage={"required_eval_types": ["rax_trace_integrity"], "present_eval_types": [], "missing_required_eval_types": ["rax_trace_integrity"], "overall_result": "fail"},
    )
    assert readiness["artifact_type"] == "rax_control_readiness_record"
    assert readiness["ready_for_control"] is False
