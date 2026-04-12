from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.orchestration.sequence_transition_policy import evaluate_sequence_transition

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "sequence_replay"


def _base_manifest(state: str) -> dict:
    allow_policy_path = _REPO_ROOT / "tests" / "fixtures" / "autonomous_cycle" / "evaluation_control_decision_allow.json"
    return {
        "cycle_id": "cycle-seq",
        "current_state": state,
        "roadmap_artifact_path": str(_REPO_ROOT / "docs" / "roadmap" / "system_roadmap.md"),
        "execution_report_paths": [
            str(_REPO_ROOT / "contracts" / "examples" / "execution_report_artifact.json"),
            str(_REPO_ROOT / "contracts" / "examples" / "execution_report_artifact.json"),
            str(_REPO_ROOT / "contracts" / "examples" / "execution_report_artifact.json"),
        ],
        "implementation_review_paths": [str(_REPO_ROOT / "tests" / "fixtures" / "autonomous_cycle" / "implementation_review_claude.json")],
        "certification_status": "passed",
        "certification_record_path": str(_REPO_ROOT / "contracts" / "examples" / "done_certification_record.json"),
        "decision_blocked": False,
        "required_judgments": ["artifact_release_readiness"],
        "judgment_record_path": str(_REPO_ROOT / "contracts" / "examples" / "judgment_record.json"),
        "judgment_application_record_path": str(_REPO_ROOT / "contracts" / "examples" / "judgment_application_record.json"),
        "judgment_eval_result_path": str(_REPO_ROOT / "contracts" / "examples" / "judgment_eval_result.json"),
        "hard_gate_falsification_record_path": str(_REPO_ROOT / "contracts" / "examples" / "pqx_hard_gate_falsification_record.json"),
        "done_certification_input_refs": {
            "replay_result_ref": str(_REPO_ROOT / "contracts" / "examples" / "replay_result.json"),
            "policy_ref": str(allow_policy_path),
            "enforcement_result_ref": str(_REPO_ROOT / "tests" / "fixtures" / "autonomous_cycle" / "enforcement_result_allow.json"),
            "eval_coverage_summary_ref": str(_REPO_ROOT / "tests" / "fixtures" / "autonomous_cycle" / "eval_coverage_summary_allow.json"),
            "certification_pack_ref": str(_REPO_ROOT / "contracts" / "examples" / "control_loop_certification_pack.json"),
            "review_control_signal_ref": str(_REPO_ROOT / "contracts" / "examples" / "review_control_signal.json"),
            "closure_decision_artifact_ref": str(_REPO_ROOT / "contracts" / "examples" / "closure_decision_artifact.json"),
            "ril_output_artifact_ref": str(_REPO_ROOT / "contracts" / "examples" / "review_integration_packet_artifact.json"),
            "trust_spine_evidence_cohesion_result_ref": str(_REPO_ROOT / "contracts" / "examples" / "trust_spine_evidence_cohesion_result.json"),
            "rax_operational_gate_record_ref": str(_REPO_ROOT / "contracts" / "examples" / "rax_operational_gate_record.json"),
        },
        "review_signal_policy": {"required_for_promotion": True},
        "control_loop_gate_proof": {
            "severity_linkage_complete": True,
            "deterministic_transition_consumption": True,
            "policy_caused_action_observed": True,
            "recurrence_prevention_linked": True,
            "failure_binding_required_for_progression": True,
            "missing_binding_blocks_progression": True,
            "advisory_only_learning_rejected": True,
            "transition_policy_consumes_binding_deterministically": True,
            "severity_linkage_refs": ["contracts/examples/failure_eval_case.json"],
            "transition_consumption_refs": ["contracts/examples/prompt_queue_transition_decision.json"],
            "policy_action_refs": ["contracts/examples/pqx_slice_execution_record.json"],
            "recurrence_prevention_refs": ["contracts/examples/failure_policy_binding.json"],
        },
        "sequence_trace_id": "trace-seq",
        "sequence_lineage": ["contracts/examples/roadmap_eligibility_artifact.json"],
        "blocking_issues": ["explicit block"],
    }


