"""OC-22..24: Operator runbook unit + red-team tests."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.operator_runbook import (
    OperatorRunbookError,
    build_operator_runbook_entry,
)


def test_entry_id_required():
    with pytest.raises(OperatorRunbookError):
        build_operator_runbook_entry(
            entry_id="",
            audit_timestamp="2026-04-28T00:00:00Z",
        )


def test_no_inputs_yields_blocked():
    entry = build_operator_runbook_entry(
        entry_id="runbook-1",
        audit_timestamp="2026-04-28T00:00:00Z",
    )
    assert entry["status"] == "blocked"
    assert entry["claims"] == []
    assert entry["next_safe_action"] == "investigate"
    assert entry["refused_claims"]


def test_pass_path_emits_claims_with_evidence_refs():
    entry = build_operator_runbook_entry(
        entry_id="runbook-1",
        audit_timestamp="2026-04-28T00:00:00Z",
        proof_intake={"intake_id": "pii-1", "overall_status": "ok"},
        bottleneck_classification={
            "classification_id": "bc-1",
            "category": "none",
            "owning_system": None,
            "next_safe_action": {"action": "warn"},
        },
        dashboard_projection={
            "projection_id": "dtp-1",
            "alignment_status": "aligned",
        },
        closure_packet={
            "packet_id": "cdp-1",
            "packet_status": "ready_to_merge",
        },
    )
    assert entry["status"] == "pass"
    assert entry["next_safe_action"] == "merge"
    refs = {c["evidence_ref"] for c in entry["claims"]}
    assert "pii-1" in refs
    assert "cdp-1" in refs
    # every claim must have a non-empty evidence_ref
    for claim in entry["claims"]:
        assert isinstance(claim["evidence_ref"], str) and claim["evidence_ref"].strip()


# ---- OC-23 red team: stale or insufficient proof refuses confident guidance ----


def test_stale_proof_intake_forces_insufficient_evidence():
    entry = build_operator_runbook_entry(
        entry_id="runbook-stale",
        audit_timestamp="2026-04-28T00:00:00Z",
        proof_intake={
            "intake_id": "pii-1",
            "overall_status": "blocked",
            "reason_code": "PROOF_INTAKE_STALE_DIGEST_MISMATCH",
            "selections": {
                "loop_proof_bundle": {
                    "selection_status": "stale",
                    "reason_code": "PROOF_INTAKE_STALE_DIGEST_MISMATCH",
                }
            },
        },
        closure_packet={"packet_id": "cdp-1", "packet_status": "ready_to_merge"},
    )
    assert entry["status"] == "insufficient_evidence"
    assert entry["claims"] == []
    assert entry["refused_claims"]
    assert entry["next_safe_action"] == "investigate"


def test_conflicting_proof_intake_refuses_guidance():
    entry = build_operator_runbook_entry(
        entry_id="runbook-conflict",
        audit_timestamp="2026-04-28T00:00:00Z",
        proof_intake={
            "intake_id": "pii-1",
            "overall_status": "blocked",
            "reason_code": "PROOF_INTAKE_CONFLICT",
            "selections": {
                "loop_proof_bundle": {
                    "selection_status": "conflict",
                    "reason_code": "PROOF_INTAKE_CONFLICT",
                }
            },
        },
    )
    assert entry["status"] == "insufficient_evidence"


def test_freeze_input_propagates_to_runbook():
    entry = build_operator_runbook_entry(
        entry_id="runbook-freeze",
        audit_timestamp="2026-04-28T00:00:00Z",
        proof_intake={"intake_id": "pii-1", "overall_status": "ok"},
        bottleneck_classification={
            "classification_id": "bc-1",
            "category": "slo",
            "owning_system": "SLO",
            "next_safe_action": {"action": "freeze"},
        },
        closure_packet={"packet_id": "cdp-1", "packet_status": "freeze"},
    )
    assert entry["status"] == "freeze"
    assert entry["next_safe_action"] == "freeze"


def test_block_input_propagates_to_runbook():
    entry = build_operator_runbook_entry(
        entry_id="runbook-block",
        audit_timestamp="2026-04-28T00:00:00Z",
        proof_intake={"intake_id": "pii-1", "overall_status": "ok"},
        bottleneck_classification={
            "classification_id": "bc-1",
            "category": "eval",
            "owning_system": "EVL",
            "next_safe_action": {"action": "block"},
        },
        closure_packet={"packet_id": "cdp-1", "packet_status": "blocked"},
    )
    assert entry["status"] == "block"
    assert entry["next_safe_action"] == "investigate"
