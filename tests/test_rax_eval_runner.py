from __future__ import annotations

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.rax_assurance import evaluate_rax_control_readiness
from spectrum_systems.modules.runtime.rax_eval_runner import (
    enforce_rax_control_advancement,
    enforce_required_rax_eval_coverage,
    load_rax_eval_case_set,
    load_rax_eval_registry,
    run_rax_eval_runner,
    build_feedback_loop_record,
    build_rax_health_snapshot,
    build_rax_drift_signal_record,
    build_rax_unknown_state_record,
    generate_adversarial_pattern_candidates,
)


def _input_assurance_ok() -> dict:
    return {
        "passed": True,
        "details": ["semantic_intent_sufficient"],
        "failure_classification": "none",
        "stop_condition_triggered": False,
    }


def _output_assurance_ok() -> dict:
    return {
        "passed": True,
        "details": ["output_semantically_aligned"],
        "failure_classification": "none",
        "stop_condition_triggered": False,
    }


def _governed_evidence_ok() -> dict:
    return {
        "assurance_audit": {"acceptance_decision": "accept_candidate", "failure_classification": "none"},
        "trace_integrity_evidence": {"trace_linked": True, "trace_complete": True},
        "lineage_provenance_evidence": {"lineage_valid": True},
        "dependency_state": {"graph_integrity": True, "unresolved_dependencies": []},
        "authority_records": {"docs/roadmaps/system_roadmap.md#RAX-INTERFACE-24-01": "1.3.112"},
    }


def _eval_type(item: dict) -> str:
    return next(mode.split(":", 1)[1] for mode in item["failure_modes"] if mode.startswith("eval_type:"))


def _readiness_from(out: dict, **overrides: dict) -> dict:
    kwargs = _governed_evidence_ok()
    kwargs.update(overrides)
    return evaluate_rax_control_readiness(
        batch="RAX-EVAL-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=out["required_eval_coverage"],
        **kwargs,
    )


def test_rax_eval_registry_example_is_valid_and_required_split_explicit() -> None:
    registry = load_rax_eval_registry()
    required_types = [entry["eval_type"] for entry in registry["eval_definitions"] if entry["required"]]
    assert len(required_types) == 9
    assert "rax_control_readiness" in required_types


def test_rax_eval_case_set_example_is_valid_and_includes_adversarial_and_baseline() -> None:
    case_set = load_rax_eval_case_set()
    classes = {case["case_class"] for case in case_set["cases"]}
    assert {"baseline", "adversarial", "failure_class"}.issubset(classes)



def test_eval_case_set_contains_novel_adversarial_semantic_case() -> None:
    case_set = load_rax_eval_case_set()
    case = next(case for case in case_set["cases"] if case["eval_case_id"] == "rax-case-novel-adversarial-semantic-ambiguity")
    assert case["case_class"] == "adversarial"
    assert case["eval_type"] == "rax_input_semantic_sufficiency"
    assert "semantic_intent_insufficient" in case["reason_codes"]

def test_runner_emits_structured_eval_results_and_summary() -> None:
    out = run_rax_eval_runner(
        run_id="rax-eval-run-001",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="12121212-1212-4121-8121-121212121212",
        input_assurance=_input_assurance_ok(),
        output_assurance=_output_assurance_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
    )
    assert out["eval_results"]
    assert out["eval_summary"]["artifact_type"] == "eval_summary"
    for result in out["eval_results"]:
        validate_artifact(result, "eval_result")
        assert any(mode.startswith("runner:rax_eval_runner") for mode in result["failure_modes"])


def test_missing_required_eval_artifact_fails_closed() -> None:
    out = run_rax_eval_runner(
        run_id="rax-eval-run-002",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="13131313-1313-4131-8131-131313131313",
        input_assurance=_input_assurance_ok(),
        output_assurance=_output_assurance_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
        omit_eval_types=["rax_trace_integrity"],
    )
    assert "rax_trace_integrity" in out["required_eval_coverage"]["missing_required_eval_types"]
    assert out["required_eval_coverage"]["overall_result"] == "fail"


def test_tests_pass_eval_fail_is_blocking() -> None:
    out = run_rax_eval_runner(
        run_id="rax-eval-run-003",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="14141414-1414-4141-8141-141414141414",
        input_assurance={"passed": False, "details": ["semantic_intent_insufficient"], "failure_classification": "invalid_input"},
        output_assurance=_output_assurance_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
    )
    readiness = _readiness_from(out)
    assert readiness["ready_for_control"] is False
    assert "tests_pass_eval_fail" in readiness["blocking_reasons"]


