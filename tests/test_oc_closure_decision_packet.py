"""OC-10..12: Closure decision packet unit + red-team tests."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.closure_decision_packet import (
    CANONICAL_REASON_CODES,
    REQUIRED_EVIDENCE_KEYS,
    ClosureDecisionPacketError,
    build_closure_decision_packet,
)


def _all_evidence_ok():
    return dict(
        proof_intake={"intake_id": "pii-1", "overall_status": "ok"},
        bottleneck_classification={
            "classification_id": "bc-1",
            "category": "none",
            "next_safe_action": {"action": "warn"},
        },
        dashboard_projection={
            "projection_id": "dtp-1",
            "alignment_status": "aligned",
        },
        fast_trust_gate={
            "manifest_id": "ftgr-1",
            "overall_status": "ok",
            "sufficiency": "sufficient",
        },
        certification_delta_proof={"delta_id": "cdp-1", "status": "ready"},
        trust_regression_pack={"pack_id": "trp-1", "status": "pass"},
        lineage_chain={"lineage_id": "lin-1", "status": "ok"},
    )


def test_required_evidence_keys_finite():
    assert set(REQUIRED_EVIDENCE_KEYS) == {
        "proof_intake_ref",
        "bottleneck_classification_ref",
        "dashboard_projection_ref",
        "fast_trust_gate_ref",
        "certification_delta_proof_ref",
        "trust_regression_pack_ref",
        "lineage_chain_ref",
    }


def test_packet_id_required():
    with pytest.raises(ClosureDecisionPacketError):
        build_closure_decision_packet(
            packet_id="",
            trace_id="t1",
            audit_timestamp="2026-04-28T00:00:00Z",
        )


def test_pass_path_yields_ready_to_merge():
    packet = build_closure_decision_packet(
        packet_id="cdp-1",
        trace_id="t1",
        audit_timestamp="2026-04-28T00:00:00Z",
        **_all_evidence_ok(),
    )
    assert packet["packet_status"] == "ready_to_merge"
    assert packet["reason_code"] == "CLOSURE_PACKET_READY"
    assert packet["missing_evidence"] == []
    assert packet["blocking_findings"] == []


def test_canonical_reason_codes_finite():
    assert "CLOSURE_PACKET_READY" in CANONICAL_REASON_CODES
    assert "CLOSURE_PACKET_BLOCKED" in CANONICAL_REASON_CODES
    assert "CLOSURE_PACKET_FROZEN" in CANONICAL_REASON_CODES
    assert "CLOSURE_PACKET_MISSING_EVIDENCE" in CANONICAL_REASON_CODES


# ---- OC-11 red team: missing evidence must block / freeze ----


def test_missing_proof_intake_marks_not_ready():
    args = _all_evidence_ok()
    args["proof_intake"] = None
    packet = build_closure_decision_packet(
        packet_id="cdp-1",
        trace_id="t1",
        audit_timestamp="2026-04-28T00:00:00Z",
        **args,
    )
    assert packet["packet_status"] in ("not_ready", "blocked", "freeze")
    assert packet["packet_status"] != "ready_to_merge"
    assert "proof_intake_ref" in packet["missing_evidence"]


def test_blocked_proof_intake_blocks_packet():
    args = _all_evidence_ok()
    args["proof_intake"] = {"intake_id": "pii-1", "overall_status": "blocked"}
    packet = build_closure_decision_packet(
        packet_id="cdp-1",
        trace_id="t1",
        audit_timestamp="2026-04-28T00:00:00Z",
        **args,
    )
    assert packet["packet_status"] == "blocked"
    assert packet["reason_code"] == "CLOSURE_PACKET_PROOF_INTAKE_BLOCKED"


def test_drifted_dashboard_blocks_packet():
    args = _all_evidence_ok()
    args["dashboard_projection"] = {
        "projection_id": "dtp-1",
        "alignment_status": "drifted",
    }
    packet = build_closure_decision_packet(
        packet_id="cdp-1",
        trace_id="t1",
        audit_timestamp="2026-04-28T00:00:00Z",
        **args,
    )
    assert packet["packet_status"] == "blocked"


def test_failed_fast_gate_blocks_packet():
    args = _all_evidence_ok()
    args["fast_trust_gate"] = {
        "manifest_id": "ftgr-1",
        "overall_status": "failed",
        "sufficiency": "insufficient",
    }
    packet = build_closure_decision_packet(
        packet_id="cdp-1",
        trace_id="t1",
        audit_timestamp="2026-04-28T00:00:00Z",
        **args,
    )
    assert packet["packet_status"] == "blocked"


def test_freeze_input_freezes_packet():
    args = _all_evidence_ok()
    args["fast_trust_gate"] = {
        "manifest_id": "ftgr-1",
        "overall_status": "freeze",
    }
    packet = build_closure_decision_packet(
        packet_id="cdp-1",
        trace_id="t1",
        audit_timestamp="2026-04-28T00:00:00Z",
        **args,
    )
    assert packet["packet_status"] == "freeze"
    assert packet["reason_code"] == "CLOSURE_PACKET_FROZEN"


def test_bottleneck_block_action_blocks_packet():
    args = _all_evidence_ok()
    args["bottleneck_classification"] = {
        "classification_id": "bc-1",
        "category": "eval",
        "next_safe_action": {"action": "block"},
    }
    packet = build_closure_decision_packet(
        packet_id="cdp-1",
        trace_id="t1",
        audit_timestamp="2026-04-28T00:00:00Z",
        **args,
    )
    assert packet["packet_status"] == "blocked"


def test_no_inputs_yields_unknown():
    packet = build_closure_decision_packet(
        packet_id="cdp-1",
        trace_id="t1",
        audit_timestamp="2026-04-28T00:00:00Z",
    )
    assert packet["packet_status"] == "unknown"
    assert packet["reason_code"] == "CLOSURE_PACKET_UNKNOWN"


def test_failing_trust_regression_blocks():
    args = _all_evidence_ok()
    args["trust_regression_pack"] = {
        "pack_id": "trp-1",
        "status": "failed",
    }
    packet = build_closure_decision_packet(
        packet_id="cdp-1",
        trace_id="t1",
        audit_timestamp="2026-04-28T00:00:00Z",
        **args,
    )
    assert packet["packet_status"] == "blocked"


def test_lineage_gap_blocks():
    args = _all_evidence_ok()
    args["lineage_chain"] = {"lineage_id": "lin-1", "status": "broken"}
    packet = build_closure_decision_packet(
        packet_id="cdp-1",
        trace_id="t1",
        audit_timestamp="2026-04-28T00:00:00Z",
        **args,
    )
    assert packet["packet_status"] == "blocked"
