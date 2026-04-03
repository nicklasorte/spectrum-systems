from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema
from spectrum_systems.eval.registry.registry import enforce_required_evals, RequiredEvalMissingError
from spectrum_systems.eval.runners import build_regression_report, run_judge, run_pairwise_eval, summarize_slices
from spectrum_systems.eval.runners.judge_runner import JudgeOutputError
from spectrum_systems.intelligence.jobs import (
    build_drift_signal,
    build_trust_posture,
    detect_evidence_gaps,
    detect_override_hotspots,
)
from spectrum_systems.ai_adapter.structured_client import enforce_structured_response, StructuredOutputError
from spectrum_systems.pqx.steps.multi_pass_pipeline import run_multi_pass_pipeline
from spectrum_systems.context.bundles import ContextBuildError, build_context_bundle, detect_context_conflicts
from spectrum_systems.routing.policy import RoutingDecisionError, select_route
from spectrum_systems.tracing.explain_runs import explain_run_failure
from spectrum_systems.replay.trace_diff import diff_runs


def _validate(schema_name: str, payload: dict) -> None:
    Draft202012Validator(load_schema(schema_name)).validate(payload)


def test_required_eval_enforcement_fail_closed() -> None:
    entry = {"artifact_family": "working_paper", "required_eval_ids": ["eval.a", "eval.b"]}
    with pytest.raises(RequiredEvalMissingError):
        enforce_required_evals(entry, ["eval.a"])


def test_pairwise_and_regression_and_slice_summary() -> None:
    pairwise = run_pairwise_eval(
        {"route_key": "route.alpha", "model_id": "model1", "score": 0.8},
        {"route_key": "route.alpha", "model_id": "model2", "score": 0.9},
    )
    _validate("model_route_comparison_record", pairwise)

    summaries = summarize_slices(
        [
            {"slice_id": "s1", "status": "pass", "run_id": "run1"},
            {"slice_id": "s1", "status": "fail", "run_id": "run1"},
        ],
        coverage_run_id="run1",
    )
    _validate("eval_slice_summary", summaries[0])

    regression = build_regression_report(
        [{"case_id": "c1", "status": "pass"}],
        [{"case_id": "c1", "status": "fail"}],
        "base",
        "cand",
    )
    _validate("eval_regression_report", regression)
    assert regression["status"] == "regression_detected"


def test_judge_runner_strict_output() -> None:
    result = run_judge({"decision": "pass", "rationale": "ok", "confidence": 0.9}, {"judge_model": "m"})
    assert result["decision"] == "pass"
    with pytest.raises(JudgeOutputError):
        run_judge({"decision": "pass"}, {"judge_model": "m"})


def test_pulse_jobs_emit_schema_bound_artifacts() -> None:
    drift = build_drift_signal(signal_id="dsr-0000000000000001", artifact_family="routing", severity="high")
    _validate("drift_signal_record", drift)

    override = detect_override_hotspots([
        {"policy_key": "p1", "overridden": True},
        {"policy_key": "p1", "overridden": True},
    ])
    _validate("override_hotspot_report", override)

    evidence = detect_evidence_gaps([
        {"artifact_family": "routing", "has_evidence": False},
        {"artifact_family": "routing", "has_evidence": False},
    ])
    _validate("evidence_gap_hotspot_report", evidence)

    posture = build_trust_posture(["dsr-1"], degraded=True)
    _validate("trust_posture_snapshot", posture)


def test_structured_output_fail_closed() -> None:
    payload = {
        "artifact_type": "explain_run_report",
        "schema_version": "1.0.0",
        "report_id": "exr-0000000000000001",
        "run_id": "run-1",
        "failure_summary": "failed",
        "hotspots": ["step-a"],
    }
    wrapped = enforce_structured_response("explain_run_report", payload, {"path": "unit"})
    assert wrapped["guardrails"]["validated"] is True

    with pytest.raises(StructuredOutputError):
        enforce_structured_response("explain_run_report", {"artifact_type": "explain_run_report"}, {"path": "unit"})


