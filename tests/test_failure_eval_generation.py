from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.modules.runtime.failure_eval_generation import (
    admit_generated_eval_case,
    build_generated_eval_promotion_decision_record,
    build_generated_eval_promotion_request_record,
    build_generated_eval_promotion_rollback_record,
    build_generated_eval_candidate_queue,
    build_generated_eval_candidate_records,
    build_generated_eval_candidate_assessment_records,
    execute_generated_eval_promotion_gate,
    execute_generated_eval_promotion_rollback,
    generate_eval_candidate_review_bundle,
    generate_and_admit_failure_eval,
    generate_eval_case_from_failure_record,
)
from spectrum_systems.modules.runtime.required_eval_coverage import load_required_eval_registry


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


def test_malformed_normalization_mapping_is_not_recommended() -> None:
    case = generate_eval_case_from_failure_record(
        _fixtures()["missing_required_eval_failure"],
        normalized_reason_code="missing_required_eval_normalized",
    )
    case["reason_code_normalization"] = {"normalized_from_reason_code": case["reason_code"]}

    admission = admit_generated_eval_case(case)

    assert admission["admitted"] is False
    assert "incomplete_reason_code_normalization_mapping" in admission["denial_reasons"]


def test_mismatched_normalization_values_are_not_recommended() -> None:
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


def test_invalid_expected_outcome_is_not_recommended() -> None:
    case = generate_eval_case_from_failure_record(_fixtures()["missing_required_eval_failure"])
    case["expected_outcome"] = "unbounded_outcome"

    admission = admit_generated_eval_case(case)

    assert admission["admitted"] is False
    assert "expected_outcome_not_bounded" in admission["denial_reasons"]


def test_expected_outcome_reason_code_suffix_must_match_expected_reason_code() -> None:
    case = generate_eval_case_from_failure_record(_fixtures()["missing_required_eval_failure"])
    case["expected_outcome"] = "halt_with_reason_code:other_reason"

    admission = admit_generated_eval_case(case)

    assert admission["admitted"] is False
    assert "expected_outcome_reason_code_mismatch" in admission["denial_reasons"]


def test_valid_bounded_expected_outcome_is_admitted() -> None:
    case = generate_eval_case_from_failure_record(_fixtures()["replay_mismatch_failure"])
    case["expected_outcome"] = "fail_closed_with_reason_code:replay_mismatch"

    admission = admit_generated_eval_case(case)

    assert admission["admitted"] is True


def test_replay_inputs_failed_evals_must_be_list() -> None:
    case = generate_eval_case_from_failure_record(_fixtures()["missing_required_eval_failure"])
    case["input_conditions"]["failed_evals"] = "not-a-list"

    admission = admit_generated_eval_case(case)

    assert admission["admitted"] is False
    assert "failed_evals_not_list" in admission["denial_reasons"]


def test_replay_inputs_missing_artifacts_must_be_list() -> None:
    case = generate_eval_case_from_failure_record(_fixtures()["missing_required_eval_failure"])
    case["input_conditions"]["missing_artifacts"] = "not-a-list"

    admission = admit_generated_eval_case(case)

    assert admission["admitted"] is False
    assert "missing_artifacts_not_list" in admission["denial_reasons"]


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


def _admitted_pair(failure_key: str, *, created_at: str | None = None) -> dict:
    failure = dict(_fixtures()[failure_key])
    if created_at:
        failure["timestamp"] = created_at
    result = generate_and_admit_failure_eval(failure)
    return result


def test_admitted_generated_evals_produce_candidate_records() -> None:
    records = build_generated_eval_candidate_records(
        [
            _admitted_pair("missing_required_eval_failure"),
            _admitted_pair("replay_mismatch_failure"),
        ]
    )

    assert len(records) == 2
    assert all(record["artifact_type"] == "generated_eval_candidate_record" for record in records)


def test_repeated_failures_increment_occurrence_count() -> None:
    staging = build_generated_eval_candidate_records(
        [
            _admitted_pair("missing_required_eval_failure", created_at="2026-04-19T00:02:00Z"),
            _admitted_pair("missing_required_eval_failure", created_at="2026-04-19T00:05:00Z"),
        ]
    )

    assert len(staging) == 1
    assert staging[0]["occurrence_count"] == 2
    assert staging[0]["first_seen_at"] == "2026-04-19T00:02:00Z"
    assert staging[0]["last_seen_at"] == "2026-04-19T00:05:00Z"


