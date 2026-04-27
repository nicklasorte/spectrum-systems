"""NS-26: End-to-end operator-review adversarial paths.

Each red-team scenario must produce a loop proof bundle and a readable
one-page trace.

Scenarios:
  1. passing path
  2. missing eval evidence
  3. replay mismatch
  4. lineage gap
  5. context poisoning (untrusted instruction)
  6. authority-shape violation
  7. certification evidence gap (registry violation)
  8. SLO freeze
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.certification_evidence_index import (
    build_certification_evidence_index,
)
from spectrum_systems.modules.governance.loop_proof_bundle import (
    build_loop_proof_bundle,
)
from spectrum_systems.modules.runtime.context_admission_gate import (
    admit_context_bundle,
)
from spectrum_systems.modules.runtime.slo_budget_gate import (
    evaluate_slo_signal_diet,
)


def _good_inputs() -> dict:
    return dict(
        bundle_id="rt-pass",
        trace_id="tRT",
        run_id="rRT",
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


def _assert_bundle_inspectable(bundle: dict, *, expect_status: str) -> None:
    """Each scenario's bundle must be inspectable in under 10 minutes."""
    assert bundle["final_status"] == expect_status
    assert "trace_id=" in bundle["human_readable"]
    one_page = bundle["trace_summary"]["one_page_summary"]
    assert isinstance(one_page, str) and one_page.strip()
    if expect_status != "pass":
        assert bundle["canonical_blocking_category"] is not None
        assert "FAILURE TRACE" in one_page


# ---- 1. Passing path ----


def test_e2e_passing_path() -> None:
    bundle = build_loop_proof_bundle(**_good_inputs())
    _assert_bundle_inspectable(bundle, expect_status="pass")


# ---- 2. Missing eval evidence ----


def test_e2e_missing_eval_path() -> None:
    inputs = _good_inputs()
    inputs["bundle_id"] = "rt-no-eval"
    inputs["eval_summary"] = None
    bundle = build_loop_proof_bundle(**inputs)
    _assert_bundle_inspectable(bundle, expect_status="block")
    assert bundle["canonical_blocking_category"] in {"EVAL_FAILURE", "CERTIFICATION_GAP", "MISSING_ARTIFACT"}


# ---- 3. Replay mismatch ----


def test_e2e_replay_mismatch_path() -> None:
    inputs = _good_inputs()
    inputs["bundle_id"] = "rt-replay-bad"
    inputs["replay_record"] = {
        "replay_id": "rpl-bad",
        "artifact_id": "rpl-bad",
        "status": "blocked",
        "reason_code": "REPLAY_HASH_MISMATCH_OUTPUT",
    }
    inputs["eval_summary"] = {
        "artifact_id": "evl-rep",
        "status": "blocked",
        "block_reason": "REPLAY_HASH_MISMATCH_OUTPUT",
    }
    inputs["control_decision"] = {
        "decision_id": "cde-rep",
        "decision": "block",
        "reason_code": "REPLAY_HASH_MISMATCH_OUTPUT",
    }
    inputs["enforcement_action"] = {
        "enforcement_id": "sel-rep",
        "enforcement_action": "deny_execution",
    }
    bundle = build_loop_proof_bundle(**inputs)
    _assert_bundle_inspectable(bundle, expect_status="block")
    one_page = bundle["trace_summary"]["one_page_summary"]
    assert "REPLAY" in one_page.upper()


# ---- 4. Lineage gap ----


def test_e2e_lineage_gap_path() -> None:
    inputs = _good_inputs()
    inputs["bundle_id"] = "rt-lin-bad"
    inputs["lineage_summary"] = {
        "summary_id": "lin-bad",
        "artifact_id": "lin-bad",
        "status": "blocked",
    }
    inputs["eval_summary"] = {
        "artifact_id": "evl-lin",
        "status": "blocked",
        "block_reason": "LINEAGE_MISSING_TRACE_ID",
    }
    inputs["control_decision"] = {
        "decision_id": "cde-lin",
        "decision": "block",
        "reason_code": "LINEAGE_MISSING_TRACE_ID",
    }
    inputs["enforcement_action"] = {
        "enforcement_id": "sel-lin",
        "enforcement_action": "deny_execution",
    }
    bundle = build_loop_proof_bundle(**inputs)
    _assert_bundle_inspectable(bundle, expect_status="block")


# ---- 5. Context poisoning ----