def test_multi_pass_pipeline_emits_all_required_passes() -> None:
    def runner(pass_type: str, prior: dict) -> dict:
        return {
            "artifact_ref": f"artifact:{pass_type}",
            "trace_id": "trace-1",
            "input_ref": prior.get("artifact_ref", "input:seed"),
            "status": "ok",
        }

    outputs = run_multi_pass_pipeline({"artifact_ref": "input:seed"}, runner)
    assert [o["pass_type"] for o in outputs] == ["extract", "critique", "contradiction", "gap", "synthesis"]


def test_context_bundle_and_conflict_detection_fail_closed() -> None:
    recipe = {
        "artifact_type": "context_recipe_spec",
        "schema_version": "1.0.0",
        "recipe_id": "recipe.alpha",
        "recipe_version": "v1.0.0",
        "required_sources": ["a", "b"],
        "optional_sources": [],
    }
    _validate("context_recipe_spec", recipe)

    with pytest.raises(ContextBuildError):
        build_context_bundle(recipe, {"a": {"x": 1}}, bundle_id="cbr-0000000000000001")

    bundle = build_context_bundle(recipe, {"a": {"x": 1}, "b": {"x": 1}}, bundle_id="cbr-0000000000000001")
    _validate("context_bundle_record", bundle)

    conflict = detect_context_conflicts("a", "b", "field", "left", "right")
    assert conflict is not None
    _validate("context_conflict_record", conflict)


def test_deterministic_routing_decision_and_fail_closed_missing_decision() -> None:
    policy = {
        "artifact_type": "routing_policy",
        "schema_version": "1.1.0",
        "policy_id": "rp-top8",
        "created_at": "2026-01-01T00:00:00Z",
        "policy_scope": "ag_runtime",
        "policy_version": "v1.0.0",
        "model_catalog": ["model1", "model2"],
        "selection_constraints": {"max_cost_usd": 0.5, "max_latency_ms": 2000},
        "routes": [
            {
                "route_key": "route.a",
                "task_class": "analysis.task",
                "task_type": "analysis",
                "risk_class": "medium",
                "canary_eligible": True,
                "budget_class": "balanced",
                "prompt_selection": {"prompt_id": "prompt.a", "prompt_alias": "prod"},
                "model_selection": {"selected_model_id": "model1"},
            }
        ],
    }
    _validate("routing_policy", policy)

    candidates = {
        "artifact_type": "route_candidate_set",
        "schema_version": "1.0.0",
        "candidate_set_id": "rcs-0000000000000001",
        "task_type": "analysis",
        "candidates": [
            {"route_key": "route.a", "model_id": "model1", "estimated_cost": 0.2, "estimated_latency_ms": 500},
            {"route_key": "route.b", "model_id": "model2", "estimated_cost": 0.4, "estimated_latency_ms": 1500},
        ],
    }
    _validate("route_candidate_set", candidates)

    decision = select_route(policy, candidates, trace_id="trace-1", run_id="run-1")
    _validate("routing_decision_record", decision)

    with pytest.raises(RoutingDecisionError):
        select_route(
            policy,
            {
                **candidates,
                "candidates": [{"route_key": "x", "model_id": "model2", "estimated_cost": 9.9, "estimated_latency_ms": 9000}],
            },
            trace_id="trace-1",
            run_id="run-1",
        )


def test_explain_run_and_trace_diff() -> None:
    explain = explain_run_failure(
        "run-1",
        [
            {"step": "extract", "status": "ok"},
            {"step": "synthesis", "status": "failed", "message": "missing evidence"},
        ],
    )
    _validate("explain_run_report", explain)

    diff = diff_runs({"run_id": "a", "status": "ok", "x": 1}, {"run_id": "b", "status": "failed", "x": 2})
    _validate("trace_diff_report", diff)
    assert diff["diffs"]
