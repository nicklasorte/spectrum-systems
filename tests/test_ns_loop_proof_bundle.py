"""NS-25: Loop proof bundle — passing path + blocked path."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.loop_proof_bundle import (
    LoopProofBundleError,
    build_loop_proof_bundle,
)


def _passing_inputs() -> dict:
    return dict(
        bundle_id="lpb-pass",
        trace_id="tPASS",
        run_id="rPASS",
        execution_record={
            "artifact_id": "exec-1",
            "artifact_type": "pqx_slice_execution_record",
            "status": "ok",
        },
        output_artifact={"artifact_id": "out-1", "artifact_type": "eval_summary"},
        eval_summary={"artifact_id": "evl-1", "status": "healthy"},
        control_decision={"decision_id": "cde-1", "decision": "allow"},
        enforcement_action={
            "enforcement_id": "sel-1",
            "enforcement_action": "allow_execution",
        },
        replay_record={"replay_id": "rpl-1", "artifact_id": "rpl-1", "status": "healthy"},
        lineage_summary={"summary_id": "lin-1", "artifact_id": "lin-1", "status": "healthy"},
    )


def test_passing_bundle_has_all_references_and_pass_status() -> None:
    bundle = build_loop_proof_bundle(**_passing_inputs())
    assert bundle["final_status"] == "pass"
    assert bundle["execution_record_ref"] == "exec-1"
    assert bundle["output_artifact_ref"] == "out-1"
    assert bundle["eval_summary_ref"] == "evl-1"
    assert bundle["control_decision_ref"] == "cde-1"
    assert bundle["enforcement_action_ref"] == "sel-1"
    assert bundle["replay_record_ref"] == "rpl-1"
    assert bundle["lineage_chain_ref"] == "lin-1"
    assert bundle["certification_evidence_index_ref"]
    assert bundle["trace_summary"]["overall_status"] == "ok"
    assert "trace_id=tPASS" in bundle["human_readable"]


def test_blocked_bundle_has_failure_trace_ref_and_block_status() -> None:
    inputs = _passing_inputs()
    inputs["bundle_id"] = "lpb-block"
    inputs["trace_id"] = "tBLOCK"
    inputs["eval_summary"] = {
        "artifact_id": "evl-bad",
        "status": "blocked",
        "block_reason": "missing_required_eval_result",
    }
    inputs["control_decision"] = {
        "decision_id": "cde-blk",
        "decision": "block",
        "reason_code": "missing_required_eval_result",
    }
    inputs["enforcement_action"] = {
        "enforcement_id": "sel-blk",
        "enforcement_action": "deny_execution",
    }
    bundle = build_loop_proof_bundle(**inputs)
    assert bundle["final_status"] == "block"
    assert bundle["failure_trace_ref"] is not None
    assert bundle["canonical_blocking_category"] in {
        "EVAL_FAILURE",
        "CERTIFICATION_GAP",
        "MISSING_ARTIFACT",
    }
    # one-page trace summary present and short
    summary = bundle["trace_summary"]["one_page_summary"]
    assert isinstance(summary, str) and len(summary) < 4000
    assert "FAILURE TRACE" in summary


def test_freeze_propagates_to_bundle() -> None:
    inputs = _passing_inputs()
    inputs["bundle_id"] = "lpb-frz"
    inputs["trace_id"] = "tFRZ"
    inputs["control_decision"] = {"decision_id": "cde-frz", "decision": "freeze"}
    bundle = build_loop_proof_bundle(**inputs)
    assert bundle["final_status"] == "freeze"


def test_bundle_id_required() -> None:
    with pytest.raises(LoopProofBundleError):
        build_loop_proof_bundle(bundle_id="", trace_id="t")


def test_bundle_does_not_embed_full_artifacts() -> None:
    """The bundle holds references only — payloads are not duplicated."""
    inputs = _passing_inputs()
    inputs["execution_record"]["huge"] = ["x"] * 5000
    bundle = build_loop_proof_bundle(**inputs)
    # huge payload not in references / summary
    assert "huge" not in str(bundle["execution_record_ref"])
    # bundle stays compact in human readable form
    assert len(bundle["human_readable"]) < 6000


def test_new_engineer_inspection_under_10_minutes() -> None:
    """The bundle's human_readable + trace_summary.one_page_summary must give
    the new engineer enough information to identify the failed stage,
    owning system, canonical category, and next action."""
    inputs = _passing_inputs()
    inputs["bundle_id"] = "lpb-eng"
    inputs["trace_id"] = "tENG"
    inputs["eval_summary"] = {
        "artifact_id": "evl-bad",
        "status": "blocked",
        "block_reason": "REPLAY_HASH_MISMATCH_OUTPUT",
    }
    inputs["control_decision"] = {
        "decision_id": "cde-eng",
        "decision": "block",
        "reason_code": "REPLAY_HASH_MISMATCH_OUTPUT",
    }
    inputs["enforcement_action"] = {
        "enforcement_id": "sel-eng",
        "enforcement_action": "deny_execution",
    }
    bundle = build_loop_proof_bundle(**inputs)
    one_page = bundle["trace_summary"]["one_page_summary"]
    # Required answers are in the one-page summary
    assert "failed_stage" in one_page
    assert "owning_system" in one_page
    assert "canonical_category" in one_page
    assert "next_recommended_action" in one_page
    # Stage and system are concrete
    assert bundle["trace_summary"]["failed_stage"] is not None
    assert bundle["trace_summary"]["owning_system"] is not None
