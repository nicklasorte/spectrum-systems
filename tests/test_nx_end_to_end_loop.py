"""NX-26: End-to-end adversarial loop coverage.

Runs through:
    execution → eval → control → enforcement → replay/lineage/observability/certification

with one passing path and one failing path. Validates that the full loop
fails closed when any stage degrades, and only allows promotion when every
stage produces ``allow``.
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.certification_prerequisites import (
    assert_certification_prerequisites,
)
from spectrum_systems.modules.lineage.lineage_enforcement import (
    assert_lineage_promotion_prerequisites,
    build_lineage_coverage_summary,
)
from spectrum_systems.modules.observability.failure_trace import build_failure_trace
from spectrum_systems.modules.replay.replay_support import (
    build_replay_coverage_summary,
    build_replay_record,
    classify_replay_mismatch,
)
from spectrum_systems.modules.runtime.context_admission_gate import admit_context_bundle
from spectrum_systems.modules.runtime.control_chain_invariants import verify_control_chain
from spectrum_systems.modules.runtime.eval_spine import evaluate_artifact_family
from spectrum_systems.modules.runtime.slo_budget_gate import evaluate_slo_budget_gate


_REGISTRY = {
    "artifact_type": "required_eval_registry",
    "registry_id": "RER-NX-E2E",
    "artifact_version": "1.0.0",
    "schema_version": "1.0.0",
    "standards_version": "1.9.8",
    "policy_reference": {"policy_id": "p1", "policy_version": "2026-04-27"},
    "mappings": [
        {
            "artifact_family": "nx_e2e_family",
            "required_evals": [
                {"eval_id": "schema_ok", "eval_family": "judgment_eval", "mandatory_for_progression": True},
                {"eval_id": "evidence_ok", "eval_family": "judgment_eval", "mandatory_for_progression": True},
            ],
        }
    ],
}


def _passing_results() -> list[dict]:
    return [
        {"eval_id": "schema_ok", "passed": True, "result_status": "pass"},
        {"eval_id": "evidence_ok", "passed": True, "result_status": "pass"},
    ]


def _ctx_bundle(stale: bool = False) -> dict:
    return {
        "preflight_passed": True,
        "admitted_candidates": [
            {
                "candidate_id": "c1",
                "role": "evidence",
                "trust_level": "trusted",
                "artifact_type": "context_evidence",
                "schema_version": "1.0.0",
                "provenance": {"source": "system_repo"},
                "expires_at": "2020-01-01T00:00:00Z" if stale else "2099-01-01T00:00:00Z",
                "topic": "spec",
                "assertion": "ok",
            }
        ],
    }


def _lineage_store() -> dict:
    return {
        "input-1": {
            "artifact_id": "input-1",
            "artifact_type": "input_bundle",
            "upstream_artifacts": [],
            "trace_id": "tE2E",
            "run_id": "rE2E",
        },
        "exec-1": {
            "artifact_id": "exec-1",
            "artifact_type": "pqx_slice_execution_record",
            "upstream_artifacts": ["input-1"],
            "trace_id": "tE2E",
            "run_id": "rE2E",
        },
        "out-1": {
            "artifact_id": "out-1",
            "artifact_type": "eval_summary",
            "upstream_artifacts": ["exec-1"],
            "trace_id": "tE2E",
            "run_id": "rE2E",
        },
    }


def test_e2e_passing_path_allows_promotion() -> None:
    # 1. Context admission
    ctx = admit_context_bundle(bundle=_ctx_bundle())
    assert ctx["decision"] == "allow"

    # 2. Execution + Output (synthetic)
    execution_record = {
        "artifact_id": "exec-1",
        "artifact_type": "pqx_slice_execution_record",
        "status": "ok",
        "trace_id": "tE2E",
        "run_id": "rE2E",
    }
    output_artifact = {
        "artifact_id": "out-1",
        "artifact_type": "eval_summary",
        "trace_id": "tE2E",
        "run_id": "rE2E",
    }

    # 3. Eval spine
    eval_outcome = evaluate_artifact_family(
        artifact_family="nx_e2e_family",
        eval_definitions=["schema_ok", "evidence_ok"],
        eval_results=_passing_results(),
        trace_id="tE2E",
        run_id="rE2E",
        created_at="2026-04-27T00:00:00Z",
        registry=_REGISTRY,
    )
    assert eval_outcome["control_handoff"]["decision"] == "allow"

    # 4. Control chain
    eval_summary = {
        "artifact_type": "eval_slice_summary",
        "artifact_id": "evl-1",
        "trace_id": "tE2E",
        "status": "healthy",
    }
    cde_decision = {
        "artifact_type": "control_decision",
        "decision_id": "cde-1",
        "decision": "allow",
        "input_eval_summary_reference": "evl-1",
        "trace_id": "tE2E",
    }
    sel_action = {
        "artifact_type": "enforcement_action",
        "enforcement_id": "sel-1",
        "enforcement_action": "allow_execution",
        "input_decision_reference": "cde-1",
        "trace_id": "tE2E",
    }
    cc = verify_control_chain(
        eval_summary=eval_summary,
        control_decision=cde_decision,
        enforcement_action=sel_action,
    )
    assert cc["decision"] == "allow"

    # 5. Replay
    rec_orig = build_replay_record(
        replay_id="rpl-orig",
        original_run_id="rE2E",
        trace_id="tE2E",
        input_payload={"x": 1},
        output_payload={"y": 1},
        artifact_type="eval_summary",
    )
    rec_replay = build_replay_record(
        replay_id="rpl-1",
        original_run_id="rE2E",
        trace_id="tE2E",
        input_payload={"x": 1},
        output_payload={"y": 1},
        artifact_type="eval_summary",
    )
    replay_classification = classify_replay_mismatch(original=rec_orig, replayed=rec_replay)
    replay_summary = build_replay_coverage_summary([replay_classification])
    assert replay_summary["status"] == "healthy"

    # 6. Lineage
    store = _lineage_store()
    lineage_per_out = assert_lineage_promotion_prerequisites(
        artifact=store["out-1"], artifact_store=store
    )
    assert lineage_per_out["decision"] == "allow"
    lineage_summary = build_lineage_coverage_summary(
        artifacts=list(store.values()), artifact_store=store
    )
    assert lineage_summary["status"] == "healthy"

    # 7. SLO budget
    slo = evaluate_slo_budget_gate(
        posture={
            "trace_id": "tE2E",
            "budget_remaining": 0.9,
            "drift_rate": 0.0,
            "override_rate": 0.0,
            "eval_pass_rate": 0.99,
            "replay_mismatch_rate": 0.0,
        }
    )
    assert slo["decision"] == "allow"

    # 8. Observability failure trace
    trace = build_failure_trace(
        trace_id="tE2E",
        execution_record=execution_record,
        output_artifact=output_artifact,
        eval_result=eval_summary,
        control_decision=cde_decision,
        enforcement_action=sel_action,
    )
    assert trace["overall_status"] == "ok"

    # 9. Certification prerequisites
    cert = assert_certification_prerequisites(
        eval_summary=eval_summary,
        lineage_summary=lineage_summary,
        replay_summary=replay_summary,
        control_decision=cde_decision,
        enforcement_record=sel_action,
        registry_violations=[],
    )
    assert cert["decision"] == "allow"
    assert cert["reason_code"] == "CERT_OK"


def test_e2e_failing_path_blocks_at_first_failure_and_propagates() -> None:
    """Inject a failure at the eval stage and ensure the entire downstream
    chain blocks promotion (with a clear failure trace)."""
    # 1. Context admission still passes
    ctx = admit_context_bundle(bundle=_ctx_bundle())
    assert ctx["decision"] == "allow"

    execution_record = {
        "artifact_id": "exec-1",
        "artifact_type": "pqx_slice_execution_record",
        "status": "ok",
        "trace_id": "tE2E",
        "run_id": "rE2E",
    }
    output_artifact = {
        "artifact_id": "out-1",
        "artifact_type": "eval_summary",
        "trace_id": "tE2E",
        "run_id": "rE2E",
    }

    # 2. Eval spine FAILS — required eval result missing
    eval_outcome = evaluate_artifact_family(
        artifact_family="nx_e2e_family",
        eval_definitions=["schema_ok", "evidence_ok"],
        eval_results=[{"eval_id": "schema_ok", "passed": True, "result_status": "pass"}],
        trace_id="tE2E",
        run_id="rE2E",
        created_at="2026-04-27T00:00:00Z",
        registry=_REGISTRY,
    )
    assert eval_outcome["control_handoff"]["decision"] == "block"
    assert eval_outcome["control_handoff"]["reason_code"] == "missing_required_eval_result"

    # 3. Control chain — CDE rightfully blocks
    eval_summary = {
        "artifact_type": "eval_slice_summary",
        "artifact_id": "evl-1",
        "trace_id": "tE2E",
        "status": "blocked",
        "block_reason": "missing_required_eval_result",
    }
    cde_decision = {
        "artifact_type": "control_decision",
        "decision_id": "cde-1",
        "decision": "block",
        "input_eval_summary_reference": "evl-1",
        "trace_id": "tE2E",
    }
    sel_action = {
        "artifact_type": "enforcement_action",
        "enforcement_id": "sel-1",
        "enforcement_action": "deny_execution",
        "input_decision_reference": "cde-1",
        "trace_id": "tE2E",
    }
    cc = verify_control_chain(
        eval_summary=eval_summary,
        control_decision=cde_decision,
        enforcement_action=sel_action,
    )
    # Control chain itself is internally consistent (block + deny match) but
    # the certification prerequisite must still block because eval failed.
    assert cc["decision"] == "allow", cc

    # 4. Failure trace surfaces eval as the failed stage
    trace = build_failure_trace(
        trace_id="tE2E",
        execution_record=execution_record,
        output_artifact=output_artifact,
        eval_result=eval_summary,
        control_decision=cde_decision,
        enforcement_action=sel_action,
    )
    assert trace["overall_status"] == "failed"
    assert trace["failed_stage"] == "eval"
    assert trace["owning_system_for_failed_stage"] == "EVL"

    # 5. Certification prerequisites refuse promotion
    cert = assert_certification_prerequisites(
        eval_summary=eval_summary,
        lineage_summary={"status": "healthy"},
        replay_summary={"status": "healthy"},
        control_decision=cde_decision,
        enforcement_record=sel_action,
        registry_violations=[],
    )
    assert cert["decision"] == "block"
    assert cert["reason_code"] in {
        "CERT_MISSING_EVAL_PASS",
        "CERT_MISSING_CONTROL_DECISION",
    }


def test_e2e_failing_path_with_replay_mismatch_blocks_certification() -> None:
    """Even with all evals passing, a replay mismatch must block certification."""
    eval_outcome = evaluate_artifact_family(
        artifact_family="nx_e2e_family",
        eval_definitions=["schema_ok", "evidence_ok"],
        eval_results=_passing_results(),
        trace_id="tE2E",
        run_id="rE2E",
        created_at="2026-04-27T00:00:00Z",
        registry=_REGISTRY,
    )
    assert eval_outcome["control_handoff"]["decision"] == "allow"

    eval_summary = {
        "artifact_type": "eval_slice_summary",
        "artifact_id": "evl-1",
        "trace_id": "tE2E",
        "status": "healthy",
    }
    cde_decision = {
        "decision_id": "cde-1",
        "decision": "allow",
        "input_eval_summary_reference": "evl-1",
        "trace_id": "tE2E",
    }
    sel_action = {
        "enforcement_id": "sel-1",
        "enforcement_action": "allow_execution",
        "input_decision_reference": "cde-1",
        "trace_id": "tE2E",
    }
    rec_orig = build_replay_record(
        replay_id="rpl-orig",
        original_run_id="rE2E",
        trace_id="tE2E",
        input_payload={"x": 1},
        output_payload={"y": 1},
        artifact_type="eval_summary",
    )
    # Replay drift on output
    rec_replay = build_replay_record(
        replay_id="rpl-1",
        original_run_id="rE2E",
        trace_id="tE2E",
        input_payload={"x": 1},
        output_payload={"y": 999},
        artifact_type="eval_summary",
    )
    replay_summary = build_replay_coverage_summary(
        [classify_replay_mismatch(original=rec_orig, replayed=rec_replay)]
    )
    assert replay_summary["status"] == "blocked"

    cert = assert_certification_prerequisites(
        eval_summary=eval_summary,
        lineage_summary={"status": "healthy"},
        replay_summary=replay_summary,
        control_decision=cde_decision,
        enforcement_record=sel_action,
        registry_violations=[],
    )
    assert cert["decision"] == "block"
    assert cert["reason_code"] == "CERT_MISSING_REPLAY_READINESS"


def test_e2e_failing_path_with_stale_context_blocks_admission() -> None:
    ctx = admit_context_bundle(bundle=_ctx_bundle(stale=True))
    assert ctx["decision"] == "block"
    assert ctx["reason_code"] == "CTX_STALE_TTL"
