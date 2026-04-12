from __future__ import annotations

import copy
import json
import subprocess

import pytest

from spectrum_systems.modules.runtime.governed_repair_loop_execution import (
    GovernedRepairLoopExecutionError,
    run_contract_preflight_production,
    run_preflight_remediation_loop,
)
from spectrum_systems.modules.runtime.system_enforcement_layer import enforce_preflight_remediation_boundaries


BASE_PREFLIGHT_BLOCK = {
    "artifact_type": "contract_preflight_result_artifact",
    "schema_version": "1.2.0",
    "preflight_status": "failed",
    "changed_contracts": ["contracts/schemas/a.schema.json"],
    "impacted_producers": ["scripts/run_contract_preflight.py"],
    "impacted_fixtures": [],
    "impacted_consumers": ["tests/test_contract_preflight.py"],
    "masking_detected": False,
    "recommended_repair_area": ["spectrum_systems/modules/runtime/top_level_conductor.py"],
    "report_paths": {
        "json_report_path": "outputs/contract_preflight/contract_preflight_report.json",
        "markdown_report_path": "outputs/contract_preflight/contract_preflight_report.md",
    },
    "generated_at": "2026-04-12T00:00:00Z",
    "control_surface_gap_status": "ok",
    "control_surface_gap_result_ref": "outputs/contract_preflight/control_surface_gap_result.json",
    "pqx_gap_work_items_ref": "outputs/contract_preflight/control_surface_gap_pqx_work_items.json",
    "control_surface_gap_blocking": True,
    "pqx_required_context_enforcement": {
        "classification": "governed_pqx_required",
        "execution_context": "pqx_governed",
        "wrapper_present": True,
        "wrapper_context_valid": True,
        "authority_context_valid": True,
        "authority_state": "authoritative_governed_pqx",
        "requires_pqx_execution": True,
        "enforcement_decision": "allow",
        "status": "allow",
        "blocking_reasons": [],
    },
    "control_signal": {
        "strategy_gate_decision": "BLOCK",
        "rationale": "critical contract drift detected",
        "changed_path_detection_mode": "base_head_diff",
        "degraded_detection": False,
    },
    "trace": {
        "producer": "scripts/run_contract_preflight.py",
        "policy_version": "1.0.0",
        "refs_attempted": ["origin/main..HEAD"],
        "fallback_used": False,
        "evaluation_mode": "full",
        "skip_reason": None,
        "changed_paths_resolved": ["contracts/schemas/a.schema.json"],
        "evaluated_surfaces": ["contract_surface"],
        "provenance_ref": "contracts/standards-manifest.json",
    },
}

BASE_LINEAGE = {
    "request_ref": "normalized_execution_request:req-123",
    "admission_ref": "build_admission_record:adm-123",
    "tlc_handoff_ref": "tlc_handoff_record:handoff-123",
    "trace_id": "trace-preflight-123",
}


def _rerun_allow() -> dict[str, object]:
    payload = copy.deepcopy(BASE_PREFLIGHT_BLOCK)
    payload["preflight_status"] = "passed"
    payload["control_signal"]["strategy_gate_decision"] = "ALLOW"
    payload["control_signal"]["rationale"] = "post-repair rerun clean"
    return payload


def test_preflight_block_bridge_emits_canonical_packet_and_candidate() -> None:
    result = run_preflight_remediation_loop(
        preflight_artifact=copy.deepcopy(BASE_PREFLIGHT_BLOCK),
        admission_lineage=copy.deepcopy(BASE_LINEAGE),
        batch_id="PF-U1",
        umbrella_id="PF-B1",
        run_id="run-1",
        trace_id="trace-preflight-123",
        retry_budget=3,
        complexity_score=2,
        risk_level="medium",
        contract_preflight_runner=_rerun_allow,
    )

    trace = result["trace"]
    assert trace["packet"]["artifact_type"] == "execution_failure_packet"
    assert trace["candidate"]["artifact_type"] == "bounded_repair_candidate_artifact"
    assert trace["decision"]["owner"] == "CDE"
    assert trace["gating_input"]["artifact_type"] == "tpa_repair_gating_input"
    assert trace["terminal"]["owner"] == "CDE"
    assert trace["terminal"]["terminal_classification"] == "pass_continue"
    assert trace["ril_detection"]["authority_state"] == "non_authoritative"
    assert trace["prg_recommendation"]["authority_state"] == "non_authoritative"
    assert result["status"] == "completed"


