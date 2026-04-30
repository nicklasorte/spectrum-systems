"""Tests for PRL-03 eval_generator: failure → eval case generation and gating."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.prl.artifact_builder import (
    build_capture_record,
    build_failure_packet,
)
from spectrum_systems.modules.prl.eval_generator import (
    build_generation_record,
    generate_eval_case_candidate,
    advance_to_eval_case,
)
from spectrum_systems.modules.prl.failure_classifier import classify
from spectrum_systems.modules.prl.failure_parser import ParsedFailure

RUN_ID = "run-eval-test-001"
TRACE_ID = "trace-eval-test-abc"

_GATE_ELIGIBLE_CLASSES = [
    "pytest_selection_missing",
    "authority_shape_violation",
    "system_registry_mismatch",
    "contract_schema_violation",
    "missing_required_artifact",
    "trace_missing",
    "replay_mismatch",
    "policy_mismatch",
    "timeout",
    "rate_limited",
]

_NON_ELIGIBLE_CLASSES = [
    "unknown_failure",
]


def _make_packet(failure_class: str) -> dict:
    parsed = ParsedFailure(
        failure_class=failure_class,
        raw_excerpt="test excerpt",
        normalized_message="Test normalized message",
        file_refs=("foo.py",),
        line_number=None,
        exit_code=None,
    )
    classification = classify(parsed)
    capture = build_capture_record(
        parsed=parsed,
        classification=classification,
        source="pre_pr_gate",
        run_id=RUN_ID,
        trace_id=TRACE_ID,
    )
    return build_failure_packet(
        capture_record=capture,
        classification=classification,
        run_id=RUN_ID,
        trace_id=TRACE_ID,
    )


def _parsed(fc: str) -> ParsedFailure:
    return ParsedFailure(
        failure_class=fc,
        raw_excerpt="x",
        normalized_message="x",
        file_refs=(),
        line_number=None,
        exit_code=None,
    )


class TestGenerateEvalCaseCandidate:
    def test_produces_required_fields(self):
        packet = _make_packet("authority_shape_violation")
        classification = classify(_parsed("authority_shape_violation"))
        candidate = generate_eval_case_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert candidate["artifact_type"] == "eval_case_candidate"
        assert candidate["schema_version"] == "1.0.0"
        assert candidate["id"].startswith("prl-cnd-")
        assert candidate["run_id"] == RUN_ID
        assert candidate["trace_id"] == TRACE_ID
        assert candidate["required"] is True
        assert isinstance(candidate["gate_eligible"], bool)

    def test_eval_type_is_valid_enum(self):
        valid_types = {
            "schema_conformance",
            "policy_alignment",
            "replay_consistency",
            "failure_regression_check",
        }
        for fc in _GATE_ELIGIBLE_CLASSES + _NON_ELIGIBLE_CLASSES:
            packet = _make_packet(fc)
            classification = classify(_parsed(fc))
            candidate = generate_eval_case_candidate(
                failure_packet=packet,
                classification=classification,
                run_id=RUN_ID,
                trace_id=TRACE_ID,
            )
            assert candidate["eval_type"] in valid_types, f"Invalid eval_type for {fc}"

    def test_pass_condition_non_empty(self):
        for fc in _GATE_ELIGIBLE_CLASSES:
            packet = _make_packet(fc)
            classification = classify(_parsed(fc))
            candidate = generate_eval_case_candidate(
                failure_packet=packet,
                classification=classification,
                run_id=RUN_ID,
                trace_id=TRACE_ID,
            )
            assert candidate["pass_condition"], f"Empty pass_condition for {fc}"

    def test_eligible_classes_are_gate_eligible(self):
        for fc in _GATE_ELIGIBLE_CLASSES:
            packet = _make_packet(fc)
            classification = classify(_parsed(fc))
            candidate = generate_eval_case_candidate(
                failure_packet=packet,
                classification=classification,
                run_id=RUN_ID,
                trace_id=TRACE_ID,
            )
            assert candidate["gate_eligible"] is True, f"{fc} should be gate_eligible"

    def test_unknown_failure_not_eligible(self):
        packet = _make_packet("unknown_failure")
        classification = classify(_parsed("unknown_failure"))
        candidate = generate_eval_case_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert candidate["gate_eligible"] is False
        assert candidate["gate_block_reason"]

    def test_failure_packet_ref_format(self):
        packet = _make_packet("trace_missing")
        classification = classify(_parsed("trace_missing"))
        candidate = generate_eval_case_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert candidate["failure_packet_ref"].startswith("pre_pr_failure_packet:")

    def test_deterministic_id(self):
        packet = _make_packet("policy_mismatch")
        classification = classify(_parsed("policy_mismatch"))
        c1 = generate_eval_case_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        c2 = generate_eval_case_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert c1["id"] == c2["id"]


class TestAdvanceToEvalCase:
    def test_eligible_candidate_advances(self):
        packet = _make_packet("authority_shape_violation")
        classification = classify(_parsed("authority_shape_violation"))
        candidate = generate_eval_case_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        gated = advance_to_eval_case(
            candidate=candidate,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert gated is not None
        assert gated["artifact_type"] == "prl_eval_case"
        assert gated["id"].startswith("prl-evl-")
        assert gated["required"] is True
        assert 0.0 <= gated["threshold"] <= 1.0
        assert gated["gated_at"]

    def test_non_eligible_returns_none(self):
        packet = _make_packet("unknown_failure")
        classification = classify(_parsed("unknown_failure"))
        candidate = generate_eval_case_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        result = advance_to_eval_case(
            candidate=candidate,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert result is None

    def test_candidate_ref_format_in_gated(self):
        packet = _make_packet("replay_mismatch")
        classification = classify(_parsed("replay_mismatch"))
        candidate = generate_eval_case_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        gated = advance_to_eval_case(
            candidate=candidate,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert gated is not None
        assert gated["candidate_ref"].startswith("eval_case_candidate:")

    def test_replay_mismatch_threshold_is_0_95(self):
        packet = _make_packet("replay_mismatch")
        classification = classify(_parsed("replay_mismatch"))
        candidate = generate_eval_case_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        gated = advance_to_eval_case(
            candidate=candidate,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert gated is not None
        assert gated["threshold"] == 0.95

    def test_all_eligible_classes_produce_prl_eval_case(self):
        for fc in _GATE_ELIGIBLE_CLASSES:
            packet = _make_packet(fc)
            classification = classify(_parsed(fc))
            candidate = generate_eval_case_candidate(
                failure_packet=packet,
                classification=classification,
                run_id=RUN_ID,
                trace_id=TRACE_ID,
            )
            gated = advance_to_eval_case(
                candidate=candidate,
                classification=classification,
                run_id=RUN_ID,
                trace_id=TRACE_ID,
            )
            assert gated is not None, f"{fc} should advance"
            assert gated["artifact_type"] == "prl_eval_case"


class TestBuildGenerationRecord:
    def test_advanced_status(self):
        packet = _make_packet("contract_schema_violation")
        classification = classify(_parsed("contract_schema_violation"))
        candidate = generate_eval_case_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        gated = advance_to_eval_case(
            candidate=candidate,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        record = build_generation_record(
            failure_packet=packet,
            candidate=candidate,
            gated_eval=gated,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert record["artifact_type"] == "prl_eval_generation_record"
        assert record["gate_status"] == "advanced"
        assert record["gated_eval_id"] == gated["id"]

    def test_requires_human_review_status(self):
        packet = _make_packet("unknown_failure")
        classification = classify(_parsed("unknown_failure"))
        candidate = generate_eval_case_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        record = build_generation_record(
            failure_packet=packet,
            candidate=candidate,
            gated_eval=None,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert record["gate_status"] == "requires_human_review"
        assert "gated_eval_id" not in record
        assert record["gate_block_reason"]

    def test_record_has_trace_refs(self):
        packet = _make_packet("trace_missing")
        classification = classify(_parsed("trace_missing"))
        candidate = generate_eval_case_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        gated = advance_to_eval_case(
            candidate=candidate,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        record = build_generation_record(
            failure_packet=packet,
            candidate=candidate,
            gated_eval=gated,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert "trace_refs" in record
        assert record["trace_refs"]["primary"] == TRACE_ID

    def test_deterministic_id(self):
        packet = _make_packet("timeout")
        classification = classify(_parsed("timeout"))
        candidate = generate_eval_case_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        r1 = build_generation_record(
            failure_packet=packet,
            candidate=candidate,
            gated_eval=None,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        r2 = build_generation_record(
            failure_packet=packet,
            candidate=candidate,
            gated_eval=None,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert r1["id"] == r2["id"]