def test_staging_status_defaults_to_pending_review() -> None:
    staging = build_generated_eval_candidate_records([_admitted_pair("replay_mismatch_failure")])
    assert staging[0]["staging_status"] == "pending_review"


def test_candidate_queue_includes_correct_candidates() -> None:
    staging = build_generated_eval_candidate_records(
        [
            _admitted_pair("missing_required_eval_failure"),
            _admitted_pair("replay_mismatch_failure"),
        ]
    )
    queue = build_generated_eval_candidate_queue(staging, high_priority_threshold=2)

    generated_eval_ids = sorted(record["generated_eval_artifact_id"] for record in staging)
    assert queue["generated_eval_ids"] == generated_eval_ids
    assert queue["total_candidates"] == 2


def test_candidate_queue_high_priority_threshold_selects_recurring_candidates() -> None:
    staging = build_generated_eval_candidate_records(
        [
            _admitted_pair("missing_required_eval_failure", created_at="2026-04-19T00:02:00Z"),
            _admitted_pair("missing_required_eval_failure", created_at="2026-04-19T00:03:00Z"),
            _admitted_pair("replay_mismatch_failure", created_at="2026-04-19T00:04:00Z"),
        ]
    )
    queue = build_generated_eval_candidate_queue(staging, high_priority_threshold=2)

    assert len(queue["high_priority_candidates"]) == 1
    recurring_id = next(record["generated_eval_artifact_id"] for record in staging if record["occurrence_count"] == 2)
    assert queue["high_priority_candidates"][0] == recurring_id


def test_candidate_assessment_emits_deterministic_priority_review_or_observe() -> None:
    staging = build_generated_eval_candidate_records(
        [
            _admitted_pair("missing_required_eval_failure", created_at="2026-04-19T00:02:00Z"),
            _admitted_pair("missing_required_eval_failure", created_at="2026-04-19T00:03:00Z"),
            _admitted_pair("replay_mismatch_failure", created_at="2026-04-19T00:04:00Z"),
        ]
    )
    recommendations = build_generated_eval_candidate_assessment_records(staging, assessment_threshold=2)

    by_eval_id = {record["generated_eval_artifact_id"]: record for record in recommendations}
    recurring_eval_id = next(record["generated_eval_artifact_id"] for record in staging if record["occurrence_count"] == 2)
    single_eval_id = next(record["generated_eval_artifact_id"] for record in staging if record["occurrence_count"] == 1)

    assert by_eval_id[recurring_eval_id]["recommendation"] == "priority_review"
    assert by_eval_id[single_eval_id]["recommendation"] == "observe"


def test_staging_aggregation_does_not_mutate_source_artifacts() -> None:
    pair = _admitted_pair("missing_required_eval_failure")
    original_case = json.loads(json.dumps(pair["generated_eval_case"]))
    original_admission = json.loads(json.dumps(pair["generated_eval_admission_record"]))

    _ = build_generated_eval_candidate_records([pair])

    assert pair["generated_eval_case"] == original_case
    assert pair["generated_eval_admission_record"] == original_admission


def test_staging_record_ids_are_deterministic_across_runs() -> None:
    inputs = [
        _admitted_pair("missing_required_eval_failure"),
        _admitted_pair("replay_mismatch_failure"),
    ]
    first = build_generated_eval_candidate_records(inputs)
    second = build_generated_eval_candidate_records(inputs)

    assert [record["artifact_id"] for record in first] == [record["artifact_id"] for record in second]


def test_end_to_end_failure_to_candidate_staging_queue_and_assessment_bundle() -> None:
    bundle = generate_eval_candidate_review_bundle(
        [
            _admitted_pair("missing_required_eval_failure", created_at="2026-04-19T00:02:00Z"),
            _admitted_pair("missing_required_eval_failure", created_at="2026-04-19T00:05:00Z"),
            _admitted_pair("replay_mismatch_failure", created_at="2026-04-19T00:04:00Z"),
        ],
        high_priority_threshold=2,
        assessment_threshold=2,
    )

    assert len(bundle["candidate_records"]) == 2
    assert bundle["candidate_queue"]["artifact_type"] == "generated_eval_candidate_queue"
    assert len(bundle["candidate_assessments"]) == 2
    assert bundle["candidate_queue"]["high_priority_candidates"]