def test_non_blocking_preflight_is_rejected_from_failure_bridge() -> None:
    artifact = copy.deepcopy(BASE_PREFLIGHT_BLOCK)
    artifact["control_signal"]["strategy_gate_decision"] = "ALLOW"
    artifact["preflight_status"] = "passed"
    with pytest.raises(GovernedRepairLoopExecutionError, match="BLOCK/FREEZE"):
        run_preflight_remediation_loop(
            preflight_artifact=artifact,
            admission_lineage=copy.deepcopy(BASE_LINEAGE),
            batch_id="PF-U1",
            umbrella_id="PF-B1",
            run_id="run-1",
            trace_id="trace-preflight-123",
            retry_budget=3,
            complexity_score=2,
            risk_level="medium",
            contract_preflight_runner=_rerun_allow,
        )


def test_missing_lineage_fails_closed() -> None:
    lineage = copy.deepcopy(BASE_LINEAGE)
    lineage.pop("admission_ref")
    with pytest.raises(GovernedRepairLoopExecutionError, match="admission_lineage.admission_ref"):
        run_preflight_remediation_loop(
            preflight_artifact=copy.deepcopy(BASE_PREFLIGHT_BLOCK),
            admission_lineage=lineage,
            batch_id="PF-U1",
            umbrella_id="PF-B1",
            run_id="run-1",
            trace_id="trace-preflight-123",
            retry_budget=3,
            complexity_score=2,
            risk_level="medium",
            contract_preflight_runner=_rerun_allow,
        )


def test_retry_budget_exhaustion_is_blocked_by_sel() -> None:
    result = run_preflight_remediation_loop(
        preflight_artifact=copy.deepcopy(BASE_PREFLIGHT_BLOCK),
        admission_lineage=copy.deepcopy(BASE_LINEAGE),
        batch_id="PF-U1",
        umbrella_id="PF-B2",
        run_id="run-1",
        trace_id="trace-preflight-123",
        retry_budget=1,
        complexity_score=2,
        risk_level="medium",
        contract_preflight_runner=_rerun_allow,
    )
    assert result["status"] == "blocked"
    assert result["stop_reason"] == "sel_block"


def test_promotion_guard_blocks_missing_rerun_evidence_and_missing_authority() -> None:
    blocked = enforce_preflight_remediation_boundaries(
        remediation_context={
            "lineage": copy.deepcopy(BASE_LINEAGE),
            "failure_packet": {"artifact_type": "execution_failure_packet"},
            "repair_candidate": {"artifact_type": "bounded_repair_candidate_artifact"},
            "continuation_decision": {"owner": "CDE"},
            "continuation_input": {"issued_at": "2026-04-12T00:00:00Z", "freshness_window_seconds": 1800},
            "gating_input": {"artifact_type": "tpa_repair_gating_input"},
            "retry_budget_remaining": 1,
            "approved_scope_refs": ["a"],
            "execution_scope_refs": ["a", "b"],
            "rerun_preflight_result": {"artifact_type": "contract_preflight_result_artifact"},
            "diagnosis_artifact": {"artifact_type": "other"},
            "terminal_classification": {"owner": "TLC"},
        }
    )
    assert blocked["enforcement_status"] == "block"
    messages = "\n".join(row["message"] for row in blocked["violations"])
    assert "beyond TPA-approved" in messages
    assert "requires FRE diagnosis artifact" in messages
    assert "requires CDE terminal classification" in messages


def test_bounded_retry_classification_is_deterministic_when_rerun_still_blocked() -> None:
    def _rerun_block() -> dict[str, object]:
        return copy.deepcopy(BASE_PREFLIGHT_BLOCK)

    result = run_preflight_remediation_loop(
        preflight_artifact=copy.deepcopy(BASE_PREFLIGHT_BLOCK),
        admission_lineage=copy.deepcopy(BASE_LINEAGE),
        batch_id="PF-U2",
        umbrella_id="PF-B4",
        run_id="run-2",
        trace_id="trace-preflight-123",
        retry_budget=4,
        complexity_score=1,
        risk_level="low",
        contract_preflight_runner=_rerun_block,
        allow_ambiguous_retry=True,
    )
    assert result["trace"]["terminal"]["terminal_classification"] == "bounded_retry_allowed"


