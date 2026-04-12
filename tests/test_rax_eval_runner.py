from __future__ import annotations

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.rax_assurance import evaluate_rax_control_readiness
from spectrum_systems.modules.runtime.rax_eval_runner import (
    enforce_required_rax_eval_coverage,
    load_rax_eval_case_set,
    load_rax_eval_registry,
    run_rax_eval_runner,
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


def test_rax_eval_registry_example_is_valid_and_required_split_explicit() -> None:
    registry = load_rax_eval_registry()
    required_types = [entry["eval_type"] for entry in registry["eval_definitions"] if entry["required"]]
    assert len(required_types) == 9
    assert "rax_control_readiness" in required_types


def test_rax_eval_case_set_example_is_valid_and_includes_adversarial_and_baseline() -> None:
    case_set = load_rax_eval_case_set()
    classes = {case["case_class"] for case in case_set["cases"]}
    assert {"baseline", "adversarial", "failure_class"}.issubset(classes)


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
    readiness = evaluate_rax_control_readiness(
        batch="RAX-EVAL-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=out["required_eval_coverage"],
    )
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
    def _etype(item: dict) -> str:
        return next(mode.split(":",1)[1] for mode in item["failure_modes"] if mode.startswith("eval_type:"))

    eval_results = [item for item in out["eval_results"] if _etype(item) != "rax_owner_intent_alignment"]
    required_eval_coverage = dict(out["required_eval_coverage"])
    required_eval_coverage["present_eval_types"] = [item for item in required_eval_coverage["present_eval_types"] if item != "rax_owner_intent_alignment"]

    enforcement = enforce_required_rax_eval_coverage(eval_results=eval_results, required_eval_coverage=required_eval_coverage)
    assert enforcement["blocked"] is True
    assert "missing_required_eval_artifact" in enforcement["reasons"]


def test_readiness_example_contract_validates() -> None:
    validate_artifact(load_example("rax_control_readiness_record"), "rax_control_readiness_record")
    validate_artifact(load_example("rax_eval_registry"), "rax_eval_registry")
    validate_artifact(load_example("rax_eval_case_set"), "rax_eval_case_set")