def test_partial_eval_set_and_summary_mismatch_blocked() -> None:
    out = run_rax_eval_runner(
        run_id="rax-eval-run-004",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="15151515-1515-4151-8151-151515151515",
        input_assurance=_input_assurance_ok(),
        output_assurance=_output_assurance_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
    )
    eval_results = [item for item in out["eval_results"] if _eval_type(item) != "rax_owner_intent_alignment"]
    required_eval_coverage = dict(out["required_eval_coverage"])
    required_eval_coverage["present_eval_types"] = [
        item for item in required_eval_coverage["present_eval_types"] if item != "rax_owner_intent_alignment"
    ]

    enforcement = enforce_required_rax_eval_coverage(eval_results=eval_results, required_eval_coverage=required_eval_coverage)
    assert enforcement["blocked"] is True
    assert "missing_required_eval_artifact" in enforcement["reasons"]


def test_mandatory_advancement_gate_blocks_missing_readiness_artifact() -> None:
    gate = enforce_rax_control_advancement(readiness_record=None)
    assert gate["allowed"] is False
    assert "missing_control_readiness_artifact" in gate["blocking_reasons"]


def test_mandatory_advancement_gate_blocks_malformed_artifact() -> None:
    gate = enforce_rax_control_advancement(readiness_record={"artifact_type": "rax_control_readiness_record"})
    assert gate["allowed"] is False
    assert "malformed_control_readiness_artifact" in gate["blocking_reasons"]


def test_fake_readiness_from_partial_eval_set_fails_closed() -> None:
    out = run_rax_eval_runner(
        run_id="redteam-17",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="00000000-0000-4000-8000-000000000017",
        input_assurance=_input_assurance_ok(),
        output_assurance=_output_assurance_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
        omit_eval_types=["rax_trace_integrity", "rax_owner_intent_alignment"],
    )
    forged_cov = {
        "required_eval_types": out["required_eval_coverage"]["required_eval_types"],
        "present_eval_types": out["required_eval_coverage"]["required_eval_types"],
        "missing_required_eval_types": [],
        "overall_result": "pass",
    }
    readiness = evaluate_rax_control_readiness(
        batch="RAX-EVAL-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=forged_cov,
        **_governed_evidence_ok(),
    )
    assert readiness["ready_for_control"] is False
    assert "missing_required_eval_types" in readiness["blocking_reasons"]


def test_contradictory_signals_force_not_ready() -> None:
    contradictory_results = [
        {
            "artifact_type": "eval_result",
            "schema_version": "1.0.0",
            "eval_case_id": "x:rax_input_semantic_sufficiency",
            "run_id": "x",
            "trace_id": "t",
            "result_status": "fail",
            "score": 0.0,
            "failure_modes": ["eval_type:rax_input_semantic_sufficiency", "semantic_intent_insufficient", "runner:rax_eval_runner:1.0.0"],
            "provenance_refs": ["roadmap_step_contract:RAX-INTERFACE-24-01", "trace://t"],
        }
    ]
    cov = {
        "required_eval_types": [
            "rax_input_semantic_sufficiency",
            "rax_owner_intent_alignment",
            "rax_normalization_integrity",
            "rax_output_semantic_alignment",
            "rax_acceptance_check_strength",
            "rax_trace_integrity",
            "rax_version_authority_alignment",
            "rax_regression_against_baseline",
            "rax_control_readiness",
        ],
        "present_eval_types": [
            "rax_input_semantic_sufficiency",
            "rax_owner_intent_alignment",
            "rax_normalization_integrity",
            "rax_output_semantic_alignment",
            "rax_acceptance_check_strength",
            "rax_trace_integrity",
            "rax_version_authority_alignment",
            "rax_regression_against_baseline",
            "rax_control_readiness",
        ],
        "missing_required_eval_types": [],
        "overall_result": "pass",
    }
    readiness = evaluate_rax_control_readiness(
        batch="RAX-EVAL-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary={
            "artifact_type": "eval_summary",
            "schema_version": "1.0.0",
            "trace_id": "t",
            "eval_run_id": "x",
            "pass_rate": 1.0,
            "failure_rate": 0.0,
            "drift_rate": 0.0,
            "reproducibility_score": 1.0,
            "system_status": "healthy",
        },
        eval_results=contradictory_results,
        required_eval_coverage=cov,
        **_governed_evidence_ok(),
    )
    assert readiness["ready_for_control"] is False
    assert "contradictory_eval_signals" in readiness["blocking_reasons"]
    assert readiness["decision"] != "ready"


