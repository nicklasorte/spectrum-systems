"""Tests for the RFX freeze propagation record (Part 3)."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_freeze_propagation import (
    RFXFreezePropagationError,
    propagate_rfx_freeze,
)


def test_propagate_emits_record_with_required_targets() -> None:
    rec = propagate_rfx_freeze(
        reason_codes=["rfx_instability_detected"],
        downstream_targets=[],
        trace_id="trace-001",
        created_at="2026-04-25T00:00:00Z",
    )
    assert rec["artifact_type"] == "rfx_freeze_record"
    assert rec["pqx_execution_blocked"] is True
    assert rec["cde_ready_blocked"] is True
    assert rec["gov_certification_blocked"] is True
    assert rec["sel_enforcement_signal"] == "halt_requested"
    for target in ("PQX", "CDE", "GOV", "SEL"):
        assert target in rec["downstream_targets"]
        assert target in rec["propagation"]


def test_propagate_unions_caller_supplied_targets() -> None:
    rec = propagate_rfx_freeze(
        reason_codes=["rfx_replay_drift_detected"],
        downstream_targets=["AEX", "TLC"],
    )
    assert "AEX" in rec["downstream_targets"]
    assert "TLC" in rec["downstream_targets"]
    # canonical targets are still present
    for target in ("PQX", "CDE", "GOV", "SEL"):
        assert target in rec["downstream_targets"]


def test_propagate_dedupes_reason_codes_preserves_order() -> None:
    rec = propagate_rfx_freeze(
        reason_codes=["rfx_a", "rfx_b", "rfx_a"],
        downstream_targets=[],
    )
    assert rec["reason_codes"] == ["rfx_a", "rfx_b"]


@pytest.mark.parametrize("bad", [None, [], [""], [None]])
def test_propagate_rejects_invalid_reason_codes(bad) -> None:
    with pytest.raises(RFXFreezePropagationError, match="rfx_freeze_propagation_invalid"):
        propagate_rfx_freeze(reason_codes=bad, downstream_targets=[])


def test_propagate_rejects_invalid_downstream_target() -> None:
    with pytest.raises(RFXFreezePropagationError, match="rfx_freeze_propagation_invalid"):
        propagate_rfx_freeze(
            reason_codes=["rfx_instability_detected"],
            downstream_targets=["AEX", ""],
        )


def test_propagate_freeze_id_is_deterministic() -> None:
    a = propagate_rfx_freeze(
        reason_codes=["rfx_a"], downstream_targets=[], trace_id="t", created_at="c",
    )
    b = propagate_rfx_freeze(
        reason_codes=["rfx_a"], downstream_targets=[], trace_id="t", created_at="c",
    )
    assert a["freeze_id"] == b["freeze_id"]
