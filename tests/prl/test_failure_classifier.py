"""Tests for PRL-01 failure_classifier: deterministic lookup table."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.prl.failure_classifier import (
    GATE_SIGNAL,
    KNOWN_FAILURE_CLASSES,
    OWNING_SYSTEM,
    Classification,
    aggregate_gate_signal,
    classify,
)
from spectrum_systems.modules.prl.failure_parser import ParsedFailure


def _make_parsed(failure_class: str) -> ParsedFailure:
    return ParsedFailure(
        failure_class=failure_class,
        raw_excerpt="test excerpt",
        normalized_message="test message",
        file_refs=(),
        line_number=None,
        exit_code=None,
    )


class TestKnownFailureClasses:
    def test_all_required_classes_present(self):
        required = {
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
        }
        assert required == KNOWN_FAILURE_CLASSES

    def test_all_classes_have_gate_signal(self):
        for fc in KNOWN_FAILURE_CLASSES:
            assert fc in GATE_SIGNAL, f"Missing GATE_SIGNAL for {fc}"

    def test_all_classes_have_owning_system(self):
        for fc in KNOWN_FAILURE_CLASSES:
            assert fc in OWNING_SYSTEM, f"Missing OWNING_SYSTEM for {fc}"

    def test_all_gate_signals_are_valid(self):
        valid = {"failed_gate", "gate_hold", "gate_warn", "passed_gate"}
        for fc, signal in GATE_SIGNAL.items():
            assert signal in valid, f"{fc} has invalid signal {signal}"


class TestClassify:
    @pytest.mark.parametrize("failure_class,expected_signal", [
        ("authority_shape_violation", "failed_gate"),
        ("system_registry_mismatch", "failed_gate"),
        ("contract_schema_violation", "failed_gate"),
        ("missing_required_artifact", "failed_gate"),
        ("trace_missing", "failed_gate"),
        ("policy_mismatch", "failed_gate"),
        ("replay_mismatch", "gate_hold"),
        ("timeout", "gate_hold"),
        ("rate_limited", "gate_hold"),
        ("unknown_failure", "gate_hold"),
        ("pytest_selection_missing", "gate_warn"),
    ])
    def test_gate_signal_mapping(self, failure_class: str, expected_signal: str):
        parsed = _make_parsed(failure_class)
        result = classify(parsed)
        assert result.gate_signal == expected_signal

    def test_unknown_class_maps_to_unknown_failure(self):
        parsed = _make_parsed("completely_invented_class")
        result = classify(parsed)
        assert result.failure_class == "unknown_failure"
        assert result.gate_signal == "gate_hold"
        assert result.is_known is False

    def test_known_class_is_known_true(self):
        parsed = _make_parsed("authority_shape_violation")
        result = classify(parsed)
        assert result.is_known is True

    def test_unknown_failure_is_known_false(self):
        parsed = _make_parsed("unknown_failure")
        result = classify(parsed)
        assert result.is_known is False

    def test_classification_is_frozen_dataclass(self):
        parsed = _make_parsed("timeout")
        result = classify(parsed)
        with pytest.raises((AttributeError, TypeError)):
            result.failure_class = "something_else"  # type: ignore[misc]

    @pytest.mark.parametrize("failure_class,expected_owner", [
        ("authority_shape_violation", "AEX"),
        ("system_registry_mismatch", "MAP"),
        ("contract_schema_violation", "EVL"),
        ("missing_required_artifact", "LIN"),
        ("trace_missing", "OBS"),
        ("replay_mismatch", "REP"),
        ("policy_mismatch", "TPA"),
        ("timeout", "PQX"),
        ("rate_limited", "PQX"),
        ("unknown_failure", "FRE"),
        ("pytest_selection_missing", "PRL"),
    ])
    def test_owning_system_mapping(self, failure_class: str, expected_owner: str):
        parsed = _make_parsed(failure_class)
        result = classify(parsed)
        assert result.owning_system == expected_owner

    def test_remediation_hint_non_empty(self):
        for fc in KNOWN_FAILURE_CLASSES:
            parsed = _make_parsed(fc)
            result = classify(parsed)
            assert result.remediation_hint, f"Empty remediation_hint for {fc}"


class TestAggregateGateSignal:
    def test_failed_gate_wins_over_all(self):
        assert aggregate_gate_signal(["failed_gate", "gate_hold", "gate_warn", "passed_gate"]) == "failed_gate"

    def test_gate_hold_wins_over_warn_passed(self):
        assert aggregate_gate_signal(["gate_hold", "gate_warn", "passed_gate"]) == "gate_hold"

    def test_gate_warn_wins_over_passed(self):
        assert aggregate_gate_signal(["gate_warn", "passed_gate"]) == "gate_warn"

    def test_all_passed_returns_passed_gate(self):
        assert aggregate_gate_signal(["passed_gate", "passed_gate"]) == "passed_gate"

    def test_empty_returns_passed_gate(self):
        assert aggregate_gate_signal([]) == "passed_gate"

    def test_single_failed_gate(self):
        assert aggregate_gate_signal(["failed_gate"]) == "failed_gate"

    def test_single_gate_hold(self):
        assert aggregate_gate_signal(["gate_hold"]) == "gate_hold"

    def test_single_gate_warn(self):
        assert aggregate_gate_signal(["gate_warn"]) == "gate_warn"
