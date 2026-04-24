"""Tests for enforcement_gate — mandatory enforcement_action_record requirement.

Every non-allow CDE decision must pass through the enforcement gate and be
annotated with enforcement_required=True. SEL must record before executing.
"""
from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.enforcement_gate import (
    apply_enforcement_gate,
    build_sel_enforcement_record,
    verify_enforcement_recorded,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cde_decision(system_response: str = "allow", decision_id: str = "ECD-ABCDEF123456") -> dict:
    return {
        "artifact_type": "evaluation_control_decision",
        "schema_version": "1.2.0",
        "decision_id": decision_id,
        "system_response": system_response,
        "decision": "allow" if system_response == "allow" else "deny",
    }


def _continuation_decision(outcome: str = "continue_repair_bounded") -> dict:
    return {
        "artifact_type": "continuation_decision_record",
        "schema_version": "1.0.0",
        "decision_id": "cde-dec-abc123",
        "decision_outcome": outcome,
    }


def _minimal_enforcement_record() -> dict:
    return {
        "artifact_type": "sel_enforcement_action_record",
        "schema_version": "1.0.0",
        "action_id": "sel-act-000000000001",
        "action_taken": "block",
    }


# ---------------------------------------------------------------------------
# apply_enforcement_gate — allow decisions
# ---------------------------------------------------------------------------

class TestApplyEnforcementGateAllow:
    def test_allow_enforcement_not_required(self) -> None:
        gate = apply_enforcement_gate(_cde_decision("allow"))
        assert gate["enforcement_required"] is False

    def test_allow_enforcement_action_record_not_required(self) -> None:
        gate = apply_enforcement_gate(_cde_decision("allow"))
        assert gate["enforcement_action_record_required"] is False

    def test_allow_gate_has_correct_type(self) -> None:
        gate = apply_enforcement_gate(_cde_decision("allow"))
        assert gate["artifact_type"] == "enforcement_gate_decision"

    def test_allow_gate_has_gate_id(self) -> None:
        gate = apply_enforcement_gate(_cde_decision("allow"))
        assert gate["gate_id"].startswith("enf-gate-")


# ---------------------------------------------------------------------------
# apply_enforcement_gate — warn/freeze/block decisions
# ---------------------------------------------------------------------------

class TestApplyEnforcementGateNonAllow:
    @pytest.mark.parametrize("response", ["warn", "freeze", "block"])
    def test_non_allow_enforcement_required(self, response: str) -> None:
        gate = apply_enforcement_gate(_cde_decision(response))
        assert gate["enforcement_required"] is True, f"{response} must require enforcement"

    @pytest.mark.parametrize("response", ["warn", "freeze", "block"])
    def test_non_allow_action_record_required_before_execution(self, response: str) -> None:
        gate = apply_enforcement_gate(_cde_decision(response))
        assert gate["enforcement_action_record_required_before_execution"] is True

    @pytest.mark.parametrize("outcome", ["block", "human_review_required", "quarantine", "halt"])
    def test_continuation_decision_non_allow_outcomes_require_enforcement(self, outcome: str) -> None:
        gate = apply_enforcement_gate(_continuation_decision(outcome))
        assert gate["enforcement_required"] is True, f"outcome={outcome} must require enforcement"

    def test_continue_repair_bounded_does_not_require_enforcement(self) -> None:
        gate = apply_enforcement_gate(_continuation_decision("continue_repair_bounded"))
        assert gate["enforcement_required"] is False

    def test_gate_references_original_decision(self) -> None:
        decision = _cde_decision("block", "ECD-TESTID123456")
        gate = apply_enforcement_gate(decision)
        assert "evaluation_control_decision" in gate["original_decision_ref"]
        assert "ECD-TESTID123456" in gate["original_decision_ref"]

    def test_apply_enforcement_gate_raises_on_non_dict(self) -> None:
        with pytest.raises(ValueError, match="must be a dict"):
            apply_enforcement_gate("not_a_dict")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# verify_enforcement_recorded
# ---------------------------------------------------------------------------

class TestVerifyEnforcementRecorded:
    def test_allow_gate_no_record_needed_passes(self) -> None:
        gate = apply_enforcement_gate(_cde_decision("allow"))
        result = verify_enforcement_recorded(gate, None)
        assert result["verified"] is True
        assert result["action_recorded"] is False

    def test_non_allow_gate_with_record_passes(self) -> None:
        gate = apply_enforcement_gate(_cde_decision("block"))
        record = _minimal_enforcement_record()
        result = verify_enforcement_recorded(gate, record)
        assert result["verified"] is True
        assert result["action_recorded"] is True

    def test_non_allow_gate_without_record_raises(self) -> None:
        gate = apply_enforcement_gate(_cde_decision("block"))
        with pytest.raises(RuntimeError, match="ENFORCEMENT_BYPASS_VIOLATION"):
            verify_enforcement_recorded(gate, None)

    def test_non_allow_gate_with_non_dict_record_raises(self) -> None:
        gate = apply_enforcement_gate(_cde_decision("freeze"))
        with pytest.raises(RuntimeError, match="ENFORCEMENT_BYPASS_VIOLATION"):
            verify_enforcement_recorded(gate, "not_a_dict")  # type: ignore[arg-type]

    @pytest.mark.parametrize("response", ["warn", "freeze", "block"])
    def test_all_non_allow_require_enforcement_record(self, response: str) -> None:
        gate = apply_enforcement_gate(_cde_decision(response))
        with pytest.raises(RuntimeError, match="ENFORCEMENT_BYPASS_VIOLATION"):
            verify_enforcement_recorded(gate, None)


# ---------------------------------------------------------------------------
# build_sel_enforcement_record
# ---------------------------------------------------------------------------

class TestBuildSelEnforcementRecord:
    def test_record_has_correct_type(self) -> None:
        gate = apply_enforcement_gate(_cde_decision("block"))
        record = build_sel_enforcement_record(
            gate_decision=gate,
            action_taken="block",
            trace_id="trace-abc123",
            decision_ref="evaluation_control_decision:ECD-ABCDEF123456",
            reason="trust_breach detected",
        )
        assert record["artifact_type"] == "sel_enforcement_action_record"

    def test_record_has_recorded_before_execution_true(self) -> None:
        gate = apply_enforcement_gate(_cde_decision("freeze"))
        record = build_sel_enforcement_record(
            gate_decision=gate,
            action_taken="freeze",
            trace_id="trace-xyz",
            decision_ref="decision:123",
            reason="budget_exhausted",
        )
        assert record["recorded_before_execution"] is True

    def test_record_has_gate_id(self) -> None:
        gate = apply_enforcement_gate(_cde_decision("warn"))
        record = build_sel_enforcement_record(
            gate_decision=gate,
            action_taken="warn",
            trace_id="trace-001",
            decision_ref="decision:001",
            reason="warning threshold",
        )
        assert record["gate_id"] == gate["gate_id"]

    def test_record_id_format(self) -> None:
        gate = apply_enforcement_gate(_cde_decision("block"))
        record = build_sel_enforcement_record(
            gate_decision=gate,
            action_taken="block",
            trace_id="trace-001",
            decision_ref="decision:001",
            reason="test",
        )
        assert record["record_id"].startswith("sel-enf-")

    def test_record_is_valid_for_verify_enforcement(self) -> None:
        gate = apply_enforcement_gate(_cde_decision("block"))
        record = build_sel_enforcement_record(
            gate_decision=gate,
            action_taken="block",
            trace_id="trace-001",
            decision_ref="decision:001",
            reason="test",
        )
        result = verify_enforcement_recorded(gate, record)
        assert result["verified"] is True
        assert result["action_recorded"] is True


# ---------------------------------------------------------------------------
# End-to-end gate cycle
# ---------------------------------------------------------------------------

class TestEnforcementGateCycle:
    def test_full_cycle_block_decision(self) -> None:
        """Full cycle: block decision → gate marks enforcement required → record produced → verified."""
        cde = _cde_decision("block", "ECD-CYCLE001")
        gate = apply_enforcement_gate(cde)

        assert gate["enforcement_required"] is True

        sel_record = build_sel_enforcement_record(
            gate_decision=gate,
            action_taken="block",
            trace_id="trace-cycle-001",
            decision_ref=gate["original_decision_ref"],
            reason="trust_breach",
        )

        verification = verify_enforcement_recorded(gate, sel_record)
        assert verification["verified"] is True

    def test_full_cycle_allow_decision_no_record_needed(self) -> None:
        """Full cycle: allow decision → gate marks no enforcement → no record needed."""
        cde = _cde_decision("allow", "ECD-ALLOW001")
        gate = apply_enforcement_gate(cde)

        assert gate["enforcement_required"] is False

        verification = verify_enforcement_recorded(gate, None)
        assert verification["verified"] is True
        assert verification["action_recorded"] is False
