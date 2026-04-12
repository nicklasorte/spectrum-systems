from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.nx_governed_intelligence import (
    JudgmentPolicyRegistry,
    NXGovernedIntelligenceError,
    PromptTaskRouteRegistry,
    aggregate_multi_run,
    build_artifact_intelligence_index,
    build_artifact_intelligence_report,
    build_explainability_artifact,
    build_feedback_flywheel_artifacts,
    build_judgment_record,
    compute_trust_score,
    evaluate_autonomy_expansion_gate,
    evolve_policy_candidates,
    fuse_signals,
    mine_patterns,
    query_recurring_failure_motifs,
    require_judgment_eval_pass,
    retrieve_precedents,
    run_advanced_certification_gate,
    run_judgment_eval_suite,
    simulate_scenarios,
    validate_cross_system_consistency,
)


def _artifact_rows() -> list[dict[str, object]]:
    return [
        {
            "artifact_id": "a-002",
            "artifact_type": "enforcement_result",
            "schema_version": "1.0.0",
            "trace_id": "t-1",
            "span_id": "s-1",
            "run_id": "r-1",
            "policy_version": "p-1",
            "decision_outcome": "blocked",
            "reason_codes": ["policy_conflict", "override", "stale_artifact"],
            "blocker_class": "policy",
            "eval_slice": "judgment",
            "route_version": "route-1",
            "prompt_version": "prompt-1",
            "time_window": "2026-04",
        },
        {
            "artifact_id": "a-001",
            "artifact_type": "enforcement_result",
            "schema_version": "1.0.0",
            "trace_id": "t-1",
            "span_id": "s-2",
            "run_id": "r-2",
            "policy_version": "p-2",
            "decision_outcome": "promotion_blocked",
            "reason_codes": ["override"],
            "blocker_class": "promotion_guard",
            "eval_slice": "promotion",
            "route_version": "route-2",
            "prompt_version": "prompt-2",
            "time_window": "2026-04",
        },
        {
            "artifact_id": "a-003",
            "artifact_type": "eval_result",
            "schema_version": "1.1.0",
            "trace_id": "t-2",
            "span_id": "s-3",
            "run_id": "r-2",
            "policy_version": "p-1",
            "decision_outcome": "failed",
            "reason_codes": ["policy_conflict"],
            "blocker_class": "policy",
            "eval_slice": "judgment",
            "route_version": "route-1",
            "prompt_version": "prompt-1",
            "time_window": "2026-04",
        },
    ]


def test_artifact_index_and_queries_are_deterministic() -> None:
    idx1 = build_artifact_intelligence_index(_artifact_rows())
    idx2 = build_artifact_intelligence_index(list(reversed(_artifact_rows())))
    assert idx1 == idx2

    report = build_artifact_intelligence_report(idx1)
    assert report["authority_scope"] == "non_authoritative"
    assert report["top_blockers"][0] == {"blocker_class": "policy", "count": 2}
    motifs = query_recurring_failure_motifs(idx1)
    assert motifs == [{"blocker_class": "policy", "eval_slice": "judgment", "count": 2}]


def test_judgment_record_structure_and_eval_enforcement() -> None:
    judgment = build_judgment_record(
        {
            "question_under_judgment": "Should promotion continue?",
            "candidate_outcomes": ["promote", "hold"],
            "selected_outcome": "promote",
            "evidence_refs": ["e-1"],
            "claims_considered": ["claim-a"],
            "rules_applied": ["rule-1"],
            "assumptions": ["stable inputs"],
            "alternatives_considered": ["hold"],
            "uncertainties": ["latency drift"],
            "decision_change_conditions": ["replay fails"],
            "precedent_refs": ["j-1"],
            "rationale_summary": "Evidence satisfies policy.",
        }
    )
    assert judgment["authority_scope"] == "non_authoritative"

    summary = run_judgment_eval_suite(judgment, prior_selected_outcome="promote")
    require_judgment_eval_pass(
        summary,
        [
            "evidence_coverage",
            "contradiction_detection",
            "policy_alignment",
            "uncertainty_calibration",
            "replay_consistency",
            "longitudinal_calibration",
        ],
    )

    with pytest.raises(NXGovernedIntelligenceError):
        require_judgment_eval_pass({"results": {"evidence_coverage": False}}, ["evidence_coverage"])


