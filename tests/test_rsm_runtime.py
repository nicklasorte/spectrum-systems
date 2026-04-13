from spectrum_systems.rsm import RSMRuntime
from spectrum_systems.contracts import validate_artifact


def _ril_inputs() -> list[dict]:
    return [
        {
            "artifact_kind": "ril_interpreted_state",
            "artifact_ref": "ril_interpreted_state:faq:001",
            "module_id": "faq",
            "status": "active",
            "trust": 0.72,
            "burden": 0.43,
            "freeze": False,
            "readiness": 0.63,
            "conflict_count": 2,
        },
        {
            "artifact_kind": "ril_interpreted_state",
            "artifact_ref": "ril_interpreted_state:working_paper:001",
            "module_id": "working_paper",
            "status": "active",
            "trust": 0.81,
            "burden": 0.25,
            "freeze": True,
            "readiness": 0.78,
            "conflict_count": 1,
        },
    ]


def test_rsm_artifacts_are_deterministic_and_validate_against_contracts() -> None:
    rsm = RSMRuntime()
    desired = rsm.build_desired_state_artifact(
        trace_id="trace-rsm-001",
        desired_module_posture={
            "faq": {"status": "active", "trust": 0.9, "burden": 0.2, "freeze": False, "readiness": 0.91},
            "working_paper": {"status": "active", "trust": 0.88, "burden": 0.21, "freeze": False, "readiness": 0.87},
        },
        desired_operator_posture={"review_capacity": 4, "escalation_policy": "bounded"},
        desired_portfolio_posture={"trust_budget": 0.8, "burden_budget": 0.35},
        source_ref="docs/roadmaps/system_roadmap.md",
        source_kind="roadmap",
        generated_at="2026-04-13T00:00:00Z",
    )
    desired_again = rsm.build_desired_state_artifact(
        trace_id="trace-rsm-001",
        desired_module_posture={
            "faq": {"status": "active", "trust": 0.9, "burden": 0.2, "freeze": False, "readiness": 0.91},
            "working_paper": {"status": "active", "trust": 0.88, "burden": 0.21, "freeze": False, "readiness": 0.87},
        },
        desired_operator_posture={"review_capacity": 4, "escalation_policy": "bounded"},
        desired_portfolio_posture={"trust_budget": 0.8, "burden_budget": 0.35},
        source_ref="docs/roadmaps/system_roadmap.md",
        source_kind="roadmap",
        generated_at="2026-04-13T00:00:00Z",
    )
    assert desired == desired_again

    actual = rsm.build_actual_state_artifact("trace-rsm-001", _ril_inputs())
    delta = rsm.compute_state_delta_artifact(desired, actual)
    divergences = rsm.classify_divergence(delta)
    reconciliation = rsm.generate_reconciliation_plan(divergences)
    portfolio = rsm.build_portfolio_snapshot(desired, actual, divergences)

    validate_artifact(desired, "rsm_desired_state_artifact")
    validate_artifact(actual, "rsm_actual_state_artifact")
    validate_artifact(delta, "rsm_state_delta_artifact")
    validate_artifact(divergences, "rsm_divergence_record")
    validate_artifact(reconciliation, "rsm_reconciliation_plan_artifact")
    validate_artifact(portfolio, "rsm_portfolio_state_snapshot")


def test_rsm_non_authoritative_and_no_sel_or_pqx_leakage() -> None:
    rsm = RSMRuntime()
    safe_artifact = {
        "artifact_type": "rsm_reconciliation_plan_artifact",
        "trace_id": "trace-rsm-001",
        "authoritative": False,
        "authority_owner": "CDE",
    }
    rsm.enforce_output_guardrails(safe_artifact)

    bad = {"artifact_type": "rsm_state_delta_artifact", "decision": "continue"}
    try:
        rsm.enforce_output_guardrails(bad)
        assert False, "expected permission error"
    except PermissionError as exc:
        assert "leakage" in str(exc)