def test_artifact_present_but_not_trace_linked_fails_closed() -> None:
    out = run_rax_eval_runner(
        run_id="redteam-24",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="00000000-0000-4000-8000-000000000024",
        input_assurance=_input_assurance_ok(),
        output_assurance=_output_assurance_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
    )
    readiness = _readiness_from(out, trace_integrity_evidence={"trace_linked": False, "trace_complete": True})
    assert readiness["ready_for_control"] is False
    assert "artifact_not_trace_linked" in readiness["blocking_reasons"]


def test_artifact_present_but_not_lineage_valid_fails_closed() -> None:
    out = run_rax_eval_runner(
        run_id="redteam-25",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="00000000-0000-4000-8000-000000000025",
        input_assurance=_input_assurance_ok(),
        output_assurance=_output_assurance_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
    )
    readiness = _readiness_from(out, lineage_provenance_evidence={"lineage_valid": False})
    assert readiness["ready_for_control"] is False
    assert "artifact_lineage_invalid" in readiness["blocking_reasons"]


def test_fake_authority_version_alignment_fails_closed() -> None:
    out = run_rax_eval_runner(
        run_id="redteam-13",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="00000000-0000-4000-8000-000000000013",
        input_assurance={"passed": False, "details": ["source_version_drift: payload=9.9.9 authority=1.3.112"], "failure_classification": "stale_reference"},
        output_assurance=_output_assurance_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
    )
    readiness = _readiness_from(out)
    assert readiness["ready_for_control"] is False
    assert readiness["version_authority_aligned"] is False


def test_dependency_graph_corruption_fails_closed() -> None:
    out = run_rax_eval_runner(
        run_id="redteam-15",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="00000000-0000-4000-8000-000000000015",
        input_assurance=_input_assurance_ok(),
        output_assurance=_output_assurance_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
    )
    readiness = _readiness_from(out, dependency_state={"graph_integrity": False, "unresolved_dependencies": ["MISSING-STEP-01"]})
    assert readiness["ready_for_control"] is False
    assert "dependency_graph_corrupt" in readiness["blocking_reasons"]


def test_cross_run_inconsistency_triggers_hold_not_ready() -> None:
    out_a = run_rax_eval_runner(
        run_id="redteam-22-a",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="00000000-0000-4000-8000-000000000221",
        input_assurance=_input_assurance_ok(),
        output_assurance=_output_assurance_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
    )
    out_b = run_rax_eval_runner(
        run_id="redteam-22-b",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="00000000-0000-4000-8000-000000000222",
        input_assurance={"passed": False, "details": ["semantic_intent_insufficient"], "failure_classification": "invalid_input"},
        output_assurance=_output_assurance_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
    )
    replay_store: dict = {}
    first = _readiness_from(out_a, replay_baseline_store=replay_store, replay_key="same-input-same-tests")
    second = _readiness_from(out_b, replay_baseline_store=replay_store, replay_key="same-input-same-tests")
    assert first["decision"] in {"ready", "block"}
    assert second["ready_for_control"] is False
    assert second["decision"] == "hold"
    assert "cross_run_eval_signal_inconsistency" in second["blocking_reasons"]


def test_readiness_example_contract_validates() -> None:
    validate_artifact(load_example("rax_control_readiness_record"), "rax_control_readiness_record")
    validate_artifact(load_example("rax_eval_registry"), "rax_eval_registry")
    validate_artifact(load_example("rax_eval_case_set"), "rax_eval_case_set")


def test_failure_to_eval_autogeneration_emits_pattern_and_candidate() -> None:
    out = run_rax_eval_runner(
        run_id="rax-eval-run-005",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="16161616-1616-4161-8161-161616161616",
        input_assurance={"passed": False, "details": ["semantic_intent_insufficient"], "failure_classification": "invalid_input"},
        output_assurance=_output_assurance_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
    )
    assert out["failure_pattern_records"]
    assert out["eval_case_candidates"]
    validate_artifact(out["failure_pattern_records"][0], "rax_failure_pattern_record")
    validate_artifact(out["eval_case_candidates"][0], "rax_failure_eval_candidate")


def test_adversarial_pattern_generation_is_deterministic() -> None:
    first = generate_adversarial_pattern_candidates(seed="seed-1", target_ref="roadmap_step_contract:RAX-INTERFACE-24-01")
    second = generate_adversarial_pattern_candidates(seed="seed-1", target_ref="roadmap_step_contract:RAX-INTERFACE-24-01")
    assert first == second
    assert len(first) == 5
    validate_artifact(first[0], "rax_adversarial_pattern_candidate")