def test_judgment_policy_registry_stays_non_authoritative() -> None:
    registry = JudgmentPolicyRegistry()
    policy = registry.register_policy(
        {
            "policy_id": "jp-1",
            "version": "1.0.0",
            "state": "draft",
            "scope": "artifact_release",
            "required_inputs": ["judgment_eval_summary"],
            "decision_table": [{"when": "evals_pass", "then": "allow_candidate"}],
            "override_policy": "manual_override_only",
            "provenance": "prg_candidate",
        }
    )
    assert policy["authority_scope"] == "non_authoritative"
    registry.transition("jp-1", "1.0.0", "canary")
    app = registry.build_application_request("jp-1", "1.0.0")
    assert app["requires_tpa_authority"] is True


def test_precedent_retrieval_is_deterministic_and_recorded() -> None:
    records = [
        {"record_id": "j-2", "question_under_judgment": "promotion risk", "rationale_summary": "hold promotion"},
        {"record_id": "j-1", "question_under_judgment": "promotion risk", "rationale_summary": "promote"},
    ]
    out1 = retrieve_precedents(query="promotion risk", records=records, method="token_overlap", method_version="1", top_k=2, threshold=0.1)
    out2 = retrieve_precedents(query="promotion risk", records=list(reversed(records)), method="token_overlap", method_version="1", top_k=2, threshold=0.1)
    assert out1 == out2
    assert out1["selected_scores"][0]["record_id"] == "j-1"


def test_signal_fusion_aggregation_pattern_and_consistency() -> None:
    fused = fuse_signals(
        {
            "preflight": {"ok": True},
            "eval_summary": {"pass_rate": 0.8},
            "runtime_observability": {"latency": 120},
            "judgment_eval": {"all_required_passed": True},
            "replay_drift": {"drift": False},
            "certification_state": {"certified": True},
        }
    )
    assert fused["authority_scope"] == "preparatory_non_authoritative"

    agg = aggregate_multi_run(
        [
            {"status": "pass", "repair_outcome": "fixed", "blocker_class": "none", "latency_ms": 100, "drift_detected": False, "promotion_blocked": False},
            {"status": "fail", "repair_outcome": "partial", "blocker_class": "policy", "latency_ms": 200, "drift_detected": True, "promotion_blocked": True},
        ]
    )
    assert agg["run_count"] == 2

    pattern = mine_patterns(
        [
            {"category": "failure", "motif": "policy_conflict"},
            {"category": "failure", "motif": "policy_conflict"},
        ]
    )
    assert pattern["authority_scope"] == "recommendation_only"

    consistency = validate_cross_system_consistency(
        [
            {"policy_version": "p1", "judgment_outcome": "allow", "certification_status": "passed", "promotion_path": "A", "replay_outcome": "match"},
            {"policy_version": "p2", "judgment_outcome": "allow", "certification_status": "passed", "promotion_path": "A", "replay_outcome": "match"},
        ]
    )
    assert consistency["divergence_detected"] is True


def test_policy_evolution_and_simulation_non_authoritative() -> None:
    pattern = mine_patterns(
        [
            {"category": "override", "motif": "manual_override"},
            {"category": "override", "motif": "manual_override"},
        ]
    )
    candidates = evolve_policy_candidates(pattern_report=pattern, overrides=[{"trace_id": "t-1"}], precedents=[{"record_id": "j-1"}])
    assert candidates["authority_scope"] == "recommendation_only"
    assert all(c["state"] == "draft" for c in candidates["candidates"])

    sim = simulate_scenarios([
        {"change_id": "c-2", "change_type": "policy", "magnitude": 0.4, "confidence": 0.5},
        {"change_id": "c-1", "change_type": "route", "magnitude": 0.2, "confidence": 1.0},
    ])
    assert sim["requires_authority_consumer"] is True


def test_explainability_trust_flywheel_and_registries() -> None:
    explain = build_explainability_artifact(
        {
            "trace": "trace-1",
            "input_artifacts": ["a-1"],
            "eval_results": ["e-1"],
            "judgment_records": ["j-1"],
            "policy_refs": ["p-1"],
            "control_decisions": ["cde:hold"],
            "enforcement_actions": ["sel:block"],
        }
    )
    assert "trace-1" in explain["human_readable_summary"]

    trust = compute_trust_score(
        {
            "eval_pass_rate": 0.9,
            "replay_consistency": 1.0,
            "drift": 0.1,
            "judgment_calibration": 0.8,
            "certification": 1.0,
            "blocker_trend": 0.2,
        }
    )
    assert trust["authority_scope"] == "recommendation_only"

    flywheel = build_feedback_flywheel_artifacts(
        failure={"failure_id": "f-1"},
        eval_summary={"artifact_type": "judgment_eval_summary"},
        pattern_report={"artifact_type": "pattern_mining_recommendation"},
        policy_candidates={"artifact_type": "policy_evolution_candidate_set", "candidates": [{"state": "draft"}]},
        activation_outcome={"state": "canary"},
    )
    assert flywheel["chain"]["failure_to_eval"]["failure_id"] == "f-1"

    registry = PromptTaskRouteRegistry()
    registry.register_task("t", "1.0.0", {"rollout": "active"})
    registry.register_prompt("p", "2.0.0", {"policy_version": "p-1"})
    registry.register_route("r", "1.2.0", {"model": "gpt"})
    resolved = registry.resolve(task_ref="t@1.0.0", prompt_ref="p@2.0.0", route_ref="r@1.2.0")
    assert resolved["task"]["version"] == "1.0.0"


