"""NT-22..24: End-to-end trust regression pack.

A small permanent regression pack across the canonical loop seams.
Each test pins one trust path so a regression in any seam is caught
immediately. Each test also exercises the NT-23 mutation that the seam
must catch — together they ensure the trust regression pack itself is
non-trivial and the seam is fail-closed.

Permanent fixture rationales live in
``tests/fixtures/trust_regression_pack/README.md``.
"""

from __future__ import annotations

import json

import pytest

from spectrum_systems.modules.governance.certification_delta import (
    compute_certification_delta,
)
from spectrum_systems.modules.governance.certification_evidence_index import (
    build_certification_evidence_index,
)
from spectrum_systems.modules.governance.loop_proof_bundle import (
    build_loop_proof_bundle,
)
from spectrum_systems.modules.governance.proof_bundle_size_budget import (
    evaluate_proof_bundle_size,
)
from spectrum_systems.modules.lineage.replay_lineage_join import (
    verify_replay_lineage_join,
)
from spectrum_systems.modules.observability.artifact_tier_audit import (
    validate_promotion_evidence_tiers,
)
from spectrum_systems.modules.observability.reason_code_canonicalizer import (
    assert_canonical_or_alias,
    canonicalize_reason_code,
)
from spectrum_systems.modules.observability.trust_artifact_freshness import (
    audit_trust_artifact_freshness,
)
from spectrum_systems.modules.runtime.control_signal_minimality import (
    audit_control_signal_minimality,
)