def test_ambiguous_rerun_state_blocks_by_default() -> None:
    def _rerun_ambiguous() -> dict[str, object]:
        payload = copy.deepcopy(BASE_PREFLIGHT_BLOCK)
        payload["preflight_status"] = "unknown"
        payload["control_signal"]["strategy_gate_decision"] = "WARN"
        return payload

    result = run_preflight_remediation_loop(
        preflight_artifact=copy.deepcopy(BASE_PREFLIGHT_BLOCK),
        admission_lineage=copy.deepcopy(BASE_LINEAGE),
        batch_id="PF-U3",
        umbrella_id="PF-B5",
        run_id="run-3",
        trace_id="trace-preflight-123",
        retry_budget=3,
        complexity_score=2,
        risk_level="medium",
        contract_preflight_runner=_rerun_ambiguous,
    )
    assert result["status"] == "blocked"
    assert result["trace"]["terminal"]["terminal_classification"] == "ambiguous_block"


def test_production_preflight_runner_wires_real_script_path(tmp_path, monkeypatch) -> None:
    output_dir = tmp_path / "preflight"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "contract_preflight_result_artifact.json"
    artifact = copy.deepcopy(BASE_PREFLIGHT_BLOCK)
    artifact["preflight_status"] = "passed"
    artifact["control_signal"]["strategy_gate_decision"] = "ALLOW"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    captured: dict[str, object] = {}

    def _fake_run(command, cwd, capture_output, text, check):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    result = run_contract_preflight_production(
        trace_id="trace-preflight-123",
        changed_paths=["contracts/schemas/a.schema.json"],
        output_dir=output_dir,
    )
    assert "scripts/run_contract_preflight.py" in " ".join(captured["command"])
    assert result["_execution_record"]["runner_identity"]["invocation_mode"] == "production"
    assert result["_execution_record"]["artifact_digest"]


def test_missing_execution_record_blocks_promotion_guard() -> None:
    result = run_preflight_remediation_loop(
        preflight_artifact=copy.deepcopy(BASE_PREFLIGHT_BLOCK),
        admission_lineage=copy.deepcopy(BASE_LINEAGE),
        batch_id="PF-U4",
        umbrella_id="PF-B6",
        run_id="run-4",
        trace_id="trace-preflight-123",
        retry_budget=3,
        complexity_score=2,
        risk_level="medium",
        contract_preflight_runner=_rerun_allow,
    )
    assert result["trace"]["rerun_execution_record"]["artifact_type"] == "preflight_execution_record"
    assert result["trace"]["promotion_guard"]["enforcement_status"] == "allow"


def test_stale_tpa_gating_input_fails_closed() -> None:
    blocked = enforce_preflight_remediation_boundaries(
        remediation_context={
            "lineage": copy.deepcopy(BASE_LINEAGE),
            "failure_packet": {"artifact_type": "execution_failure_packet", "a": 1},
            "repair_candidate": {"artifact_type": "bounded_repair_candidate_artifact", "b": 2},
            "continuation_decision": {"owner": "CDE"},
            "continuation_input": {
                "failure_packet_digest": "deadbeef",
                "repair_candidate_digest": "deadbeef",
                "issued_at": "1970-01-01T00:00:00Z",
                "freshness_window_seconds": 1,
            },
            "gating_input": {
                "approved_scope_digest": "mismatch",
                "issued_at": "1970-01-01T00:00:00Z",
                "freshness_window_seconds": 1,
            },
            "retry_budget_remaining": 1,
            "approved_scope_refs": ["a"],
            "execution_scope_refs": ["a"],
        }
    )
    assert blocked["enforcement_status"] == "block"
    messages = "\n".join(row["message"] for row in blocked["violations"])
    assert "stale" in messages
    assert "digest mismatch" in messages