def test_advanced_certification_and_autonomy_gate_block_without_authority() -> None:
    cert = run_advanced_certification_gate(
        {
            "backward_compatibility": True,
            "replay_integrity": True,
            "failure_injection": False,
            "cost_latency_guard": True,
            "control_loop_enforcement": True,
            "stateless_isolation": True,
        }
    )
    assert cert["blocked"] is True
    assert "failure_injection" in cert["failing_evidence"]

    gate = evaluate_autonomy_expansion_gate(
        readiness={"eligible": True, "recommendation_only": True},
        authority_inputs={"cde_authorized": False},
    )
    assert gate["eligible"] is False
    assert "missing_cde_authority" in gate["blocked_reasons"]

from spectrum_systems.modules.runtime.nx_governed_system import (
    NXGovernedSystemError,
    resolve_nx_contract,
    validate_nx_artifact,
)


def _with_trace(payload: dict[str, object]) -> dict[str, object]:
    out = dict(payload)
    out.setdefault("schema_version", "1.0.0")
    out.setdefault("trace_id", "trace-nx-001")
    if out.get("artifact_type") != "artifact_intelligence_index":
        out.setdefault("lineage", {"trace_id": "trace-nx-001", "producer": "RIL"})
    return out


def test_nx_runtime_outputs_validate_against_published_contracts() -> None:
    index = _with_trace(build_artifact_intelligence_index(_artifact_rows()))
    report = _with_trace(build_artifact_intelligence_report(index))
    fused = _with_trace(
        fuse_signals(
            {
                "preflight": {"ok": True},
                "eval_summary": {"pass_rate": 0.9},
                "runtime_observability": {"latency": 100},
                "judgment_eval": {"all_required_passed": True},
                "replay_drift": {"drift": False},
                "certification_state": {"certified": True},
            }
        )
    )
    aggregate = _with_trace(
        aggregate_multi_run(
            [
                {"status": "pass", "repair_outcome": "fixed", "blocker_class": "none", "latency_ms": 100, "drift_detected": False, "promotion_blocked": False}
            ]
        )
    )
    pattern = _with_trace(mine_patterns([{"category": "failure", "motif": "policy_conflict"}, {"category": "failure", "motif": "policy_conflict"}]))
    explain = _with_trace(
        build_explainability_artifact(
            {
                "trace": "trace-1",
                "input_artifacts": ["a-1"],
                "eval_results": ["e-1"],
                "judgment_records": ["j-1"],
                "policy_refs": ["p-1"],
                "control_decisions": ["cde:hold"],
                "enforcement_actions": ["sel:block"],
            }
        )
    )
    trust = _with_trace(
        compute_trust_score(
            {
                "eval_pass_rate": 0.9,
                "replay_consistency": 1.0,
                "drift": 0.1,
                "judgment_calibration": 0.8,
                "certification": 1.0,
                "blocker_trend": 0.2,
            }
        )
    )
    candidates = _with_trace(evolve_policy_candidates(pattern_report=pattern, overrides=[], precedents=[]))
    autonomy = _with_trace(evaluate_autonomy_expansion_gate(readiness={"eligible": True, "recommendation_only": False}, authority_inputs={"cde_authorized": True}))

    for artifact in [index, report, fused, aggregate, pattern, explain, trust, candidates, autonomy]:
        validate_nx_artifact(artifact)
        assert resolve_nx_contract(str(artifact["artifact_type"]))["schema_version"] == "1.0.0"


def test_nx_contract_resolution_fails_on_version_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    from spectrum_systems.modules.runtime import nx_governed_system as nxs

    manifest = nxs._load_manifest()
    for row in manifest["contracts"]:
        if row.get("artifact_type") == "fused_signal_record":
            row["schema_version"] = "9.9.9"
    monkeypatch.setattr(nxs, "_load_manifest", lambda: manifest)

    with pytest.raises(NXGovernedSystemError, match="schema mismatch"):
        resolve_nx_contract("fused_signal_record")
