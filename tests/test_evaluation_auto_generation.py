from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402

from spectrum_systems.contracts import load_schema  # noqa: E402
from spectrum_systems.modules.runtime.evaluation_auto_generation import (  # noqa: E402
    _FAILURE_CLASS_PREVENTION_MAP,
    EvalCaseGenerationError,
    build_failure_pattern_record,
    build_failure_learning_bundle,
    enforce_failure_pattern_eval_gate,
    generate_eval_case_from_failure_pattern,
    generate_failure_derived_eval_cases_from_review_signal,
    generate_failure_eval_case,
    normalize_failure_pattern,
    map_failure_class_to_prevention_rule,
    register_failure_eval_case,
    build_review_eval_generation_report,
)


def _execution_result() -> dict:
    return {
        "execution_status": "blocked",
        "continuation_allowed": False,
        "publication_blocked": True,
        "decision_blocked": True,
        "execution_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "human_review_required": True,
        "escalation_triggered": True,
    }


def _validate_failure_eval_case(artifact: dict) -> None:
    schema = load_schema("failure_eval_case")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(artifact)


def test_generated_failure_eval_case_is_schema_valid() -> None:
    artifact = generate_failure_eval_case(
        source_artifact={
            "artifact_type": "agent_failure_record",
            "id": "afr-001",
            "trace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        },
        source_run_id="agrun-001",
        stage="eval",
        runtime_environment="agent_golden_path",
        execution_result=_execution_result(),
    )
    assert artifact["artifact_type"] == "failure_eval_case"
    _validate_failure_eval_case(artifact)


def test_generation_is_deterministic_for_identical_inputs() -> None:
    kwargs = dict(
        source_artifact={
            "artifact_type": "agent_failure_record",
            "id": "afr-001",
            "trace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        },
        source_run_id="agrun-001",
        stage="eval",
        runtime_environment="agent_golden_path",
        execution_result=_execution_result(),
    )
    first = generate_failure_eval_case(**kwargs)
    second = generate_failure_eval_case(**kwargs)
    assert first == second


def test_generation_from_review_required_indeterminate_source() -> None:
    artifact = generate_failure_eval_case(
        source_artifact={
            "artifact_type": "hitl_review_request",
            "id": "hrr-001",
            "trace_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            "trigger_reason": "indeterminate_outcome_routed_to_human",
        },
        source_run_id="agrun-002",
        stage="control",
        runtime_environment="agent_golden_path",
        execution_result=_execution_result(),
    )
    assert artifact["failure_class"] == "review_boundary_halt"
    assert artifact["failure_stage"] == "review_boundary"


def test_generation_from_control_indeterminate_source() -> None:
    artifact = generate_failure_eval_case(
        source_artifact={
            "artifact_type": "evaluation_control_decision",
            "decision_id": "ECD-001",
            "trace_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
            "decision": "require_review",
            "rationale_code": "require_review_indeterminate_failure",
        },
        source_run_id="eval-run-003",
        stage="synthesis",
        runtime_environment="cli",
        execution_result=_execution_result(),
    )
    assert artifact["failure_class"] == "control_indeterminate"
    assert artifact["source_artifact_id"] == "ECD-001"


def test_unsupported_source_artifact_type_is_rejected() -> None:
    with pytest.raises(EvalCaseGenerationError, match="unsupported source artifact_type"):
        generate_failure_eval_case(
            source_artifact={
                "artifact_type": "eval_summary",
                "eval_run_id": "eval-run-001",
                "trace_id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
            },
            source_run_id="eval-run-001",
            stage="synthesis",
            runtime_environment="cli",
            execution_result=_execution_result(),
        )


def test_replay_linkage_fields_are_present() -> None:
    artifact = generate_failure_eval_case(
        source_artifact={
            "artifact_type": "agent_failure_record",
            "id": "afr-009",
            "trace_id": "ffffffff-ffff-4fff-8fff-ffffffffffff",
        },
        source_run_id="agrun-009",
        stage="eval",
        runtime_environment="agent_golden_path",
        execution_result=_execution_result(),
    )

    assert artifact["source_run_id"] == "agrun-009"
    assert artifact["source_artifact_id"] == "afr-009"
    assert artifact["provenance"]["source_artifact_ref"] == "agent_failure_record:afr-009"


def test_failure_class_maps_to_prevention_rule() -> None:
    mapping = map_failure_class_to_prevention_rule("runtime_failure")
    assert mapping["failure_class_id"] == "runtime_failure"
    assert mapping["prevention_action"] == "block_repeat_execution"
    assert mapping["control_decision_surface"] == "evaluation_control_decision"


def test_prevention_artifact_emitted() -> None:
    artifact = generate_failure_eval_case(
        source_artifact={
            "artifact_type": "agent_failure_record",
            "id": "afr-map-001",
            "trace_id": "99999999-9999-4999-8999-999999999999",
        },
        source_run_id="agrun-map-001",
        stage="eval",
        runtime_environment="agent_golden_path",
        execution_result=_execution_result(),
    )
    registry: dict[str, dict] = {}
    binding = register_failure_eval_case(
        failure_eval_case=artifact,
        eval_registry=registry,
        policy_id="failure-binding-policy-v1",
        trigger_condition="on_agent_failure_record",
    )
    prevention_artifact = binding["recurrence_prevention_artifact"]
    assert prevention_artifact["artifact_type"] == "recurrence_prevention_authority"
    assert prevention_artifact["source_failure_class_id"] == artifact["failure_class"]
    assert prevention_artifact["linked_eval_case_ids"] == [artifact["eval_case_id"]]
    assert prevention_artifact["prevention_rule_id"] == binding["prevention_rule_id"]


def test_missing_prevention_mapping_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(_FAILURE_CLASS_PREVENTION_MAP, "runtime_failure", raising=False)
    artifact = generate_failure_eval_case(
        source_artifact={
            "artifact_type": "agent_failure_record",
            "id": "afr-map-002",
            "trace_id": "12121212-1212-4121-8121-121212121212",
        },
        source_run_id="agrun-map-002",
        stage="eval",
        runtime_environment="agent_golden_path",
        execution_result=_execution_result(),
    )
    with pytest.raises(EvalCaseGenerationError, match="missing recurrence prevention mapping"):
        register_failure_eval_case(
            failure_eval_case=artifact,
            eval_registry={},
            policy_id="failure-binding-policy-v1",
            trigger_condition="on_agent_failure_record",
        )


def test_critical_review_findings_generate_failure_derived_eval_cases() -> None:
    review_signal = {
        "artifact_type": "review_control_signal",
        "schema_version": "1.1.0",
        "signal_id": "rcs-1111111111111111",
        "review_id": "REV-TEST-001",
        "review_type": "failure",
        "gate_assessment": "FAIL",
        "scale_recommendation": "NO",
        "critical_findings": [
            "Missing fail-closed mapping [eval_family:review_gate_alignment]",
            "Replay linkage weak [eval_family:review_signal_validity]",
            "Missing  fail-closed mapping [eval_family:review_gate_alignment]",
        ],
        "confidence": 0.3,
        "trace_linkage": {
            "review_markdown_path": "docs/reviews/example.md",
            "source_digest_sha256": "a" * 64,
            "review_artifact_path": "artifacts/reviews/example.json",
        },
    }

    cases = generate_failure_derived_eval_cases_from_review_signal(review_signal)
    assert len(cases) == 2
    assert all(case["artifact_type"] == "eval_case" for case in cases)
    assert all(case["created_from"] == "failure_trace" for case in cases)
    assert all(case["provenance"]["review_id"] == "REV-TEST-001" for case in cases)
    assert all(case["provenance"]["review_control_signal_id"] == "rcs-1111111111111111" for case in cases)
    assert cases[0]["expected_output_spec"]["reason_code"] == "review_failure_derived::review_gate_alignment"
    assert cases[1]["expected_output_spec"]["reason_code"] == "review_failure_derived::review_signal_validity"


def test_ambiguous_review_finding_mapping_fails_closed() -> None:
    review_signal = {
        "artifact_type": "review_control_signal",
        "schema_version": "1.1.0",
        "signal_id": "rcs-2222222222222222",
        "review_id": "REV-TEST-002",
        "review_type": "failure",
        "gate_assessment": "FAIL",
        "scale_recommendation": "NO",
        "critical_findings": ["No explicit mapping family"],
        "confidence": 0.2,
        "trace_linkage": {
            "review_markdown_path": "docs/reviews/example-2.md",
            "source_digest_sha256": "b" * 64,
            "review_artifact_path": "artifacts/reviews/example-2.json",
        },
    }
    with pytest.raises(EvalCaseGenerationError, match="missing explicit \\[eval_family"):
        generate_failure_derived_eval_cases_from_review_signal(review_signal)


def test_repeated_review_failures_mark_high_priority_deterministically() -> None:
    review_signal = {
        "artifact_type": "review_control_signal",
        "schema_version": "1.1.0",
        "signal_id": "rcs-3333333333333333",
        "review_id": "REV-TEST-003",
        "review_type": "failure",
        "gate_assessment": "FAIL",
        "scale_recommendation": "NO",
        "critical_findings": [
            "Missing fail-closed mapping [eval_family:review_gate_alignment]",
        ],
        "confidence": 0.2,
        "trace_linkage": {
            "review_markdown_path": "docs/reviews/example-3.md",
            "source_digest_sha256": "c" * 64,
            "review_artifact_path": "artifacts/reviews/review-artifact-3.json",
        },
    }
    baseline = generate_failure_derived_eval_cases_from_review_signal(review_signal)
    dedupe_key = baseline[0]["provenance"]["dedupe_key"]
    cases = generate_failure_derived_eval_cases_from_review_signal(
        review_signal,
        prior_recurrence_counts={dedupe_key: 2},
    )
    assert cases
    assert cases[0]["provenance"]["high_priority"] is True


def test_review_eval_generation_report_deterministic() -> None:
    report = build_review_eval_generation_report(
        generated_eval_cases=[{"eval_case_id": "ec-1"}, {"eval_case_id": "ec-2"}],
        recurrence_counts={"rfd-a": 1, "rfd-b": 3},
        trace_id="trace-review",
    )
    second = build_review_eval_generation_report(
        generated_eval_cases=[{"eval_case_id": "ec-1"}, {"eval_case_id": "ec-2"}],
        recurrence_counts={"rfd-a": 1, "rfd-b": 3},
        trace_id="trace-review",
    )
    assert report == second
    assert report["high_priority_eval_count"] == 1


def test_failure_pattern_normalization_is_deterministic() -> None:
    kwargs = {
        "stop_reason": "missing_required_signal",
        "root_cause_chain": [
            {"step": "review_or_input_condition", "reason": "PROP_REVIEW_EVAL_NOT_INGESTED"},
            {"step": "control_gate", "reason": "control_block"},
        ],
        "blocking_conditions": ["PROP_REVIEW_EVAL_NOT_INGESTED", "AUTH_REVIEW_REQUIRED"],
    }
    first = normalize_failure_pattern(**kwargs)
    second = normalize_failure_pattern(**kwargs)
    assert first == second


def test_failure_pattern_record_reuses_prior_record_and_increments_count() -> None:
    seed = build_failure_pattern_record(
        stop_reason="missing_required_signal",
        root_cause_chain=[{"step": "review_or_input_condition", "reason": "PROP_REVIEW_EVAL_NOT_INGESTED"}],
        blocking_conditions=["PROP_REVIEW_EVAL_NOT_INGESTED"],
        trace_id="trace-1",
        related_artifacts=["core_system_integration_validation:CSI-001"],
        observed_at="2026-04-01T00:00:00Z",
    )
    second = build_failure_pattern_record(
        stop_reason="missing_required_signal",
        root_cause_chain=[{"step": "review_or_input_condition", "reason": "PROP_REVIEW_EVAL_NOT_INGESTED"}],
        blocking_conditions=["PROP_REVIEW_EVAL_NOT_INGESTED"],
        trace_id="trace-2",
        related_artifacts=["remediation_plan:RMP-001"],
        prior_record=seed,
        observed_at="2026-04-02T00:00:00Z",
    )
    assert second["pattern_id"] == seed["pattern_id"]
    assert second["occurrence_count"] == 2
    assert second["first_seen"] == "2026-04-01T00:00:00Z"
    assert second["last_seen"] == "2026-04-02T00:00:00Z"
    assert second["trace_ids"] == ["trace-1", "trace-2"]


def test_failure_pattern_eval_generation_honors_threshold_and_dedupes() -> None:
    pattern = build_failure_pattern_record(
        stop_reason="missing_required_signal",
        root_cause_chain=[{"step": "review_or_input_condition", "reason": "PROP_REVIEW_EVAL_NOT_INGESTED"}],
        blocking_conditions=["PROP_REVIEW_EVAL_NOT_INGESTED"],
        trace_id="trace-1",
        observed_at="2026-04-01T00:00:00Z",
    )
    assert generate_eval_case_from_failure_pattern(failure_pattern_record=pattern, threshold=2) is None

    pattern = build_failure_pattern_record(
        stop_reason="missing_required_signal",
        root_cause_chain=[{"step": "review_or_input_condition", "reason": "PROP_REVIEW_EVAL_NOT_INGESTED"}],
        blocking_conditions=["PROP_REVIEW_EVAL_NOT_INGESTED"],
        trace_id="trace-2",
        prior_record=pattern,
        observed_at="2026-04-02T00:00:00Z",
    )
    generated = generate_eval_case_from_failure_pattern(failure_pattern_record=pattern, threshold=2)
    assert generated is not None
    assert generated["created_from"] == "failure_trace"

    duplicate = generate_eval_case_from_failure_pattern(
        failure_pattern_record=pattern,
        threshold=2,
        existing_eval_case_ids=[generated["eval_case_id"]],
    )
    assert duplicate is None


def test_failure_learning_bundle_links_remediation_and_required_eval_set() -> None:
    pattern = build_failure_pattern_record(
        stop_reason="missing_required_signal",
        root_cause_chain=[{"step": "review_or_input_condition", "reason": "PROP_REVIEW_EVAL_NOT_INGESTED"}],
        blocking_conditions=["PROP_REVIEW_EVAL_NOT_INGESTED"],
        trace_id="trace-1",
        observed_at="2026-04-01T00:00:00Z",
    )
    pattern = build_failure_pattern_record(
        stop_reason="missing_required_signal",
        root_cause_chain=[{"step": "review_or_input_condition", "reason": "PROP_REVIEW_EVAL_NOT_INGESTED"}],
        blocking_conditions=["PROP_REVIEW_EVAL_NOT_INGESTED"],
        trace_id="trace-2",
        prior_record=pattern,
        observed_at="2026-04-02T00:00:00Z",
    )
    bundle = build_failure_learning_bundle(
        failure_pattern_record=pattern,
        remediation_plan={"plan_id": "RMP-LEARN-001"},
        threshold=2,
    )
    assert bundle["failure_pattern_record_ref"].startswith("failure_pattern_record:")
    assert bundle["remediation_plan_ref"] == "remediation_plan:RMP-LEARN-001"
    assert len(bundle["required_eval_case_ids"]) == 1


def test_failure_pattern_eval_gate_freezes_when_threshold_violated() -> None:
    pattern = build_failure_pattern_record(
        stop_reason="missing_required_signal",
        root_cause_chain=[{"step": "review_or_input_condition", "reason": "PROP_REVIEW_EVAL_NOT_INGESTED"}],
        blocking_conditions=["PROP_REVIEW_EVAL_NOT_INGESTED"],
        trace_id="trace-1",
        observed_at="2026-04-01T00:00:00Z",
    )
    pattern = build_failure_pattern_record(
        stop_reason="missing_required_signal",
        root_cause_chain=[{"step": "review_or_input_condition", "reason": "PROP_REVIEW_EVAL_NOT_INGESTED"}],
        blocking_conditions=["PROP_REVIEW_EVAL_NOT_INGESTED"],
        trace_id="trace-2",
        prior_record=pattern,
        observed_at="2026-04-02T00:00:00Z",
    )
    decision = enforce_failure_pattern_eval_gate(failure_pattern_record=pattern, threshold=2)
    assert decision["decision"] == "deny"
    assert decision["system_response"] == "freeze"
