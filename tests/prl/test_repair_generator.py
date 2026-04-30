"""Tests for PRL-02 repair_generator: bounded, never-auto-applied repair candidates."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.prl.artifact_builder import (
    build_capture_record,
    build_failure_packet,
)
from spectrum_systems.modules.prl.failure_classifier import classify
from spectrum_systems.modules.prl.failure_parser import ParsedFailure
from spectrum_systems.modules.prl.repair_generator import generate_repair_candidate

RUN_ID = "run-repair-test-001"
TRACE_ID = "trace-repair-test-abc"


def _make_packet(failure_class: str) -> dict:
    parsed = ParsedFailure(
        failure_class=failure_class,
        raw_excerpt="test excerpt",
        normalized_message="Test normalized message",
        file_refs=("foo.py", "bar.py"),
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


class TestGenerateRepairCandidate:
    def test_produces_required_fields(self):
        packet = _make_packet("authority_shape_violation")
        classification = classify(ParsedFailure(
            failure_class="authority_shape_violation",
            raw_excerpt="x",
            normalized_message="x",
            file_refs=(),
            line_number=None,
            exit_code=None,
        ))
        repair = generate_repair_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert repair["artifact_type"] == "prl_repair_candidate"
        assert repair["schema_version"] == "1.0.0"
        assert repair["id"].startswith("prl-rep-")
        assert repair["run_id"] == RUN_ID
        assert repair["trace_id"] == TRACE_ID
        assert isinstance(repair["repair_prompt"], str)
        assert isinstance(repair["minimal_fix_scope"], str)
        assert isinstance(repair["target_files"], list)

    def test_auto_apply_is_always_false(self):
        """INVARIANT: auto_apply must NEVER be True."""
        for fc in [
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
            "unknown_failure",
        ]:
            packet = _make_packet(fc)
            parsed = ParsedFailure(
                failure_class=fc,
                raw_excerpt="x",
                normalized_message="x",
                file_refs=(),
                line_number=None,
                exit_code=None,
            )
            classification = classify(parsed)
            repair = generate_repair_candidate(
                failure_packet=packet,
                classification=classification,
                run_id=RUN_ID,
                trace_id=TRACE_ID,
            )
            assert repair["auto_apply"] is False, f"auto_apply must be False for {fc}"

    def test_failure_packet_ref_format(self):
        packet = _make_packet("trace_missing")
        parsed = ParsedFailure(
            failure_class="trace_missing",
            raw_excerpt="x",
            normalized_message="x",
            file_refs=(),
            line_number=None,
            exit_code=None,
        )
        classification = classify(parsed)
        repair = generate_repair_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert repair["failure_packet_ref"].startswith("pre_pr_failure_packet:")

    def test_safety_classification_is_valid_enum(self):
        valid = {"safe", "requires_review", "unsafe"}
        for fc in ["contract_schema_violation", "authority_shape_violation", "trace_missing"]:
            packet = _make_packet(fc)
            parsed = ParsedFailure(
                failure_class=fc,
                raw_excerpt="x",
                normalized_message="x",
                file_refs=(),
                line_number=None,
                exit_code=None,
            )
            classification = classify(parsed)
            repair = generate_repair_candidate(
                failure_packet=packet,
                classification=classification,
                run_id=RUN_ID,
                trace_id=TRACE_ID,
            )
            assert repair["safety_classification"] in valid

    def test_requires_human_review_matches_safety_classification(self):
        for fc in ["authority_shape_violation", "trace_missing", "pytest_selection_missing"]:
            packet = _make_packet(fc)
            parsed = ParsedFailure(
                failure_class=fc,
                raw_excerpt="x",
                normalized_message="x",
                file_refs=(),
                line_number=None,
                exit_code=None,
            )
            classification = classify(parsed)
            repair = generate_repair_candidate(
                failure_packet=packet,
                classification=classification,
                run_id=RUN_ID,
                trace_id=TRACE_ID,
            )
            expected = repair["safety_classification"] == "requires_review"
            assert repair["requires_human_review"] == expected

    def test_deterministic_id(self):
        packet = _make_packet("policy_mismatch")
        parsed = ParsedFailure(
            failure_class="policy_mismatch",
            raw_excerpt="x",
            normalized_message="x",
            file_refs=(),
            line_number=None,
            exit_code=None,
        )
        classification = classify(parsed)
        r1 = generate_repair_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        r2 = generate_repair_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert r1["id"] == r2["id"]

    def test_target_files_from_packet(self):
        packet = _make_packet("contract_schema_violation")
        parsed = ParsedFailure(
            failure_class="contract_schema_violation",
            raw_excerpt="x",
            normalized_message="x",
            file_refs=(),
            line_number=None,
            exit_code=None,
        )
        classification = classify(parsed)
        repair = generate_repair_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        # target_files comes from packet["file_refs"]
        assert repair["target_files"] == packet["file_refs"]

    def test_repair_prompt_non_empty_for_all_classes(self):
        for fc in [
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
            "unknown_failure",
        ]:
            packet = _make_packet(fc)
            parsed = ParsedFailure(
                failure_class=fc,
                raw_excerpt="x",
                normalized_message="x",
                file_refs=(),
                line_number=None,
                exit_code=None,
            )
            classification = classify(parsed)
            repair = generate_repair_candidate(
                failure_packet=packet,
                classification=classification,
                run_id=RUN_ID,
                trace_id=TRACE_ID,
            )
            assert repair["repair_prompt"], f"Empty repair_prompt for {fc}"
            assert repair["minimal_fix_scope"], f"Empty minimal_fix_scope for {fc}"