def test_feedback_loop_record_tracks_recurrence() -> None:
    record = build_feedback_loop_record(
        record_id="feedback-loop-test",
        originating_failure_pattern_ref="rax-failure-x",
        fix_artifact_refs=["fix://rax/1"],
        eval_artifact_refs_added=["rax-failure-x:eval-candidate"],
        historical_failure_classes=["invalid_input", "dependency_blocked"],
        current_failure_class="invalid_input",
        recurrence_window="P14D",
        readiness_delta=-0.2,
        confidence_delta=-0.1,
    )
    assert record["recurrence_detected"] is True
    validate_artifact(record, "rax_feedback_loop_record")


def test_health_snapshot_threshold_degradation_sets_candidate_posture() -> None:
    thresholds = {
        "readiness_pass_rate": {"warn_min": 0.9, "freeze_candidate_min": 0.8, "block_candidate_min": 0.7},
        "eval_coverage_rate": {"warn_min": 0.95, "freeze_candidate_min": 0.9, "block_candidate_min": 0.8},
        "semantic_failure_rate": {"warn_min": 0.0, "freeze_candidate_min": 0.0, "block_candidate_min": 0.0},
        "readiness_bypass_attempt_rate": {"warn_min": 0.0, "freeze_candidate_min": 0.0, "block_candidate_min": 0.0},
        "replay_consistency_rate": {"warn_min": 0.95, "freeze_candidate_min": 0.9, "block_candidate_min": 0.8},
        "trace_completeness_rate": {"warn_min": 0.95, "freeze_candidate_min": 0.9, "block_candidate_min": 0.8},
        "lineage_validity_rate": {"warn_min": 0.95, "freeze_candidate_min": 0.9, "block_candidate_min": 0.8},
        "contradiction_rate": {"warn_min": 0.0, "freeze_candidate_min": 0.0, "block_candidate_min": 0.0},
    }
    snapshot = build_rax_health_snapshot(
        snapshot_id="health-test",
        window_ref="window://current",
        metrics={
            "readiness_pass_rate": 0.6,
            "eval_coverage_rate": 1.0,
            "semantic_failure_rate": 0.0,
            "readiness_bypass_attempt_rate": 0.0,
            "replay_consistency_rate": 1.0,
            "trace_completeness_rate": 1.0,
            "lineage_validity_rate": 1.0,
            "contradiction_rate": 0.0,
        },
        thresholds=thresholds,
    )
    assert snapshot["candidate_posture"] == "block_candidate"


def test_drift_signal_detection_blocks_when_exceeding_threshold() -> None:
    drift = build_rax_drift_signal_record(
        signal_id="drift-test",
        baseline_window_ref="window://baseline",
        current_window_ref="window://current",
        baseline_metrics={"eval_coverage_rate": 1.0, "readiness_pass_rate": 1.0, "semantic_failure_rate": 0.0, "lineage_validity_rate": 1.0, "trace_completeness_rate": 1.0},
        current_metrics={"eval_coverage_rate": 0.5, "readiness_pass_rate": 0.5, "semantic_failure_rate": 0.4, "lineage_validity_rate": 0.4, "trace_completeness_rate": 0.6},
        drift_thresholds={"eval_signal_drift": 0.1, "readiness_outcome_drift": 0.1, "semantic_classification_drift": 0.1, "version_authority_drift": 0.1, "trace_lineage_completeness_drift": 0.1},
    )
    assert drift["candidate_posture"] == "block_candidate"


def test_unknown_state_record_never_allows_advancement() -> None:
    unknown = build_rax_unknown_state_record(
        record_id="unknown-test",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        unknown_reasons=["required_signal_missing"],
        evidence_refs=["roadmap_step_contract:RAX-INTERFACE-24-01"],
    )
    assert unknown["candidate_ready"] is False
    assert unknown["advancement_allowed"] is False


def test_readiness_record_populates_conditions_under_which_ready_changes() -> None:
    out = run_rax_eval_runner(
        run_id="rax-eval-run-006",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="17171717-1717-4171-8171-171717171717",
        input_assurance=_input_assurance_ok(),
        output_assurance=_output_assurance_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
        omit_eval_types=["rax_trace_integrity"],
    )
    readiness = _readiness_from(out)
    assert readiness["ready_for_control"] is False
    assert readiness["conditions_under_which_ready_changes"]


def test_precert_alignment_blocks_candidate_ready_when_not_aligned() -> None:
    out = run_rax_eval_runner(
        run_id="rax-eval-run-007",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="18181818-1818-4181-8181-181818181818",
        input_assurance=_input_assurance_ok(),
        output_assurance=_output_assurance_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
    )
    readiness = _readiness_from(out)
    assert "pre_certification_alignment_not_ready" in readiness["blocking_reasons"]
