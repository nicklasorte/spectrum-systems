"""Tests for RGE Phase Justification Gate (Principle 1: Kill Complexity Early)."""
from __future__ import annotations

import pytest

from spectrum_systems.rge.phase_justification_gate import (
    CANONICAL_LOOP_LEGS,
    PhaseJustificationError,
    validate_phase_justification,
)

_RUN = "run-test-001"
_TRACE = "trace-test-001"


def _good(**overrides: str) -> dict:
    base = {
        "phase_id": "P1",
        "name": "Wire EVL eval gate",
        "failure_prevented": (
            "Phases promoted without eval coverage - eval_coverage_rate "
            "drops below 80%"
        ),
        "signal_improved": "eval_coverage_rate increases from current 62% toward 90% threshold",
        "loop_leg": "EVL",
    }
    return {**base, **overrides}


class TestPhaseJustificationGate:
    def test_valid_phase_returns_allow(self):
        r = validate_phase_justification(_good(), run_id=_RUN, trace_id=_TRACE)
        assert r["decision"] == "allow"
        assert r["principle"] == "kill_complexity_early"
        assert r["errors"] == []

    def test_record_has_required_fields(self):
        r = validate_phase_justification(_good(), run_id=_RUN, trace_id=_TRACE)
        for field in ("artifact_type", "record_id", "run_id", "trace_id", "created_at"):
            assert field in r, f"missing field: {field}"
        assert r["artifact_type"] == "phase_justification_record"
        assert r["schema_version"] == "1.0.0"

    def test_missing_failure_prevented_blocks(self):
        with pytest.raises(PhaseJustificationError, match="failure_prevented"):
            validate_phase_justification(
                _good(failure_prevented=""), run_id=_RUN, trace_id=_TRACE
            )

    def test_short_failure_prevented_blocks(self):
        with pytest.raises(PhaseJustificationError, match="too vague"):
            validate_phase_justification(
                _good(failure_prevented="bad"), run_id=_RUN, trace_id=_TRACE
            )

    def test_vague_failure_prevented_blocks(self):
        with pytest.raises(PhaseJustificationError, match="vague"):
            validate_phase_justification(
                _good(failure_prevented="improve things generally in the system"),
                run_id=_RUN,
                trace_id=_TRACE,
            )

    def test_missing_signal_improved_blocks(self):
        with pytest.raises(PhaseJustificationError, match="signal_improved"):
            validate_phase_justification(
                _good(signal_improved=""), run_id=_RUN, trace_id=_TRACE
            )

    def test_unmeasurable_signal_blocks(self):
        with pytest.raises(PhaseJustificationError, match="not measurable"):
            validate_phase_justification(
                _good(signal_improved="makes the system better overall"),
                run_id=_RUN,
                trace_id=_TRACE,
            )

    def test_missing_loop_leg_blocks(self):
        with pytest.raises(PhaseJustificationError, match="loop_leg: missing"):
            validate_phase_justification(
                _good(loop_leg=""), run_id=_RUN, trace_id=_TRACE
            )

    def test_invalid_loop_leg_blocks(self):
        with pytest.raises(PhaseJustificationError, match="not a canonical loop leg"):
            validate_phase_justification(
                _good(loop_leg="MAGIC"), run_id=_RUN, trace_id=_TRACE
            )

    def test_all_canonical_legs_accepted(self):
        for leg in CANONICAL_LOOP_LEGS:
            r = validate_phase_justification(
                _good(loop_leg=leg), run_id=_RUN, trace_id=_TRACE
            )
            assert r["decision"] == "allow", f"leg {leg} was rejected"

    def test_deletion_phase_must_also_justify(self):
        delete_phase = _good(
            phase_id="DEL-01",
            name="Delete unused monitoring abstraction",
            failure_prevented=(
                "Complexity budget exceeded - 3 sustained regressions in "
                "abstraction_growth score"
            ),
            signal_improved="complexity_score drops by 12 points (84 to 72, below 80 threshold)",
            loop_leg="TPA",
        )
        r = validate_phase_justification(delete_phase, run_id=_RUN, trace_id=_TRACE)
        assert r["decision"] == "allow"

    def test_stable_record_id_for_same_inputs(self):
        r1 = validate_phase_justification(_good(), run_id=_RUN, trace_id=_TRACE)
        r2 = validate_phase_justification(_good(), run_id=_RUN, trace_id=_TRACE)
        assert r1["record_id"] == r2["record_id"]

    def test_error_list_populated_on_block(self):
        with pytest.raises(PhaseJustificationError):
            validate_phase_justification(
                _good(failure_prevented=""), run_id=_RUN, trace_id=_TRACE
            )
