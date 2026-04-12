import hashlib
import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.rax_assurance import (
    assure_rax_input,
    assure_rax_output,
    build_rax_assurance_audit_record,
)
from spectrum_systems.modules.runtime.rax_expander import expand_to_step_contract
from spectrum_systems.modules.runtime.rax_model import RAXModelError, load_compact_roadmap_step, normalize_compact_roadmap_step


REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "config" / "roadmap_expansion_policy.json"


def _load_policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _policy_hash() -> str:
    return hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()


def test_canonical_model_normalization_is_deterministic() -> None:
    upstream = load_example("rax_upstream_input_envelope")
    upstream["depends_on"] = ["RAX-INTERFACE-24-02", "RAX-INTERFACE-24-00", "RAX-INTERFACE-24-00"]
    model = normalize_compact_roadmap_step(upstream)
    assert model.depends_on == ("RAX-INTERFACE-24-00", "RAX-INTERFACE-24-02")


def test_canonical_model_fails_closed_for_missing_required_field() -> None:
    upstream = load_example("rax_upstream_input_envelope")
    upstream.pop("intent", None)
    with pytest.raises(RAXModelError):
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
    result = assure_rax_input(
        upstream,
        policy=_load_policy(),
        expected_policy_hash=_policy_hash(),
        freshness_records={},
        provenance_records={upstream["input_provenance_ref"]: {"trusted": True}},
    )
    assert result["passed"] is False
    assert result["failure_classification"] == "stale_reference"


def test_input_assurance_classifies_trace_tampering() -> None:
    upstream = load_example("rax_upstream_input_envelope")
    result = assure_rax_input(
        upstream,
        policy=_load_policy(),
        expected_policy_hash=_policy_hash(),
        trace={"expansion_policy_hash": "0" * 64},
        freshness_records={upstream["input_freshness_ref"]: {"is_fresh": True}},
        provenance_records={upstream["input_provenance_ref"]: {"trusted": True}},
    )
    assert result["passed"] is False
    assert result["failure_classification"] == "trace_tampering"


def test_output_assurance_rejects_unresolvable_runtime_entrypoint() -> None:
    step_contract = load_example("roadmap_step_contract")
    step_contract["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.rax_model:missing_func"]
    result = assure_rax_output(step_contract, repo_root=REPO_ROOT)
    assert result["passed"] is False
    assert result["failure_classification"] == "downstream_incompatible"


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


def test_weak_output_fails_closed() -> None:
    step_contract = load_example("roadmap_step_contract")
    step_contract["acceptance_checks"] = []
    result = assure_rax_output(step_contract, repo_root=REPO_ROOT)
    assert result["passed"] is False
    assert result["stop_condition_triggered"] is True
