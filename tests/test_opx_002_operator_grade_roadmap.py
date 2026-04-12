from spectrum_systems.opx.runtime import OPXRuntime, OPX_002_MANDATORY_TEST_COVERAGE


def test_opx_29_operator_control_v2_actions_and_authority_enforcement():
    runtime = OPXRuntime()
    action = runtime.create_operator_action_v2(
        "assign_review",
        "trace-29",
        actor="operator-1",
        evidence_refs=["prov:a"],
        queue_id="q-review",
        reviewer="rqx-1",
    )
    routed = runtime.route_operator_action(action)
    assert routed["tlc_routed"] is True
    assert routed["rqx_queue_id"] == "q-review"

    action["authority_path"] = ["AEX", "PQX"]
    try:
        runtime.route_operator_action(action)
        assert False, "authority bypass must fail-closed"
    except PermissionError:
        assert True


def test_opx_30_to_33_evidence_bundle_faq_hardening_feedback_and_template_compiler():
    runtime = OPXRuntime()
    current = {
        "trace_link": "trace:30",
        "confidence": 0.9,
        "provenance_refs": ["prov:1", "prov:2"],
        "trust_decomposition_ref": "trust:30",
    }
    prior = {"trace_link": "trace:30", "confidence": 0.6}
    bundle_1 = runtime.build_operator_evidence_bundle(current, prior, ["prov:2"], ["policy_change"])
    bundle_2 = runtime.build_operator_evidence_bundle(current, prior, ["prov:2"], ["policy_change"])
    assert bundle_1["bundle_hash"] == bundle_2["bundle_hash"]

    faq_output = runtime.run_module("faq", "transcript", ["doc-a"])
    hardened = runtime.harden_faq_wave2(
        faq_output,
        override={"justification": "bounded override", "expires": "2026-05-01"},
        replay_ok=True,
        context_quality=90,
        trust_posture="guarded",
        promotion_regret=0.02,
    )
    assert hardened["promotion_ready"] is True

    feedback = runtime.feedback_to_eval_artifacts(
        "faq",
        override_events=[{"id": "ovr-1", "recurs": True}],
        review_findings=[{"id": "rvw-1"}],
        corrections=[{"id": "fix-1", "pattern": "citation"}],
    )
    assert feedback["authoritative"] is False
    template = runtime.compile_module_template(faq_output, feedback)
    assert template["template"]["feedback_hooks"] == ["feedback_to_eval_artifacts"]


def test_opx_34_to_37_compatibility_conflicts_trust_and_burden_metrics():
    runtime = OPXRuntime()
    graph = runtime.build_compatibility_graph([
        {"name": "faq", "shared_contracts": ["policy-core"], "schema_versions": {"output": "2.0-breaking"}},
        {"name": "working_paper", "shared_contracts": ["policy-core"], "schema_versions": {"output": "1.2"}},
    ])
    assert graph["drift"] is True
    assert graph["incompatibilities"] == ["faq:output:2.0-breaking"]

    conflicts = runtime.resolve_policy_judgment_conflicts({
        "policies": [{"id": "p1", "topic": "scope", "stance": "allow"}],
        "judgments": [{"id": "j1", "topic": "scope", "stance": "deny"}],
    })
    assert conflicts["conflicts"] == ["p1!=j1"]

    trust = runtime.trust_decomposition({"trace_failures": 1, "replay_failures": 2, "review_backlog": 3})
    assert trust["authoritative"] is False
    metrics = runtime.queue_burden_metrics(
        [
            {"status": "escalated", "age_hours": 30, "action_latency_minutes": 10, "override": True, "disagreement": True},
            {"status": "fixed", "age_hours": 2, "action_latency_minutes": 20, "override": False, "disagreement": False},
        ],
        cert_backlog=4,
    )
    assert metrics["review_queue_size"] == 2
    assert metrics["pending_escalations"] == 1


def test_opx_38_to_40_templated_modules_run_e2e_with_certification():
    runtime = OPXRuntime()
    faq_output = runtime.run_module("faq", "seed", ["ctx"])
    feedback = runtime.feedback_to_eval_artifacts("faq", override_events=[], review_findings=[], corrections=[])
    template = runtime.compile_module_template(faq_output, feedback)
    wp = runtime.run_templated_module_e2e("working_paper", template, "wp-t", ["wp-c1"])
    cr = runtime.run_templated_module_e2e("comment_resolution", template, "cr-t", ["cr-c1"])
    sp = runtime.run_templated_module_e2e("study_plan", template, "sp-t", ["sp-c1"])
    assert wp["certification"]["certified"] is True
    assert cr["governed"] is True
    assert sp["output"]["module"] == "study_plan"


def test_opx_41_to_43_champion_lane_maintain_stage_and_simulation_pack():
    runtime = OPXRuntime()
    lane = runtime.champion_challenger_lane({"id": "champ"}, {"id": "challenger"}, 0.1)
    assert lane["auto_activation"] is False
    maintain = runtime.maintain_stage_v2("fixed-seed")
    assert maintain["silent_mutation"] is False
    simulation = runtime.simulation_promotion_pack("sim-43", resource_limit=1024, replay_seed="r1")
    assert simulation["replayability"] is True


def test_opx_44_to_48_red_team_fix_waves_semantic_cache_and_non_duplication():
    runtime = OPXRuntime()
    red1 = runtime.red_team_pack_v2("rt1", ["operator_action_abuse", "authority_bypass"])
    fix1 = runtime.apply_fix_wave_v2(red1)
    assert fix1["remaining"] == 0

    key_fields = {
        "task_spec": "faq-issue",
        "schema_version": "1.0",
        "policy_version": "1.0",
        "context_fingerprint": "abc",
        "active_set": "v2",
    }
    runtime.semantic_cache_store(key_fields, {"payload": "ok"})
    hit = runtime.semantic_cache_retrieve(key_fields)
    miss = runtime.semantic_cache_retrieve({**key_fields, "policy_version": "2.0"})
    assert hit["hit"] is True and hit["reuse_record_emitted"] is True
    assert miss["hit"] is False

    red2 = runtime.red_team_pack_v2("rt2", ["cache_poisoning", "queue_overload", "policy_conflict"])
    fix2 = runtime.apply_fix_wave_v2(red2)
    assert fix2["remaining"] == 0
    assert runtime.non_duplication_check() is True
    assert len(OPX_002_MANDATORY_TEST_COVERAGE) == 19
