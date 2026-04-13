from spectrum_systems.opx import DesiredStateRegistry, OPX005Runtime


def test_desired_state_registry_versioned_retrieve_is_deterministic() -> None:
    reg = DesiredStateRegistry()
    older = reg.register(
        target_id="portfolio/core",
        version="1.0.0",
        state={"target": "stabilize"},
        source={"source_ref": "roadmap:v1", "source_kind": "roadmap"},
        generated_at="2026-04-13T00:00:00Z",
    )
    newer = reg.register(
        target_id="portfolio/core",
        version="1.1.0",
        state={"target": "expand"},
        source={"source_ref": "roadmap:v2", "source_kind": "roadmap"},
        generated_at="2026-04-13T01:00:00Z",
    )
    picked_a = reg.retrieve([newer, older], "portfolio/core")
    picked_b = reg.retrieve([older, newer], "portfolio/core")
    assert picked_a == picked_b
    assert picked_a["version"] == "1.1.0"
    assert picked_a["non_authoritative"] is True


def test_precedent_gate_and_precedence_engine_block_invalid_inputs() -> None:
    rt = OPX005Runtime()
    eligibility = rt.precedent_eligibility_gate(
        [
            {"precedent_id": "p1", "active": True, "scope": "faq", "provenance_valid": True},
            {"precedent_id": "p2", "active": False, "scope": "faq", "provenance_valid": True},
            {"precedent_id": "p3", "active": True, "scope": "other", "provenance_valid": True},
        ],
        scope="faq",
        now="2026-04-13T04:00:00Z",
    )
    assert [p["precedent_id"] for p in eligibility["eligible_precedents"]] == ["p1"]
    assert len(eligibility["rejected_precedents"]) == 2

    precedence = rt.resolve_precedence(
        [
            {"rule_id": "r1", "key": "freeze", "value": True, "layer": "local_override"},
            {"rule_id": "r2", "key": "freeze", "value": False, "layer": "global_invariant"},
        ]
    )
    assert precedence["resolved"][0]["winner_rule_id"] == "r2"
    assert precedence["conflicts"]


def test_compilation_degrades_safely_and_provenance_fails_closed() -> None:
    rt = OPX005Runtime()
    degraded = rt.compile_judgment_to_policy({"judgment_id": "j-1", "stable_cycles": 1})
    assert degraded["status"] == "commentary_only"

    verification = rt.verify_promotion_provenance({"lineage_chain": ["a"]})
    assert verification["passed"] is False
    assert verification["fail_closed"] is True


def test_reconciliation_economics_blast_doctrine_memory_xrl_and_planning_are_deterministic() -> None:
    rt = OPX005Runtime()
    debt = rt.reconciliation_debt([
        {"module_id": "m1", "magnitude": 0.4},
        {"module_id": "m1", "magnitude": 0.3},
        {"module_id": "m2", "magnitude": 0.2},
    ])
    assert debt["module_debt"] == {"m1": 0.7, "m2": 0.2}

    dem = rt.dem_decision_economics({"cost_of_delay": 3.0, "false_positive_cost": 1.0, "false_negative_cost": 2.0, "human_review_cost": 1.0})
    assert dem["recommendation_only"] is True

    brm = rt.brm_blast_radius({"affected_modules": 6, "irreversible": True})
    assert brm["escalation_requirement_record"] is True

    mcl = rt.mcl_compaction([
        {"record_id": "a", "age_days": 45, "entropy": 0.2},
        {"record_id": "b", "age_days": 3, "entropy": 0.9},
    ])
    assert mcl["archival_tier_assignment"] == ["a"]
    assert mcl["memory_compaction_plan"] == ["b"]

    dcl = rt.dcl_compile_doctrine([
        {"judgment_id": "j1", "topic": "freeze", "stance": "strict", "stable": True, "validated": True},
        {"judgment_id": "j2", "topic": "freeze", "stance": "loose", "stable": True, "validated": True, "conflict": True},
    ])
    assert dcl["doctrine_update_candidate"] is True

    xrl = rt.xrl_weight_outcomes(
        [{"signal_id": "s1", "observed_at": "2026-04-12T00:00:00Z", "corroborations": 2, "source_reputation": 0.9}],
        now="2026-04-13T00:00:00Z",
    )
    assert xrl["external_outcome_signal"][0]["outcome_trust_weight"] > 0

    readiness = rt.readiness_planner([
        {"module_id": "m1", "trust": 0.8, "outcome": 0.7, "burden": 0.2, "compatibility": 0.9},
        {"module_id": "m2", "trust": 0.5, "outcome": 0.4, "burden": 0.5, "compatibility": 0.6},
    ])
    assert readiness["recommendations"][0]["module_id"] == "m1"

    scenarios = rt.strategic_scenarios({"trust": 0.7, "burden": 0.3, "outcome": 0.6})
    assert len(scenarios["scenarios"]) == 2


def test_trace_gate_freeze_and_redteam_fix_rounds() -> None:
    rt = OPX005Runtime()
    trace = rt.trace_completeness_gate({"trace_id": "t1", "lineage_chain": ["a"], "evidence_refs": ["e"], "replay_ref": None})
    assert trace["allow_progression"] is False

    release = rt.policy_release_gate({"tests_passed": True, "reviewed": False, "canary_ready": True, "rollback_hook": True})
    assert release["release_ready"] is False

    findings = rt.redteam_findings("rt-1", [{"scenario": "stale precedent", "exposed": True}, {"scenario": "queue starvation", "exposed": False}])
    fix = rt.fix_wave(findings)
    assert findings["fix_wave_required"] is True
    assert fix["status"] == "resolved"