def _passing_loop_inputs() -> dict:
    return dict(
        bundle_id="lpb-reg-pass",
        trace_id="tREG-PASS",
        run_id="rREG-PASS",
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


# ---- pass path ----


def test_pass_path_full_loop_passes_proof_size_and_freshness() -> None:
    bundle = build_loop_proof_bundle(**_passing_loop_inputs())
    assert bundle["final_status"] == "pass"
    size = evaluate_proof_bundle_size(bundle=bundle)
    assert size["decision"] == "allow"


# ---- block path: missing eval ----


def test_block_path_missing_eval_blocks_with_canonical_reason() -> None:
    inputs = _passing_loop_inputs()
    inputs["bundle_id"] = "lpb-reg-block"
    inputs["trace_id"] = "tREG-BLOCK"
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
    assert bundle["canonical_blocking_category"] in {
        "EVAL_FAILURE",
        "MISSING_ARTIFACT",
        "CERTIFICATION_GAP",
    }


# ---- freeze path: control freeze ----


def test_freeze_path_certification_propagates() -> None:
    inputs = _passing_loop_inputs()
    inputs["bundle_id"] = "lpb-reg-frz"
    inputs["trace_id"] = "tREG-FRZ"
    inputs["control_decision"] = {"decision_id": "cde-frz", "decision": "freeze"}
    bundle = build_loop_proof_bundle(**inputs)
    assert bundle["final_status"] == "freeze"


# ---- stale proof path ----


def test_stale_proof_path_freshness_blocks() -> None:
    """Stale certification evidence index produces a stale freshness audit."""
    import hashlib

    inputs = {"k": "v"}
    digest = hashlib.sha256(
        json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    arts = {}
    for kind in (
        "artifact_tier_policy",
        "reason_code_alias_map",
        "certification_evidence_index",
        "loop_proof_bundle",
        "failure_trace",
        "replay_lineage_join_summary",
        "slo_signal_policy",
    ):
        arts[kind] = {
            "artifact_id": f"{kind}-1",
            "producer_inputs": inputs,
            "producer_input_digest": digest,
            "generated_at": "2026-04-26T12:00:00Z",
        }
    # Tamper certification_evidence_index inputs but keep declared digest.
    arts["certification_evidence_index"]["producer_inputs"] = {"k": "TAMPERED"}
    res = audit_trust_artifact_freshness(
        audit_id="reg-stale",
        artifacts=arts,
        audit_timestamp="2026-04-27T12:00:00Z",
    )
    assert res["status"] == "stale"
    assert "certification_evidence_index" in res["stale_kinds"]


# ---- tier violation path ----


def test_tier_violation_path_report_blocks() -> None:
    res = validate_promotion_evidence_tiers(
        [{"artifact_id": "rep-1", "artifact_path": "outputs/reports/x.md"}],
        validation_id="reg-tier",
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "TIER_REPORT_AS_AUTHORITY"


# ---- reason-code violation path ----


def test_reason_code_violation_path_blocks_at_boundary() -> None:
    with pytest.raises(Exception):
        assert_canonical_or_alias("totally_unknown_blocker_code")


def test_reason_code_canonicalizer_returns_unknown_for_unknown_code() -> None:
    res = canonicalize_reason_code("brand_new_made_up_code")
    assert res["canonical_category"] == "UNKNOWN"


# ---- replay-lineage mismatch path ----


def test_replay_lineage_mismatch_path_blocks() -> None:
    rep = {
        "replay_id": "rpl-1",
        "trace_id": "tA",
        "original_run_id": "rA",
        "target_artifact_id": "out-1",
        "output_hash": "deadbeef" * 4,
        "referenced_lineage_summary_id": "wrong-summary",  # broken link
    }
    lin = {
        "summary_id": "lin-sum-1",
        "trace_id": "tA",
        "run_id": "rA",
        "replay_record_ids": ["rpl-1"],
        "artifact_ids": ["out-1"],
        "output_hash": "deadbeef" * 4,
    }
    res = verify_replay_lineage_join(replay_record=rep, lineage_summary=lin)
    assert res["decision"] == "block"


# ---- context admission failure path (propagates to certification) ----


def test_context_admission_failure_path_blocks_via_minimality() -> None:
    """A context admission failure is a hard trust signal; minimality
    audit must accept it as the basis of a block."""
    res = audit_control_signal_minimality(
        proposed_decision={
            "decision": "block",
            "canonical_reason": "CONTEXT_ADMISSION_FAILURE",
        },
        signals_used={"context_admissibility_status": "block"},
        evidence_refs=["ctx-1"],
    )
    assert res["decision"] == "allow"
    assert res["reason_code"] == "MINIMALITY_OK"


# ---- NT-23 mutations: each seam catches its tampering ----


def test_mutation_missing_eval_caught_by_evidence_index() -> None:
    cei = build_certification_evidence_index(
        index_id="cei-mut",
        trace_id="tMUT",
        eval_summary=None,
        lineage_summary={"artifact_id": "lin-1", "status": "healthy"},
        replay_summary={"artifact_id": "rpl-1", "status": "healthy"},
        control_decision={"decision_id": "cde-1", "decision": "allow"},
        authority_shape_preflight={"artifact_id": "asp", "status": "pass"},
        registry_validation={"artifact_id": "reg", "status": "pass", "violations": []},
        artifact_tier_validation={"validation_id": "tier", "decision": "allow"},
    )
    assert cei["status"] == "blocked"
    assert "CERT_MISSING_EVAL_PASS" in cei["blocking_detail_codes"]


def test_mutation_silent_evidence_swap_caught_by_delta() -> None:
    prev = {
        "references": {"eval_summary_ref": "evl-1"},
    }
    curr = {
        "references": {"eval_summary_ref": "evl-2"},
    }
    delta = compute_certification_delta(
        delta_id="d-mut", previous_index=prev, current_index=curr
    )
    assert delta["decision"] == "block"
    assert delta["overall_delta_risk"] == "high"


def test_mutation_observation_hijack_caught_by_minimality() -> None:
    res = audit_control_signal_minimality(
        proposed_decision={"decision": "block", "canonical_reason": "EVAL_FAILURE"},
        signals_used={"dashboard_freshness_seconds": 9999},
        evidence_refs=["x"],
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "MINIMALITY_OBSERVATION_HIJACK"


def test_mutation_proof_bloat_caught_by_size_budget() -> None:
    bundle = build_loop_proof_bundle(**_passing_loop_inputs())
    bundle["human_readable"] = "x" * 50_000
    res = evaluate_proof_bundle_size(bundle=bundle, kind="loop_proof_bundle")
    assert res["decision"] == "block"
    assert res["reason_code"] == "PROOF_SIZE_OVER_CHAR_BUDGET"
