from __future__ import annotations

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.ai_governed_integration import (
    AIGovernanceError,
    GovernedAIRequest,
    build_lineage_bundle,
    cde_decide_continuation,
    cde_decide_escalation,
    compute_posture,
    enforce_context_preflight,
    enforce_registered_prompt,
    evaluate_ai_output,
    execute_red_team_rounds,
    tlx_dispatch,
)


def _request() -> GovernedAIRequest:
    return GovernedAIRequest(
        task_id="task.ai.summary",
        prompt_id="prompt.summary",
        prompt_version="1.0.0",
        context_bundle_id="ctxb-001",
        route={"provider": "mock", "model": "mock-1"},
        limits={"max_output_tokens": 400, "timeout_ms": 5000},
        trace={"trace_id": "trace-001", "run_id": "run-aig-001", "step_id": "AIG-001"},
    )


def test_tlx_requires_registered_prompt_and_context_and_eval_gate() -> None:
    request = _request()
    enforce_registered_prompt(request, {"prompt.summary": {"1.0.0"}})
    filter_result = enforce_context_preflight(
        {
            "bundle_id": "ctxb-001",
            "run_id": "run-aig-001",
            "approved": True,
            "relevance_pass": True,
            "token_count": 512,
            "token_limit": 2048,
        }
    )
    validate_artifact(filter_result, "ctx_ai_context_filter_result")

    dispatch, response = tlx_dispatch(
        request,
        {
            "structured_valid": True,
            "payload": {"summary": "governed"},
            "usage": {"prompt_tokens": 40, "completion_tokens": 70, "cost_usd": 0.01},
        },
    )
    validate_artifact(dispatch, "tlx_ai_adapter_dispatch_record")

    eval_result = evaluate_ai_output(response)
    validate_artifact(eval_result, "evl_ai_output_eval_result")

    bundle = build_lineage_bundle(request, response, eval_result)
    validate_artifact(bundle["lineage"], "lin_ai_call_lineage_record")
    validate_artifact(bundle["replay"], "rep_ai_replay_request_record")
    validate_artifact(bundle["observability"], "obs_ai_call_observability_record")


def test_direct_call_bypass_blocked_without_registered_prompt() -> None:
    request = _request()
    try:
        enforce_registered_prompt(request, {"other": {"1.0.0"}})
    except AIGovernanceError as exc:
        assert "unregistered_or_disallowed_prompt" in str(exc)
    else:
        raise AssertionError("expected fail-closed prompt registry enforcement")


def test_tlx_failure_classification_and_cde_authority() -> None:
    request = _request()
    dispatch, response = tlx_dispatch(
        request,
        {
            "structured_valid": False,
            "provider_error": None,
            "timed_out": False,
            "truncated": False,
            "payload": {},
            "usage": {"cost_usd": 0.02},
        },
    )
    assert dispatch["payload"]["failure_class"] == "schema_failure"

    eval_result = evaluate_ai_output(response)
    posture = compute_posture(
        usage_records=[{"cost_usd": 25.0}],
        failure_records=[{"failure_class": "schema_failure"}],
        queue_pressure=0.9,
    )
    for name, artifact in posture.items():
        validate_artifact(artifact, f"{name}_ai_{'cost_budget_posture' if name=='cap' else 'reliability_budget_posture' if name=='slo' else 'queue_pressure_record'}")

    decision = cde_decide_continuation(eval_result=eval_result, posture=posture, lineage_complete=True)
    escalation = cde_decide_escalation(failure_class="schema_failure", repeat_failures=2)
    validate_artifact(decision, "cde_ai_usage_continuation_decision")
    validate_artifact(escalation, "cde_ai_failure_escalation_decision")
    assert decision["status"] == "halt"
    assert escalation["status"] == "escalate"


def test_non_authoritative_assist_layer_contract_examples_validate() -> None:
    for name in (
        "prg_ai_model_routing_recommendation",
        "prg_ai_control_signal_bundle",
        "jdx_ai_judgment_candidate_record",
        "jdx_ai_contradiction_assist_record",
        "pol_ai_policy_candidate_record",
        "prx_ai_precedent_retrieval_record",
        "ail_ai_pattern_mining_record",
        "ail_ai_roadmap_candidate_record",
    ):
        validate_artifact(load_example(name), name)


def test_red_team_rounds_execute_with_immediate_fix_packs_and_regressions() -> None:
    rounds = execute_red_team_rounds()
    assert len(rounds) == 14
    for index in range(0, len(rounds), 2):
        red = rounds[index]
        fix = rounds[index + 1]
        assert red["artifact_type"].startswith("ril_ai_")
        assert fix["artifact_type"].startswith("fre_tpa_sel_pqx_ai_fix_pack_")
        validate_artifact(red, red["artifact_type"])
        validate_artifact(fix, fix["artifact_type"])
        for exploit in red["payload"]["exploit_codes"]:
            assert f"fixed:{exploit}" in fix["payload"]["exploit_codes"]


def test_final_integration_artifacts_validate() -> None:
    for name in (
        "final_ai_roadmap_integration_scenario_pack",
        "final_ai_failure_cascade_simulation",
        "final_ai_impacted_suite_rerun_report",
    ):
        validate_artifact(load_example(name), name)