def test_sequence_happy_path_fixture_allows_ordered_transitions() -> None:
    fixture = json.loads((_FIXTURES / "happy_path.json").read_text(encoding="utf-8"))
    states = fixture["states"]
    for idx in range(len(states) - 1):
        manifest = _base_manifest(states[idx])
        decision = evaluate_sequence_transition(manifest, states[idx + 1])
        assert decision.allowed is True


def test_sequence_broken_path_fixture_blocks_illegal_transitions() -> None:
    fixture = json.loads((_FIXTURES / "broken_paths.json").read_text(encoding="utf-8"))
    for case in fixture["cases"]:
        manifest = _base_manifest(case["from"])
        decision = evaluate_sequence_transition(manifest, case["to"])
        assert decision.allowed is False
        assert case["reason"] in str(decision.reason)


def test_sequence_indeterminate_fixture_blocks_inconsistent_evidence() -> None:
    fixture = json.loads((_FIXTURES / "indeterminate_paths.json").read_text(encoding="utf-8"))
    for case in fixture["cases"]:
        manifest = _base_manifest(case["from"])
        manifest.update(case.get("mutations", {}))
        if case["name"] == "promotion_without_control_allow":
            manifest["done_certification_input_refs"].pop("closure_decision_artifact_ref", None)
        decision = evaluate_sequence_transition(manifest, case["to"])
        assert decision.allowed is False
        if case["reason"] == "explicit control_allow_promotion":
            assert "closure_decision_artifact" in str(decision.reason)
        else:
            assert case["reason"] in str(decision.reason)


def test_promotion_blocks_when_failure_binding_proof_missing() -> None:
    manifest = _base_manifest("certification_pending")
    manifest["control_loop_gate_proof"]["failure_binding_required_for_progression"] = False
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "failure_binding_required_for_progression" in str(decision.reason)


def test_promotion_blocks_when_closure_decision_artifact_missing() -> None:
    manifest = _base_manifest("certification_pending")
    manifest["done_certification_input_refs"].pop("closure_decision_artifact_ref")
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "closure_decision_artifact" in str(decision.reason)


def test_promotion_blocks_when_required_judgment_artifact_missing() -> None:
    manifest = _base_manifest("certification_pending")
    manifest["judgment_eval_result_path"] = ""
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "judgment_eval_result_path" in str(decision.reason)


