"""Tests for PRL-01 failure_classifier: deterministic lookup table."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.prl.failure_classifier import (
    CONTROL_SIGNAL,
    KNOWN_FAILURE_CLASSES,
    OWNING_SYSTEM,
    Classification,
    aggregate_control_signal,
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

    def test_all_classes_have_control_signal(self):
        for fc in KNOWN_FAILURE_CLASSES:
            assert fc in CONTROL_SIGNAL, f"Missing CONTROL_SIGNAL for {fc}"

    def test_all_classes_have_owning_system(self):
        for fc in KNOWN_FAILURE_CLASSES:
            assert fc in OWNING_SYSTEM, f"Missing OWNING_SYSTEM for {fc}"

    def test_all_control_signals_are_valid(self):
        valid = {"block", "freeze", "warn", "allow"}
        for fc, signal in CONTROL_SIGNAL.items():
            assert signal in valid, f"{fc} has invalid signal {signal}"


class TestClassify:
    @pytest.mark.parametrize("failure_class,expected_signal", [
        ("authority_shape_violation", "block"),
        ("system_registry_mismatch", "block"),
        ("contract_schema_violation", "block"),
        ("missing_required_artifact", "block"),
        ("trace_missing", "block"),
        ("policy_mismatch", "block"),
        ("replay_mismatch", "freeze"),
        ("timeout", "freeze"),
        ("rate_limited", "freeze"),
        ("unknown_failure", "freeze"),
        ("pytest_selection_missing", "warn"),
    ])
    def test_control_signal_mapping(self, failure_class: str, expected_signal: str):
        parsed = _make_parsed(failure_class)
        result = classify(parsed)
        assert result.control_signal == expected_signal

    def test_unknown_class_maps_to_unknown_failure(self):
        parsed = _make_parsed("completely_invented_class")
        result = classify(parsed)
        assert result.failure_class == "unknown_failure"
        assert result.control_signal == "freeze"
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


class TestAggregateControlSignal:
    def test_block_wins_over_all(self):
        assert aggregate_control_signal(["block", "freeze", "warn", "allow"]) == "block"

    def test_freeze_wins_over_warn_allow(self):
        assert aggregate_control_signal(["freeze", "warn", "allow"]) == "freeze"

    def test_warn_wins_over_allow(self):
        assert aggregate_control_signal(["warn", "allow"]) == "warn"

    def test_all_allow_returns_allow(self):
        assert aggregate_control_signal(["allow", "allow"]) == "allow"

    def test_empty_returns_allow(self):
        assert aggregate_control_signal([]) == "allow"

    def test_single_block(self):
        assert aggregate_control_signal(["block"]) == "block"

    def test_single_freeze(self):
        assert aggregate_control_signal(["freeze"]) == "freeze"

    def test_single_warn(self):
        assert aggregate_control_signal(["warn"]) == "warn"