def test_rsm_freshness_and_source_validation() -> None:
    rsm = RSMRuntime()
    desired = rsm.build_desired_state_artifact(
        trace_id="trace-rsm-002",
        desired_module_posture={"faq": {"status": "active", "trust": 0.8, "burden": 0.3, "freeze": False, "readiness": 0.7}},
        desired_operator_posture={"review_capacity": 3},
        desired_portfolio_posture={"trust_budget": 0.75},
        source_ref="docs/roadmaps/system_roadmap.md",
        source_kind="roadmap",
        generated_at="2026-04-10T00:00:00Z",
    )
    result = rsm.validate_desired_state_freshness(
        desired,
        now="2026-04-13T12:00:00Z",
        max_age_hours=48,
        allowed_sources={"roadmap", "policy"},
    )
    assert result["stale"] is True
    assert result["source_valid"] is True
    assert result["trust_degraded"] is True


def test_rsm_contract_enforcement_stability_and_prioritization() -> None:
    rsm = RSMRuntime()
    desired = rsm.build_desired_state_artifact(
        trace_id="trace-rsm-003",
        desired_module_posture={"faq": {"status": "active", "trust": 0.9, "burden": 0.2, "freeze": False, "readiness": 0.95}},
        desired_operator_posture={"review_capacity": 4},
        desired_portfolio_posture={"trust_budget": 0.8},
        source_ref="docs/roadmaps/system_roadmap.md",
        source_kind="roadmap",
        generated_at="2026-04-13T00:00:00Z",
    )
    actual = rsm.build_actual_state_artifact("trace-rsm-003", [
        {
            "artifact_kind": "ril_interpreted_state",
            "artifact_ref": "ril_interpreted_state:faq:100",
            "module_id": "faq",
            "status": "degraded",
            "trust": 0.3,
            "burden": 0.6,
            "freeze": False,
            "readiness": 0.4,
            "conflict_count": 4,
        }
    ])

    delta = rsm.compute_state_delta_artifact(desired, actual)
    divergences = rsm.classify_divergence(delta)
    ranked = rsm.rank_divergences(divergences["divergences"], top_k=3)
    stabilized = rsm.apply_stability_control(ranked, history=["faq::status"], cooldown_cycles=2)
    overload = rsm.protect_operator_overload(ranked, top_k=1, collapse_threshold=0.25)
    conflict = rsm.compute_conflict_density(actual, module_count=1)

    assert ranked[0]["field"] == "status"
    assert all(not d["cooldown_blocked"] for d in stabilized)
    assert len(overload["top_k"]) == 1
    assert conflict["density"] == 4.0


def test_rsm_rejects_raw_evidence_inputs_and_preserves_cde_authority() -> None:
    rsm = RSMRuntime()
    try:
        rsm.build_actual_state_artifact(
            "trace-rsm-004",
            [{"artifact_kind": "raw_event", "artifact_ref": "raw:1", "module_id": "faq", "raw_evidence": True}],
        )
        assert False, "expected fail-closed contract error"
    except ValueError as exc:
        assert "rsm_requires_ril_interpreted_inputs" in str(exc)

    desired = rsm.build_desired_state_artifact(
        trace_id="trace-rsm-004",
        desired_module_posture={"faq": {"status": "active", "trust": 0.9, "burden": 0.2, "freeze": False, "readiness": 0.9}},
        desired_operator_posture={"review_capacity": 3},
        desired_portfolio_posture={"trust_budget": 0.82},
        source_ref="docs/roadmaps/system_roadmap.md",
        source_kind="roadmap",
        generated_at="2026-04-13T00:00:00Z",
    )
    actual = rsm.build_actual_state_artifact("trace-rsm-004", _ril_inputs())
    delta = rsm.compute_state_delta_artifact(desired, actual)
    divergences = rsm.classify_divergence(delta)
    plan = rsm.generate_reconciliation_plan(divergences)
    portfolio = rsm.build_portfolio_snapshot(desired, actual, divergences)
    cde_input = rsm.build_cde_input_bundle(plan, portfolio)
    assert cde_input["decision_owner"] == "CDE"
    assert cde_input["authoritative"] is False