def test_promotion_blocks_when_hard_gate_falsification_fails(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    payload = json.loads(Path(manifest["hard_gate_falsification_record_path"]).read_text(encoding="utf-8"))
    payload["overall_result"] = "fail"
    bad_path = tmp_path / "hard_gate_falsification_failed.json"
    bad_path.write_text(json.dumps(payload), encoding="utf-8")
    manifest["hard_gate_falsification_record_path"] = str(bad_path)
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "hard gate falsification" in str(decision.reason)


def test_promotion_requires_replay_authority_refs_even_when_falsification_ref_can_be_resolved(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    cert_pack = json.loads(Path(_REPO_ROOT / "contracts" / "examples" / "control_loop_certification_pack.json").read_text(encoding="utf-8"))
    cert_pack["gate_proof_evidence"]["hard_gate_falsification_refs"] = [manifest["hard_gate_falsification_record_path"]]
    cert_pack_path = tmp_path / "control_loop_certification_pack.json"
    cert_pack_path.write_text(json.dumps(cert_pack), encoding="utf-8")

    manifest["hard_gate_falsification_record_path"] = ""
    manifest["done_certification_input_refs"] = {
        "certification_pack_ref": str(cert_pack_path),
        "closure_decision_artifact_ref": str(_REPO_ROOT / "contracts" / "examples" / "closure_decision_artifact.json"),
    }
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "TRUST_SPINE_REQUIRED_REF_MISSING" in str(decision.reason)


def test_promotion_blocks_when_enforcement_result_is_deny(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    enforcement = json.loads(Path(manifest["done_certification_input_refs"]["enforcement_result_ref"]).read_text(encoding="utf-8"))
    enforcement["final_status"] = "deny"
    bad_path = tmp_path / "enforcement_result_blocked.json"
    bad_path.write_text(json.dumps(enforcement), encoding="utf-8")
    manifest["done_certification_input_refs"]["enforcement_result_ref"] = str(bad_path)
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "enforcement result" in str(decision.reason)


def test_promotion_blocks_when_required_eval_coverage_gap_present(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    coverage = json.loads(Path(manifest["done_certification_input_refs"]["eval_coverage_summary_ref"]).read_text(encoding="utf-8"))
    coverage["required_slice_gaps"] = [{"slice_id": "runtime_guardrails", "reason": "missing"}]
    bad_path = tmp_path / "eval_coverage_summary_gap.json"
    bad_path.write_text(json.dumps(coverage), encoding="utf-8")
    manifest["done_certification_input_refs"]["eval_coverage_summary_ref"] = str(bad_path)
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "coverage gaps" in str(decision.reason)


def test_promotion_blocks_when_enforcement_result_ref_missing() -> None:
    manifest = _base_manifest("certification_pending")
    manifest["done_certification_input_refs"].pop("enforcement_result_ref")
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "TRUST_SPINE_ENFORCEMENT_REF_MISSING" in str(decision.reason)


def test_promotion_blocks_when_rax_operational_gate_ref_missing() -> None:
    manifest = _base_manifest("certification_pending")
    manifest["done_certification_input_refs"].pop("rax_operational_gate_record_ref")
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "rax_operational_gate_record_ref" in str(decision.reason)


def test_promotion_blocks_when_rax_operational_gate_not_passed(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    gate = json.loads(Path(manifest["done_certification_input_refs"]["rax_operational_gate_record_ref"]).read_text(encoding="utf-8"))
    gate["passed"] = False
    gate["decision"] = "block_candidate"
    gate["blocking_reasons"] = ["replay_evidence_unbound_or_stale"]
    path = tmp_path / "rax_operational_gate_record_blocked.json"
    path.write_text(json.dumps(gate), encoding="utf-8")
    manifest["done_certification_input_refs"]["rax_operational_gate_record_ref"] = str(path)
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "passed=false" in str(decision.reason)


def test_promotion_blocks_when_eval_coverage_summary_ref_missing() -> None:
    manifest = _base_manifest("certification_pending")
    manifest["done_certification_input_refs"].pop("eval_coverage_summary_ref")
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "TRUST_SPINE_COVERAGE_REF_MISSING" in str(decision.reason)


def test_promotion_legacy_mode_is_explicitly_non_promotable_when_refs_missing() -> None:
    manifest = _base_manifest("certification_pending")
    manifest["authority_path_mode"] = "legacy_compatibility"
    manifest["done_certification_input_refs"].pop("enforcement_result_ref")
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "TRUST_SPINE_LEGACY_PATH_NOT_PROMOTABLE" in str(decision.reason)


def test_promotion_blocks_when_policy_has_no_decision_or_system_response(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    ambiguous = {"artifact_type": "evaluation_control_decision", "schema_version": "1.2.0"}
    path = tmp_path / "ambiguous_policy.json"
    path.write_text(json.dumps(ambiguous), encoding="utf-8")
    manifest["done_certification_input_refs"]["policy_ref"] = str(path)
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "decision/system_response" in str(decision.reason)


def test_promotion_blocks_when_threshold_context_is_comparative_analysis(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    policy = json.loads(Path(manifest["done_certification_input_refs"]["policy_ref"]).read_text(encoding="utf-8"))
    policy["threshold_context"] = "comparative_analysis"
    path = tmp_path / "policy_comparative.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    manifest["done_certification_input_refs"]["policy_ref"] = str(path)
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "TRUST_SPINE_THRESHOLD_CONTEXT_MISMATCH" in str(decision.reason)


def test_promotion_blocks_when_policy_allow_conflicts_with_enforcement_deny(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    enforcement = json.loads(Path(manifest["done_certification_input_refs"]["enforcement_result_ref"]).read_text(encoding="utf-8"))
    enforcement["final_status"] = "deny"
    path = tmp_path / "enforcement_deny.json"
    path.write_text(json.dumps(enforcement), encoding="utf-8")
    manifest["done_certification_input_refs"]["enforcement_result_ref"] = str(path)
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "enforcement result" in str(decision.reason) or "TRUST_SPINE_CONTROL_ENFORCEMENT_MISMATCH" in str(decision.reason)


def test_promotion_blocks_when_replay_ref_content_is_blocked(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    replay = json.loads(Path(manifest["done_certification_input_refs"]["replay_result_ref"]).read_text(encoding="utf-8"))
    replay["status"] = "blocked"
    path = tmp_path / "blocked_replay.json"
    path.write_text(json.dumps(replay), encoding="utf-8")
    manifest["done_certification_input_refs"]["replay_result_ref"] = str(path)
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "status=blocked" in str(decision.reason)


def test_promotion_blocks_when_uncovered_required_slices_present(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    coverage = json.loads(Path(manifest["done_certification_input_refs"]["eval_coverage_summary_ref"]).read_text(encoding="utf-8"))
    coverage["uncovered_required_slices"] = ["runtime_guardrails"]
    path = tmp_path / "coverage_uncovered_required.json"
    path.write_text(json.dumps(coverage), encoding="utf-8")
    manifest["done_certification_input_refs"]["eval_coverage_summary_ref"] = str(path)
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "coverage gaps" in str(decision.reason)


def test_promotion_blocks_when_coverage_gaps_show_required_high_severity(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    coverage = json.loads(Path(manifest["done_certification_input_refs"]["eval_coverage_summary_ref"]).read_text(encoding="utf-8"))
    coverage["coverage_gaps"] = [{"slice_id": "runtime_guardrails", "required": True, "severity": "critical", "status": "missing"}]
    path = tmp_path / "coverage_required_high.json"
    path.write_text(json.dumps(coverage), encoding="utf-8")
    manifest["done_certification_input_refs"]["eval_coverage_summary_ref"] = str(path)
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "coverage gaps" in str(decision.reason)


def test_enforcement_vocabulary_normalization_blocks_variants(tmp_path: Path) -> None:
    variants = ["block", "blocked", "freeze", "frozen", "hold"]
    for variant in variants:
        manifest = _base_manifest("certification_pending")
        enforcement = json.loads(Path(manifest["done_certification_input_refs"]["enforcement_result_ref"]).read_text(encoding="utf-8"))
        enforcement["final_status"] = variant
        path = tmp_path / f"enforcement_{variant}.json"
        path.write_text(json.dumps(enforcement), encoding="utf-8")
        manifest["done_certification_input_refs"]["enforcement_result_ref"] = str(path)
        decision = evaluate_sequence_transition(manifest, "promoted")
        assert decision.allowed is False


def test_promotion_blocks_when_review_signal_missing_and_required() -> None:
    manifest = _base_manifest("certification_pending")
    manifest["done_certification_input_refs"].pop("review_control_signal_ref")
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "required review_control_signal is missing" in str(decision.reason)


def test_promotion_blocks_when_review_signal_gate_fails(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    signal = json.loads(Path(manifest["done_certification_input_refs"]["review_control_signal_ref"]).read_text(encoding="utf-8"))
    signal["gate_assessment"] = "FAIL"
    signal["scale_recommendation"] = "NO"
    path = tmp_path / "review_control_signal_fail.json"
    path.write_text(json.dumps(signal), encoding="utf-8")
    manifest["done_certification_input_refs"]["review_control_signal_ref"] = str(path)
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "gate_assessment=FAIL" in str(decision.reason)


def test_promotion_blocks_when_obedience_result_blocks(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    obedience = json.loads((_REPO_ROOT / "contracts" / "examples" / "control_surface_obedience_result.json").read_text(encoding="utf-8"))
    obedience["overall_decision"] = "BLOCK"
    obedience["blocking_reasons"] = ["sequence_transition_promotion:promotion allowed despite failed done certification"]
    obedience["missing_obedience_evidence"] = ["sequence_transition_promotion:promotion consumed_signals evidence missing"]
    obedience["contradictory_obedience_evidence"] = []
    path = tmp_path / "control_surface_obedience_result_block.json"
    path.write_text(json.dumps(obedience), encoding="utf-8")
    manifest["done_certification_input_refs"]["control_surface_obedience_result_ref"] = str(path)

    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "control_surface_obedience_result" in str(decision.reason)


def test_promotion_blocks_when_cohesion_result_ref_missing() -> None:
    manifest = _base_manifest("certification_pending")
    manifest["done_certification_input_refs"].pop("trust_spine_evidence_cohesion_result_ref")
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "trust_spine_evidence_cohesion_result_ref" in str(decision.reason)


def test_promotion_blocks_when_cohesion_result_blocks(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    cohesion = json.loads((_REPO_ROOT / "contracts" / "examples" / "trust_spine_evidence_cohesion_result.json").read_text(encoding="utf-8"))
    cohesion["overall_decision"] = "BLOCK"
    cohesion["contradiction_categories"] = ["promotion_certification_contradiction"]
    cohesion["blocking_reasons"] = ["PROMOTION_CERTIFICATION_CONTRADICTION:promotion_allowed_with_obedience_block"]
    path = tmp_path / "cohesion_block.json"
    path.write_text(json.dumps(cohesion), encoding="utf-8")
    manifest["done_certification_input_refs"]["trust_spine_evidence_cohesion_result_ref"] = str(path)

    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "trust_spine_evidence_cohesion_result" in str(decision.reason)


def test_promotion_allows_when_obedience_result_allows(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    path = tmp_path / "control_surface_obedience_result_allow.json"
    path.write_text((_REPO_ROOT / "contracts" / "examples" / "control_surface_obedience_result.json").read_text(encoding="utf-8"), encoding="utf-8")
    manifest["done_certification_input_refs"]["control_surface_obedience_result_ref"] = str(path)

    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is True


def test_promotion_stage_contract_gate_blocks_when_required_eval_missing(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    contract = json.loads((_REPO_ROOT / "contracts" / "examples" / "stage_contracts" / "pqx_stage_contract.json").read_text(encoding="utf-8"))
    contract["verification"]["required_eval_types"] = ["certification_status", "promotion_control_allow", "external_gate_eval"]
    contract_path = tmp_path / "promotion.stage_contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    manifest["stage_contract_path"] = str(contract_path)

    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "STAGE_CONTRACT_MISSING_REQUIRED_EVAL" in str(decision.reason)


def test_promotion_stage_contract_gate_allows_when_contract_signals_present() -> None:
    manifest = _base_manifest("certification_pending")
    manifest["stage_contract_path"] = str(_REPO_ROOT / "contracts" / "examples" / "stage_contracts" / "pqx_stage_contract.json")

    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is True


def test_stage_contract_continuity_gate_blocks_invalid_resume() -> None:
    manifest = _base_manifest("certification_pending")
    manifest["stage_contract_path"] = str(_REPO_ROOT / "contracts" / "examples" / "stage_contracts" / "pqx_stage_contract.json")
    manifest["request_resume"] = True
    manifest["checkpoint_age_minutes"] = 999
    manifest["has_resume_validation_evidence"] = False
    manifest["checkpoint_record"] = {
        "artifact_type": "checkpoint_record",
        "checkpoint_id": "cp-1",
        "state_snapshot": {
            "required_inputs": ["a"],
            "observed_outputs": ["b"],
            "eval_refs": ["eval-1"],
            "control_refs": ["ctrl-1"],
            "pending_actions": ["pending"],
        },
    }

    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "continuity gate blocked" in str(decision.reason)


def test_stage_contract_continuity_gate_blocks_missing_handoff_in_reset_mode(tmp_path: Path) -> None:
    manifest = _base_manifest("certification_pending")
    contract = json.loads((_REPO_ROOT / "contracts" / "examples" / "stage_contracts" / "pqx_stage_contract.json").read_text(encoding="utf-8"))
    contract["execution_mode"] = "reset_with_handoff"
    path = tmp_path / "reset_contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    manifest["stage_contract_path"] = str(path)

    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "HANDOFF_REQUIRED" in str(decision.reason)