def _promotion_setup(*, occurrence_count: int = 2) -> dict:
    pair = _admitted_pair("missing_required_eval_failure")
    generated_eval_case = pair["generated_eval_case"]
    admission_record = pair["generated_eval_admission_record"]
    candidate_record = {
        "artifact_type": "generated_eval_candidate_record",
        "artifact_id": "GES-TEST-001",
        "generated_eval_artifact_id": generated_eval_case["artifact_id"],
        "source_failure_artifact_id": generated_eval_case["source_failure_artifact_id"],
        "source_failure_artifact_ids": [generated_eval_case["source_failure_artifact_id"]],
        "reason_code": generated_eval_case["reason_code"],
        "staging_status": "pending_review",
        "occurrence_count": occurrence_count,
        "first_seen_at": generated_eval_case["created_at"],
        "last_seen_at": generated_eval_case["created_at"],
        "created_at": generated_eval_case["created_at"],
    }
    request = build_generated_eval_promotion_request_record(
        generated_eval_case,
        candidate_record,
        request_origin="candidate_assessment",
        justification="Recurring admitted candidate with deterministic lineage.",
    )
    decision = build_generated_eval_promotion_decision_record(
        request,
        decision="approved",
        decided_by="runtime-governance-reviewer",
        rationale="Replay linkage and promotion lineage reviewed.",
    )
    return {
        "generated_eval_case": generated_eval_case,
        "admission_record": admission_record,
        "candidate_record": candidate_record,
        "request": request,
        "decision": decision,
        "required_eval_registry": load_required_eval_registry(),
    }


def test_promotion_without_admission_record_blocks() -> None:
    setup = _promotion_setup()
    output = execute_generated_eval_promotion_gate(
        generated_eval_case=setup["generated_eval_case"],
        generated_eval_admission_record=None,
        candidate_record=setup["candidate_record"],
        promotion_request_record=setup["request"],
        promotion_decision_record=setup["decision"],
        required_eval_registry=setup["required_eval_registry"],
    )
    assert output["generated_eval_promotion_result_record"]["promoted"] is False
    assert "missing_generated_eval_admission_record" in output["generated_eval_promotion_result_record"]["blocked_reasons"]


def test_promotion_with_no_candidate_record_blocks() -> None:
    setup = _promotion_setup()
    output = execute_generated_eval_promotion_gate(
        generated_eval_case=setup["generated_eval_case"],
        generated_eval_admission_record=setup["admission_record"],
        candidate_record=None,
        promotion_request_record=setup["request"],
        promotion_decision_record=setup["decision"],
        required_eval_registry=setup["required_eval_registry"],
    )
    assert output["generated_eval_promotion_result_record"]["promoted"] is False
    assert "missing_candidate_record" in output["generated_eval_promotion_result_record"]["blocked_reasons"]


def test_promotion_below_threshold_blocks() -> None:
    setup = _promotion_setup(occurrence_count=1)
    output = execute_generated_eval_promotion_gate(
        generated_eval_case=setup["generated_eval_case"],
        generated_eval_admission_record=setup["admission_record"],
        candidate_record=setup["candidate_record"],
        promotion_request_record=setup["request"],
        promotion_decision_record=setup["decision"],
        required_eval_registry=setup["required_eval_registry"],
        occurrence_threshold=2,
    )
    assert output["generated_eval_promotion_result_record"]["promoted"] is False
    assert "occurrence_count_below_threshold" in output["generated_eval_promotion_result_record"]["blocked_reasons"]


def test_promotion_without_request_artifact_blocks() -> None:
    setup = _promotion_setup()
    output = execute_generated_eval_promotion_gate(
        generated_eval_case=setup["generated_eval_case"],
        generated_eval_admission_record=setup["admission_record"],
        candidate_record=setup["candidate_record"],
        promotion_request_record=None,
        promotion_decision_record=setup["decision"],
        required_eval_registry=setup["required_eval_registry"],
    )
    assert output["generated_eval_promotion_result_record"]["promoted"] is False
    assert "missing_promotion_request_record" in output["generated_eval_promotion_result_record"]["blocked_reasons"]