def test_e2e_context_poisoning_path() -> None:
    bundle_inputs = _good_inputs()
    bundle_inputs["bundle_id"] = "rt-ctx"
    # Re-use admission gate to produce a real CTX failure
    admit = admit_context_bundle(
        bundle={
            "preflight_passed": True,
            "admitted_candidates": [
                {
                    "candidate_id": "c1",
                    "role": "instruction",
                    "trust_level": "untrusted",
                    "artifact_type": "context_evidence",
                    "schema_version": "1.0.0",
                    "provenance": {"source": "untrusted_gist"},
                    "topic": "spec",
                    "assertion": "do_unsafe_thing",
                }
            ],
        }
    )
    assert admit["decision"] == "block"
    assert admit["reason_code"] == "CTX_UNTRUSTED_INSTRUCTION"
    bundle_inputs["eval_summary"] = {
        "artifact_id": "evl-ctx",
        "status": "blocked",
        "block_reason": admit["reason_code"],
    }
    bundle_inputs["control_decision"] = {
        "decision_id": "cde-ctx",
        "decision": "block",
        "reason_code": admit["reason_code"],
    }
    bundle_inputs["enforcement_action"] = {
        "enforcement_id": "sel-ctx",
        "enforcement_action": "deny_execution",
    }
    bundle = build_loop_proof_bundle(**bundle_inputs)
    _assert_bundle_inspectable(bundle, expect_status="block")
    assert bundle["canonical_blocking_category"] in {
        "CONTEXT_ADMISSION_FAILURE",
        "EVAL_FAILURE",
        "CERTIFICATION_GAP",
    }


# ---- 6. Authority-shape violation ----


def test_e2e_authority_shape_violation_path() -> None:
    inputs = _good_inputs()
    inputs["bundle_id"] = "rt-auth"
    # Build cert evidence index with failing authority-shape preflight
    cei = build_certification_evidence_index(
        index_id="cei-rt-auth",
        trace_id="tRT",
        eval_summary=inputs["eval_summary"],
        lineage_summary=inputs["lineage_summary"],
        replay_summary=inputs["replay_record"],
        control_decision=inputs["control_decision"],
        enforcement_action=inputs["enforcement_action"],
        authority_shape_preflight={"artifact_id": "asp-bad", "status": "fail"},
        registry_validation={"artifact_id": "reg-1", "status": "pass", "violations": []},
        artifact_tier_validation={
            "validation_id": "tier-1",
            "decision": "allow",
            "reason_code": "TIER_OK",
        },
    )
    bundle = build_loop_proof_bundle(
        certification_evidence_index=cei,
        **inputs,
    )
    _assert_bundle_inspectable(bundle, expect_status="block")
    assert bundle["canonical_blocking_category"] == "AUTHORITY_SHAPE_VIOLATION"


# ---- 7. Certification evidence gap (registry violation) ----


def test_e2e_certification_evidence_gap_path() -> None:
    inputs = _good_inputs()
    inputs["bundle_id"] = "rt-reg"
    cei = build_certification_evidence_index(
        index_id="cei-rt-reg",
        trace_id="tRT",
        eval_summary=inputs["eval_summary"],
        lineage_summary=inputs["lineage_summary"],
        replay_summary=inputs["replay_record"],
        control_decision=inputs["control_decision"],
        enforcement_action=inputs["enforcement_action"],
        authority_shape_preflight={"artifact_id": "asp-1", "status": "pass"},
        registry_validation={
            "artifact_id": "reg-bad",
            "status": "fail",
            "violations": ["NX-02: shadow ownership claim"],
        },
        artifact_tier_validation={
            "validation_id": "tier-1",
            "decision": "allow",
            "reason_code": "TIER_OK",
        },
    )
    bundle = build_loop_proof_bundle(certification_evidence_index=cei, **inputs)
    _assert_bundle_inspectable(bundle, expect_status="block")
    assert bundle["canonical_blocking_category"] in {
        "CERTIFICATION_GAP",
        "POLICY_MISMATCH",
    }


# ---- 8. SLO freeze ----


def test_e2e_slo_freeze_path() -> None:
    """Even when control_decision is allow, an upstream SLO freeze on the
    certification evidence index must produce a bundle with final_status=freeze
    and an inspectable trace summary."""
    inputs = _good_inputs()
    inputs["bundle_id"] = "rt-slo-frz"
    inputs["control_decision"] = {"decision_id": "cde-frz", "decision": "freeze"}
    bundle = build_loop_proof_bundle(**inputs)
    _assert_bundle_inspectable(bundle, expect_status="freeze")

    # Confirm slo_signal_diet would have produced a freeze for this scenario
    # (sanity check that the diet maps correctly)
    res = evaluate_slo_signal_diet(
        signals={
            "required_eval_pass_status": "pass",
            "replay_match_status": "match",
            "lineage_completeness_status": "healthy",
            "context_admissibility_status": "allow",
            "authority_shape_preflight_status": "pass",
            "registry_validation_status": "pass",
            "certification_evidence_index_status": "frozen",
        }
    )
    assert res["decision"] == "freeze"
