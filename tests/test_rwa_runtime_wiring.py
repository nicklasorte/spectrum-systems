from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rwa_runtime_wiring import (
    VALIDATION_LADDER_ORDER,
    RuntimeWiringEngine,
    RuntimeWiringFailure,
    ThinPromptRequest,
    execute_rwa_final_autonomous_run,
    execute_rwa_minimal_prompt_flow,
    execute_rwa_red_team_rounds,
)


def test_rdx_tlc_bridge_and_ctx_injection() -> None:
    engine = RuntimeWiringEngine()
    plan = engine.compile_execution_ready_plan(
        ThinPromptRequest(
            prompt_id="prm-minimal",
            objective="runtime autonomous flow",
            requested_change_refs=["RWA-001"],
        )
    )
    assert plan["artifact_type"] == "rdx_tlc_execution_bridge_record"
    assert plan["status"] == "execution_ready"

    ctx = engine.inject_minimal_context(
        recipe={"scope": "runtime", "constraints": ["fail_closed"], "evidence_refs": ["registry"]},
        plan=plan,
    )
    assert ctx["artifact_type"] == "ctx_runtime_minimal_context_injection_result"
    assert ctx["status"] == "pass"


def test_ctx_injection_fails_closed_on_missing_recipe_fields() -> None:
    engine = RuntimeWiringEngine()
    plan = engine.compile_execution_ready_plan(
        ThinPromptRequest(prompt_id="prm-minimal", objective="obj", requested_change_refs=["RWA-001"])
    )
    with pytest.raises(RuntimeWiringFailure):
        engine.inject_minimal_context(recipe={"scope": "runtime"}, plan=plan)


def test_validation_ladder_order_is_enforced() -> None:
    engine = RuntimeWiringEngine()
    passed = engine.run_validation_ladder(executed_order=list(VALIDATION_LADDER_ORDER))
    assert passed["status"] == "pass"
    with pytest.raises(RuntimeWiringFailure):
        engine.run_validation_ladder(executed_order=["contracts", "registry_guard"])


def test_tlc_ril_fre_evl_con_obs_lin_rep_cde_path() -> None:
    flow = execute_rwa_minimal_prompt_flow()
    assert flow["reviews"]["review"]["artifact_type"] == "ril_runtime_review_execution_record"
    assert flow["reviews"]["red_team"]["artifact_type"] == "ril_runtime_red_team_execution_record"
    assert flow["fix_pack"]["artifact_type"] == "fre_runtime_fix_pack_compilation_record"
    assert flow["severity"]["artifact_type"] == "fre_runtime_fix_severity_enforcement_record"
    assert flow["obligations"]["artifact_type"] == "evl_runtime_exploit_to_eval_conversion_record"
    assert flow["eval_gate"]["status"] == "pass"
    assert flow["composition"]["status"] == "pass"
    assert flow["telemetry"]["trace"]["artifact_type"] == "obs_runtime_full_loop_trace_record"
    assert flow["telemetry"]["lineage"]["artifact_type"] == "lin_runtime_loop_lineage_report"
    assert flow["telemetry"]["replay"]["artifact_type"] == "rep_runtime_loop_replay_bundle"
    assert flow["cde"]["post_loop"]["artifact_type"] == "cde_runtime_post_loop_continuation_decision"
    assert flow["cde"]["post_loop"]["decision"] == "continue"


def test_cde_unresolved_mandatory_fix_gate_halts() -> None:
    engine = RuntimeWiringEngine()
    decisions = engine.cde_decide(
        eval_gate_status="pass",
        mandatory_fix_ids=["fix-rt-1"],
        resolved_fix_ids=set(),
        composition_status="pass",
    )
    assert decisions["post_loop"]["decision"] == "halt"
    assert decisions["unresolved_fix"]["halt"] is True


def test_mnt_recurring_behavior_is_runtime_active() -> None:
    flow = execute_rwa_minimal_prompt_flow()
    assert flow["maintain"]["trigger"]["artifact_type"] == "mnt_runtime_maintain_trigger_record"
    assert flow["maintain"]["trigger"]["triggered"] is True
    assert flow["maintain"]["expansion"]["artifact_type"] == "mnt_runtime_eval_expansion_record"
    assert flow["maintain"]["expansion"]["jobs"]


def test_red_team_rounds_execute_with_immediate_fix_and_rerun() -> None:
    rounds = execute_rwa_red_team_rounds()
    assert len(rounds) == 15
    for idx in range(0, len(rounds), 3):
        rt = rounds[idx]
        fx = rounds[idx + 1]
        rerun = rounds[idx + 2]
        assert rt["owner"] == "RIL"
        assert fx["owner"] == "FRE"
        assert fx["execution_path"] == ["FRE", "TPA", "SEL", "PQX"]
        assert rerun["artifact_type"] == "tlc_runtime_rerun_execution_record"
        assert rerun["reran_impacted_suites"] is True


def test_final_autonomous_run_and_full_rerun_report() -> None:
    final = execute_rwa_final_autonomous_run()
    assert final["artifact_type"] == "final_runtime_autonomous_run_simulation"
    assert final["status"] == "pass"
    assert final["full_rerun_report"]["artifact_type"] == "final_runtime_wiring_full_rerun_report"
    assert final["full_rerun_report"]["status"] == "pass"