def test_promotion_without_decision_artifact_blocks() -> None:
    setup = _promotion_setup()
    output = execute_generated_eval_promotion_gate(
        generated_eval_case=setup["generated_eval_case"],
        generated_eval_admission_record=setup["admission_record"],
        candidate_record=setup["candidate_record"],
        promotion_request_record=setup["request"],
        promotion_decision_record=None,
        required_eval_registry=setup["required_eval_registry"],
    )
    assert output["generated_eval_promotion_result_record"]["promoted"] is False
    assert "missing_promotion_decision_record" in output["generated_eval_promotion_result_record"]["blocked_reasons"]


def test_promotion_with_rejected_decision_blocks() -> None:
    setup = _promotion_setup()
    rejected_decision = build_generated_eval_promotion_decision_record(
        setup["request"],
        decision="rejected",
        decided_by="runtime-governance-reviewer",
        rationale="Insufficient governance confidence.",
    )
    output = execute_generated_eval_promotion_gate(
        generated_eval_case=setup["generated_eval_case"],
        generated_eval_admission_record=setup["admission_record"],
        candidate_record=setup["candidate_record"],
        promotion_request_record=setup["request"],
        promotion_decision_record=rejected_decision,
        required_eval_registry=setup["required_eval_registry"],
    )
    assert output["generated_eval_promotion_result_record"]["promoted"] is False
    assert "promotion_decision_not_approved" in output["generated_eval_promotion_result_record"]["blocked_reasons"]


def test_promotion_approved_but_replay_validation_fails_blocks() -> None:
    setup = _promotion_setup()
    setup["generated_eval_case"]["expected_reason_code"] = "mismatched_reason"
    output = execute_generated_eval_promotion_gate(
        generated_eval_case=setup["generated_eval_case"],
        generated_eval_admission_record=setup["admission_record"],
        candidate_record=setup["candidate_record"],
        promotion_request_record=setup["request"],
        promotion_decision_record=setup["decision"],
        required_eval_registry=setup["required_eval_registry"],
    )
    result = output["generated_eval_promotion_result_record"]
    assert result["promoted"] is False
    assert result["replay_validation_passed"] is False
    assert "replay_validation_failed" in result["blocked_reasons"]


def test_promotion_with_all_requirements_succeeds() -> None:
    setup = _promotion_setup()
    output = execute_generated_eval_promotion_gate(
        generated_eval_case=setup["generated_eval_case"],
        generated_eval_admission_record=setup["admission_record"],
        candidate_record=setup["candidate_record"],
        promotion_request_record=setup["request"],
        promotion_decision_record=setup["decision"],
        required_eval_registry=setup["required_eval_registry"],
    )
    result = output["generated_eval_promotion_result_record"]
    assert result["promoted"] is True
    assert result["blocked_reasons"] == []


def test_promotion_result_blocked_reasons_are_deterministic() -> None:
    setup = _promotion_setup(occurrence_count=1)
    first = execute_generated_eval_promotion_gate(
        generated_eval_case=setup["generated_eval_case"],
        generated_eval_admission_record=None,
        candidate_record=setup["candidate_record"],
        promotion_request_record=None,
        promotion_decision_record=None,
        required_eval_registry=setup["required_eval_registry"],
        occurrence_threshold=2,
    )
    second = execute_generated_eval_promotion_gate(
        generated_eval_case=setup["generated_eval_case"],
        generated_eval_admission_record=None,
        candidate_record=setup["candidate_record"],
        promotion_request_record=None,
        promotion_decision_record=None,
        required_eval_registry=setup["required_eval_registry"],
        occurrence_threshold=2,
    )
    assert first["generated_eval_promotion_result_record"]["blocked_reasons"] == second["generated_eval_promotion_result_record"][
        "blocked_reasons"
    ]


