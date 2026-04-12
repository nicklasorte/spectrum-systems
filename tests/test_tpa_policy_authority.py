from __future__ import annotations

from copy import deepcopy

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.tpa_policy_authority import (
    evaluate_tpa_policy_input_bundle,
    replay_validate,
    run_redteam_round,
)


def _bundle() -> dict:
    return load_example("tpa_policy_input_bundle")


def test_contract_examples_validate_for_new_tpa_boundary_contracts() -> None:
    for name in (
        "tpa_policy_input_bundle",
        "tpa_policy_decision_record",
        "tpa_evidence_requirement_record",
        "tpa_conflict_record",
        "tpa_policy_eval_result",
        "tpa_policy_bundle",
    ):
        validate_artifact(load_example(name), name)


def test_tpa_policy_engine_is_deterministic_for_same_inputs() -> None:
    bundle = _bundle()
    first = evaluate_tpa_policy_input_bundle(bundle)
    second = evaluate_tpa_policy_input_bundle(bundle)
    assert first == second


def test_tpa_scope_gating_and_budget_emit_narrow_when_requested_scope_too_large() -> None:
    bundle = _bundle()
    bundle["requested_scope"] = [
        "spectrum_systems/modules/runtime/tpa_policy_authority.py",
        "spectrum_systems/modules/runtime/cde_decision_flow.py",
        "spectrum_systems/modules/runtime/sel_enforcement_foundation.py",
        "tests/test_tpa_policy_authority.py",
    ]
    result = evaluate_tpa_policy_input_bundle(bundle)
    assert result["decision_record"]["decision"] == "narrow"
    assert "scope_exceeds_policy_limit" in result["decision_record"]["reason_codes"]


def test_tpa_freshness_guard_escalates_stale_source_authority() -> None:
    bundle = _bundle()
    bundle["source_authority_refresh_receipt"]["freshness_status"] = "stale"
    result = evaluate_tpa_policy_input_bundle(bundle)
    assert result["decision_record"]["decision"] == "evidence_required"


def test_tpa_boundary_fencing_rejects_non_governed_upstream_input() -> None:
    bundle = _bundle()
    bundle["task_wrapper_ref"] = "ad_hoc_payload:123"
    result = evaluate_tpa_policy_input_bundle(bundle)
    assert result["decision_record"]["decision"] == "reject"
    assert "invalid_upstream_task_wrapper" in result["decision_record"]["reason_codes"]


def test_tpa_replay_validation_detects_drift() -> None:
    bundle = _bundle()
    result = evaluate_tpa_policy_input_bundle(bundle)
    assert replay_validate(bundle, result["policy_bundle"]["replay_fingerprint"]) is True

    drifted = deepcopy(bundle)
    drifted["requested_scope"].append("docs/governance/README.md")
    assert replay_validate(drifted, result["policy_bundle"]["replay_fingerprint"]) is False


def test_tpa_evidence_escalation_debt_tracker_forces_evidence_required() -> None:
    bundle = _bundle()
    bundle["evidence_debt_counter"] = 5
    result = evaluate_tpa_policy_input_bundle(bundle)
    assert result["decision_record"]["decision"] == "evidence_required"
    assert "evidence_escalation_debt" in result["decision_record"]["reason_codes"]


def test_tpa_redteam_round_rt1_and_rt2_have_no_fail_open_exploits() -> None:
    rt1 = run_redteam_round(round_id="TPA-RT1")
    rt2 = run_redteam_round(round_id="TPA-RT2")
    assert rt1["status"] == "pass"
    assert rt2["status"] == "pass"
    assert rt1["exploits"] == []
    assert rt2["exploits"] == []
