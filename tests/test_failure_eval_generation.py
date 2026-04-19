from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.modules.runtime.failure_eval_generation import (
    admit_generated_eval_case,
    generate_and_admit_failure_eval,
    generate_eval_case_from_failure_record,
)


_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "failure_eval_generation_cases.json"


def _fixtures() -> dict:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def test_failure_record_with_missing_trace_lineage_generates_valid_eval_case() -> None:
    case = generate_eval_case_from_failure_record(_fixtures()["missing_trace_lineage_failure"])

    assert case["artifact_type"] == "generated_eval_case"
    assert case["reason_code"] == "missing_trace_or_lineage"
    assert case["source_failure_artifact_id"] == "FAIL-TRACE-LINEAGE-001"


def test_replay_mismatch_failure_generates_valid_eval_case() -> None:
    case = generate_eval_case_from_failure_record(_fixtures()["replay_mismatch_failure"])

    assert case["reason_code"] == "replay_mismatch"
    assert case["expected_outcome"] == "pause_with_reason_code:replay_mismatch"
    assert case["input_conditions"]["failure_state"] == "paused"


def test_missing_required_eval_failure_generates_valid_eval_case() -> None:
    case = generate_eval_case_from_failure_record(_fixtures()["missing_required_eval_failure"])

    assert case["reason_code"] == "missing_required_eval_result"
    assert case["input_conditions"]["failed_evals"] == ["debuggability_valid"]
    assert case["input_conditions"]["failure_state"] == "halted"


def test_generated_eval_case_uses_neutral_failure_state_vocabulary() -> None:
    case = generate_eval_case_from_failure_record(_fixtures()["missing_required_eval_failure"])
    assert case["scenario_name"].startswith("halted__")
    assert case["input_conditions"]["failure_state"] in {"halted", "paused", "failed_closed"}


def test_generated_eval_ids_are_deterministic() -> None:
    failure = _fixtures()["missing_required_eval_failure"]

    first = generate_eval_case_from_failure_record(failure)
    second = generate_eval_case_from_failure_record(failure)

    assert first["artifact_id"] == second["artifact_id"]


def test_generated_eval_admission_rejects_malformed_non_deterministic_case() -> None:
    case = generate_eval_case_from_failure_record(_fixtures()["missing_required_eval_failure"])
    case["determinism_requirements"] = []
    case["expected_outcome"] = ""

    admission = admit_generated_eval_case(case)

    assert admission["admitted"] is False
    assert "non_deterministic_eval_case" in admission["denial_reasons"]
    assert "missing_required_field:expected_outcome" in admission["denial_reasons"]


def test_malformed_normalization_mapping_is_rejected() -> None:
    case = generate_eval_case_from_failure_record(
        _fixtures()["missing_required_eval_failure"],
        normalized_reason_code="missing_required_eval_normalized",
    )
    case["reason_code_normalization"] = {"normalized_from_reason_code": case["reason_code"]}

    admission = admit_generated_eval_case(case)

    assert admission["admitted"] is False
    assert "incomplete_reason_code_normalization_mapping" in admission["denial_reasons"]


def test_mismatched_normalization_values_are_rejected() -> None:
    case = generate_eval_case_from_failure_record(
        _fixtures()["missing_required_eval_failure"],
        normalized_reason_code="missing_required_eval_normalized",
    )
    case["reason_code_normalization"] = {
        "normalized_from_reason_code": "wrong_source_reason",
        "normalized_to_reason_code": "wrong_target_reason",
    }

    admission = admit_generated_eval_case(case)

    assert admission["admitted"] is False
    assert "reason_code_normalization_from_mismatch" in admission["denial_reasons"]
    assert "reason_code_normalization_to_mismatch" in admission["denial_reasons"]


def test_generated_eval_admission_accepts_valid_case() -> None:
    failure = _fixtures()["missing_required_eval_failure"]
    case = generate_eval_case_from_failure_record(failure)

    admission = admit_generated_eval_case(case, source_failure_record=failure)

    assert admission["admitted"] is True
    assert admission["denial_reasons"] == []


def test_invalid_expected_outcome_is_rejected() -> None:
    case = generate_eval_case_from_failure_record(_fixtures()["missing_required_eval_failure"])
    case["expected_outcome"] = "unbounded_outcome"

    admission = admit_generated_eval_case(case)

    assert admission["admitted"] is False
    assert "expected_outcome_not_bounded" in admission["denial_reasons"]


def test_valid_bounded_expected_outcome_is_admitted() -> None:
    case = generate_eval_case_from_failure_record(_fixtures()["replay_mismatch_failure"])
    case["expected_outcome"] = "fail_closed_with_reason_code:replay_mismatch"

    admission = admit_generated_eval_case(case)

    assert admission["admitted"] is True


def test_generated_eval_preserves_reason_code_linkage_to_source_failure() -> None:
    failure = _fixtures()["replay_mismatch_failure"]
    case = generate_eval_case_from_failure_record(failure)

    assert case["reason_code"] == failure["reason_code"]
    assert case["expected_reason_code"] == failure["reason_code"]


def test_generated_eval_admission_requires_source_failure_artifact_id() -> None:
    case = generate_eval_case_from_failure_record(_fixtures()["missing_required_eval_failure"])
    case["source_failure_artifact_id"] = ""

    admission = admit_generated_eval_case(case)

    assert admission["admitted"] is False
    assert "missing_required_field:source_failure_artifact_id" in admission["denial_reasons"]


def test_end_to_end_failure_to_eval_generation_and_admission() -> None:
    failure = _fixtures()["missing_required_eval_failure"]

    result = generate_and_admit_failure_eval(failure)

    case = result["generated_eval_case"]
    admission = result["generated_eval_admission_record"]

    assert case["source_failure_artifact_id"] == failure["artifact_id"]
    assert case["expected_reason_code"] == failure["reason_code"]
    assert admission["admitted"] is True
    assert admission["generated_eval_artifact_id"] == case["artifact_id"]
