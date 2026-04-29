"""Tests for PRL-01 artifact_builder: schema-validated artifact construction."""

from __future__ import annotations

import jsonschema
import pytest

from spectrum_systems.modules.prl.artifact_builder import (
    build_capture_record,
    build_failure_packet,
)
from spectrum_systems.modules.prl.failure_classifier import Classification, classify
from spectrum_systems.modules.prl.failure_parser import ParsedFailure


def _make_parsed(
    failure_class: str = "authority_shape_violation",
    file_refs: tuple[str, ...] = ("foo.py",),
    line_number: int | None = None,
    exit_code: int | None = None,
) -> ParsedFailure:
    return ParsedFailure(
        failure_class=failure_class,
        raw_excerpt="test excerpt",
        normalized_message="Test normalized message",
        file_refs=file_refs,
        line_number=line_number,
        exit_code=exit_code,
    )


def _make_classification(failure_class: str = "authority_shape_violation") -> Classification:
    return classify(_make_parsed(failure_class))


RUN_ID = "run-test-001"
TRACE_ID = "trace-test-abc123"


class TestBuildCaptureRecord:
    def test_produces_required_fields(self):
        parsed = _make_parsed()
        classification = _make_classification()
        record = build_capture_record(
            parsed=parsed,
            classification=classification,
            source="pre_pr_gate",
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert record["artifact_type"] == "pr_failure_capture_record"
        assert record["schema_version"] == "1.0.0"
        assert record["id"].startswith("prl-cap-")
        assert record["run_id"] == RUN_ID
        assert record["trace_id"] == TRACE_ID
        assert record["failure_class"] == "authority_shape_violation"
        assert record["owning_system"] == "AEX"
        assert record["source"] == "pre_pr_gate"
        assert isinstance(record["file_refs"], list)

    def test_trace_refs_canonical_shape(self):
        parsed = _make_parsed()
        classification = _make_classification()
        record = build_capture_record(
            parsed=parsed,
            classification=classification,
            source="ci_log",
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert "trace_refs" in record
        assert "primary" in record["trace_refs"]
        assert "related" in record["trace_refs"]
        assert record["trace_refs"]["primary"] == TRACE_ID

    def test_optional_line_number_included_when_present(self):
        parsed = _make_parsed(line_number=42)
        classification = _make_classification()
        record = build_capture_record(
            parsed=parsed,
            classification=classification,
            source="pre_pr_gate",
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert record["line_number"] == 42

    def test_optional_line_number_absent_when_none(self):
        parsed = _make_parsed(line_number=None)
        classification = _make_classification()
        record = build_capture_record(
            parsed=parsed,
            classification=classification,
            source="pre_pr_gate",
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert "line_number" not in record

    def test_optional_exit_code_included_when_present(self):
        parsed = _make_parsed(exit_code=1)
        classification = _make_classification()
        record = build_capture_record(
            parsed=parsed,
            classification=classification,
            source="local_run",
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert record["exit_code"] == 1

    def test_deterministic_id(self):
        parsed = _make_parsed()
        classification = _make_classification()
        r1 = build_capture_record(
            parsed=parsed,
            classification=classification,
            source="pre_pr_gate",
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        r2 = build_capture_record(
            parsed=parsed,
            classification=classification,
            source="pre_pr_gate",
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert r1["id"] == r2["id"]

    @pytest.mark.parametrize("failure_class", [
        "authority_shape_violation",
        "system_registry_mismatch",
        "contract_schema_violation",
        "missing_required_artifact",
        "trace_missing",
        "replay_mismatch",
        "policy_mismatch",
        "pytest_selection_missing",
        "timeout",
        "rate_limited",
        "unknown_failure",
    ])
    def test_all_failure_classes_produce_valid_records(self, failure_class: str):
        parsed = _make_parsed(failure_class)
        classification = _make_classification(failure_class)
        record = build_capture_record(
            parsed=parsed,
            classification=classification,
            source="pre_pr_gate",
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert record["failure_class"] == failure_class


class TestBuildFailurePacket:
    def _make_capture(self, failure_class: str = "authority_shape_violation") -> dict:
        parsed = _make_parsed(failure_class)
        classification = _make_classification(failure_class)
        return build_capture_record(
            parsed=parsed,
            classification=classification,
            source="pre_pr_gate",
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )

    def test_produces_required_fields(self):
        capture = self._make_capture()
        classification = _make_classification()
        packet = build_failure_packet(
            capture_record=capture,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert packet["artifact_type"] == "pre_pr_failure_packet"
        assert packet["schema_version"] == "1.0.0"
        assert packet["id"].startswith("prl-pkt-")
        assert packet["run_id"] == RUN_ID
        assert packet["trace_id"] == TRACE_ID
        assert packet["control_signal"] in {"block", "freeze", "warn", "allow"}
        assert packet["failure_class"] == "authority_shape_violation"

    def test_capture_record_ref_format(self):
        capture = self._make_capture()
        classification = _make_classification()
        packet = build_failure_packet(
            capture_record=capture,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert packet["capture_record_ref"].startswith("pr_failure_capture_record:")

    def test_remediation_hint_non_empty(self):
        capture = self._make_capture()
        classification = _make_classification()
        packet = build_failure_packet(
            capture_record=capture,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert packet["remediation_hint"]

    def test_deterministic_id(self):
        capture = self._make_capture()
        classification = _make_classification()
        p1 = build_failure_packet(
            capture_record=capture,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        p2 = build_failure_packet(
            capture_record=capture,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert p1["id"] == p2["id"]

    def test_trace_refs_include_related(self):
        capture = self._make_capture()
        classification = _make_classification()
        packet = build_failure_packet(
            capture_record=capture,
            classification=classification,
            run_id=RUN_ID,
            trace_id=TRACE_ID,
        )
        assert "trace_refs" in packet
        assert isinstance(packet["trace_refs"]["related"], list)