def test_controlled_update_path_records_required_eval_target() -> None:
    setup = _promotion_setup()
    output = execute_generated_eval_promotion_gate(
        generated_eval_case=setup["generated_eval_case"],
        generated_eval_admission_record=setup["admission_record"],
        candidate_record=setup["candidate_record"],
        promotion_request_record=setup["request"],
        promotion_decision_record=setup["decision"],
        required_eval_registry=setup["required_eval_registry"],
    )
    assert (
        output["generated_eval_promotion_result_record"]["required_eval_target"]
        == "required_eval_registry.mappings[artifact_family=generated_eval_case].required_evals"
    )


def test_rollback_record_can_be_created_for_promoted_eval() -> None:
    setup = _promotion_setup()
    promotion_output = execute_generated_eval_promotion_gate(
        generated_eval_case=setup["generated_eval_case"],
        generated_eval_admission_record=setup["admission_record"],
        candidate_record=setup["candidate_record"],
        promotion_request_record=setup["request"],
        promotion_decision_record=setup["decision"],
        required_eval_registry=setup["required_eval_registry"],
    )
    rollback_record = build_generated_eval_promotion_rollback_record(
        generated_eval_artifact_id=setup["generated_eval_case"]["artifact_id"],
        promotion_result_record=promotion_output["generated_eval_promotion_result_record"],
        rollback_reason="manual_governance_reversal",
    )
    assert rollback_record["rolled_back"] is True
    assert rollback_record["generated_eval_artifact_id"] == setup["generated_eval_case"]["artifact_id"]


def test_rollback_path_is_deterministic() -> None:
    setup = _promotion_setup()
    promotion_output = execute_generated_eval_promotion_gate(
        generated_eval_case=setup["generated_eval_case"],
        generated_eval_admission_record=setup["admission_record"],
        candidate_record=setup["candidate_record"],
        promotion_request_record=setup["request"],
        promotion_decision_record=setup["decision"],
        required_eval_registry=setup["required_eval_registry"],
    )
    first = execute_generated_eval_promotion_rollback(
        generated_eval_artifact_id=setup["generated_eval_case"]["artifact_id"],
        promotion_result_record=promotion_output["generated_eval_promotion_result_record"],
        rollback_reason="manual_governance_reversal",
        required_eval_registry=promotion_output["required_eval_registry"],
    )
    second = execute_generated_eval_promotion_rollback(
        generated_eval_artifact_id=setup["generated_eval_case"]["artifact_id"],
        promotion_result_record=promotion_output["generated_eval_promotion_result_record"],
        rollback_reason="manual_governance_reversal",
        required_eval_registry=promotion_output["required_eval_registry"],
    )
    assert first["generated_eval_promotion_rollback_record"]["artifact_id"] == second["generated_eval_promotion_rollback_record"][
        "artifact_id"
    ]


def test_end_to_end_generated_eval_promotion_and_rollback_flow() -> None:
    failure = _fixtures()["missing_required_eval_failure"]
    generated = generate_and_admit_failure_eval(failure)
    generated_repeat = generate_and_admit_failure_eval(failure)
    candidate_record = build_generated_eval_candidate_records([generated, generated_repeat])[0]
    request = build_generated_eval_promotion_request_record(
        generated["generated_eval_case"],
        candidate_record,
        request_origin="candidate_assessment",
        justification="Recurring admitted candidate.",
    )
    decision = build_generated_eval_promotion_decision_record(
        request,
        decision="approved",
        decided_by="runtime-governance-reviewer",
        rationale="Promotion review complete.",
    )
    promoted = execute_generated_eval_promotion_gate(
        generated_eval_case=generated["generated_eval_case"],
        generated_eval_admission_record=generated["generated_eval_admission_record"],
        candidate_record=candidate_record,
        promotion_request_record=request,
        promotion_decision_record=decision,
        required_eval_registry=load_required_eval_registry(),
    )
    rollback = execute_generated_eval_promotion_rollback(
        generated_eval_artifact_id=generated["generated_eval_case"]["artifact_id"],
        promotion_result_record=promoted["generated_eval_promotion_result_record"],
        rollback_reason="manual_governance_reversal",
        required_eval_registry=promoted["required_eval_registry"],
    )
    assert promoted["generated_eval_promotion_result_record"]["promoted"] is True
    assert rollback["generated_eval_promotion_rollback_record"]["rolled_back"] is True
