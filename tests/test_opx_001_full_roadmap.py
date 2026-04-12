from spectrum_systems.opx.runtime import MANDATORY_TEST_COVERAGE, OPXRuntime, run_full_opx_roadmap


def test_opx_00_operator_actions_are_artifact_backed_and_authority_safe():
    runtime = OPXRuntime()
    artifact = runtime.create_operator_action("freeze", "trace-1")
    assert artifact.trace_id == "trace-1"
    assert artifact.authority_path == runtime.canonical_authority_path

    try:
        runtime.enforce_authority_path(("AEX", "PQX"))
        assert False, "bypass must fail"
    except PermissionError:
        assert True


def test_opx_01_review_queue_is_bounded_and_owner_safe():
    runtime = OPXRuntime()
    queued = runtime.enqueue_review("faq", "high", threshold=80)
    assert queued["owner"] == "RQX"
    processed = runtime.process_review(0, score=40)
    assert processed["bounded_fix_required"] is True


def test_opx_02_to_06_faq_pipeline_judgment_cert_dataset_runbook():
    runtime = OPXRuntime()
    output = runtime.run_module("faq", "t", ["doc-a"])
    assert output["lineage"] == list(runtime.canonical_authority_path)
    assert output["judgment"]["judgment_record"] is True

    cert = runtime.certify_module(output, replay_ok=True, contracts_ok=True, compatibility_ok=True, negative_path_checked=True)
    assert cert["certified"] is True

    key = runtime.register_dataset_case("faq", "v1", "core", "default", {"result": "ok"})
    assert runtime.retrieve_dataset_case("faq", "v1", "core", "default") == {"result": "ok"}
    assert key == "faq:v1:core:default"

    runbook = runtime.generate_runbook("stale_context")
    assert "trace" in runbook["required_evidence"]


def test_opx_07_to_14_compression_bypass_canary_reuse_budget_active_compat_override():
    runtime = OPXRuntime()
    tracker = runtime.apply_prompt_compression()
    assert "stage_defaults" in tracker

    bypass = runtime.detect_bypass(["AEX", "TLC", "PQX"])
    assert bypass["blocked"] is True

    canary = runtime.register_candidate_rollout("c1", activated=False)
    assert canary["governed"] is True

    missing_reuse = runtime.record_reuse("policy", None)
    assert missing_reuse["valid"] is False

    budget = runtime.consume_budget("wrong_allow", 2, closure_authorized=False, enforced=True)
    assert budget["blocked"] is True

    runtime.set_active_item("policy", "v1")
    runtime.set_active_item("policy", "v2", supersedes="v1")
    assert runtime.retrieve_active("policy") == ["v2"]

    compat = runtime.compatibility_audit({"shared": "2.0-breaking"})
    assert compat["drift_detected"] is True

    hygiene = runtime.override_hygiene_audit([{"id": "o1", "expires": None, "justification": ""}])
    assert hygiene["healthy"] is False


def test_opx_15_to_28_redteam_template_multimodule_controlplane_and_governance():
    runtime = OPXRuntime()
    red1 = runtime.red_team("pack-1", ["authority_bypass"])
    fix1 = runtime.fix_wave(red1)
    assert red1["count"] == fix1["fixed"]

    template = runtime.extract_template("faq")
    minutes = runtime.instantiate_from_template("minutes", template)
    working_paper = runtime.instantiate_from_template("working_paper", template)
    comment_resolution = runtime.instantiate_from_template("comment_resolution", template)
    study_plan = runtime.instantiate_from_template("study_plan", template)
    assert len({minutes["template_hash"], working_paper["template_hash"], comment_resolution["template_hash"], study_plan["template_hash"]}) == 1

    runtime.enqueue_review("minutes", "med", 50)
    runtime.process_review(0, 40)
    plane = runtime.cross_module_control_plane()
    assert "queue_posture" in plane

    backtest = runtime.backtest_counterfactual([{"id": "c1"}])
    assert backtest["authoritative"] is False

    simulation = runtime.governed_simulation("sim-1", 512)
    assert simulation["resource_limit"] == 512
    assert simulation["replayable"] is True

    prioritizer = runtime.portfolio_prioritizer([{"trust": 1, "cost": 2, "value": 3}])
    assert prioritizer["authoritative"] is False

    maintain = runtime.maintain_stage()
    assert maintain["invariant_checks"] == "done"

    red2 = runtime.red_team("pack-2", ["queue_overload"])
    fix2 = runtime.fix_wave(red2)
    assert fix2["remaining"] == 0
    assert runtime.non_duplication_check() is True


def test_full_roadmap_runner_and_mandatory_coverage_index_present():
    summary = run_full_opx_roadmap()
    assert summary["fix_wave_1"]["remaining"] == 0
    assert summary["fix_wave_2"]["remaining"] == 0
    assert len(MANDATORY_TEST_COVERAGE) == 25
