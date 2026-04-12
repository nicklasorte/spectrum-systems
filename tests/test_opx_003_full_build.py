from spectrum_systems.opx.runtime import OPXRuntime, OPX_003_MANDATORY_TEST_COVERAGE, run_opx_003_roadmap


def test_opx_003_serial_runner_executes_all_groups_and_mandatory_coverage():
    summary = run_opx_003_roadmap()

    assert summary["operator_flow"]["request"]["kind"] == "operator_action_request_artifact"
    assert summary["operator_flow"]["resolution"]["kind"] == "operator_action_resolution_artifact"
    assert summary["evidence_bundle"]["kind"] == "operator_evidence_bundle_artifact"
    assert summary["faq_hardened"]["promotion_ready"] is True
    assert summary["template"]["template"]["feedback_hooks"] == ["feedback_to_eval_artifacts"]
    assert summary["compatibility"]["drift"] is True
    assert summary["conflicts"]["conflicts"] == ["p-1!=j-1"]
    assert summary["trust"]["authoritative"] is False
    assert summary["burden"]["pending_escalations"] == 1
    assert summary["modules"]["working_paper"]["certification"]["certified"] is True
    assert summary["modules"]["comment_resolution"]["certification"]["certified"] is True
    assert summary["modules"]["study_plan"]["certification"]["certified"] is True
    assert summary["champion_challenger"]["auto_activation"] is False
    assert summary["maintain_stage"]["silent_mutation"] is False
    assert summary["simulation_pack"]["replayability"] is True
    assert summary["fix_wave_1"]["remaining"] == 0
    assert summary["semantic_cache"]["hit"]["hit"] is True
    assert summary["semantic_cache"]["miss"]["hit"] is False
    assert summary["fix_wave_2"]["remaining"] == 0
    assert summary["non_duplication"] is True
    assert len(OPX_003_MANDATORY_TEST_COVERAGE) == 19


def test_operator_actions_fail_closed_and_emit_governed_artifacts():
    runtime = OPXRuntime()
    flow = runtime.build_operator_action_flow(
        action="freeze",
        trace_id="trace-fail-closed",
        actor="operator-z",
        evidence_refs=["prov:z:1"],
    )
    assert flow["resolution"]["enforcement_owner"] == "SEL"

    bad_action = runtime.create_operator_action_v2(
        "assign_review",
        "trace-bad",
        actor="operator-z",
        evidence_refs=["prov:z:2"],
    )
    bad_action["authority_path"] = ["AEX", "PQX"]
    try:
        runtime.route_operator_action(bad_action)
        assert False, "must fail closed"
    except PermissionError:
        assert True


def test_evidence_bundle_and_feedback_artifacts_are_deterministic():
    runtime = OPXRuntime()
    current = {
        "trace_link": "trace-deterministic",
        "recommendation": "approve_bounded_continuation",
        "confidence": 0.9,
        "provenance_refs": ["prov:1", "prov:2"],
    }
    prior = {"trace_link": "trace-deterministic", "recommendation": "abstain", "confidence": 0.5}

    first = runtime.build_operator_evidence_bundle(current, prior, ["prov:2"], ["calibration_decay"])
    second = runtime.build_operator_evidence_bundle(current, prior, ["prov:2"], ["calibration_decay"])

    assert first["bundle_hash"] == second["bundle_hash"]

    feedback = runtime.feedback_to_eval_artifacts(
        "faq",
        override_events=[{"id": "ovr-10", "recurs": True}],
        review_findings=[{"id": "rvw-10"}],
        corrections=[{"id": "fix-10", "pattern": "evidence_gap"}],
    )
    assert feedback["eval_cases"] == ["eval:ovr-10", "eval:rvw-10", "eval:fix-10"]
    assert feedback["dataset_candidates"] == ["dataset:fix-10"]
    assert feedback["override_recurrence_signals"] == ["ovr-10"]


def test_semantic_cache_strict_match_and_key_shape_enforced():
    runtime = OPXRuntime()
    key_fields = {
        "task_spec": "task-a",
        "schema_version": "1.0",
        "policy_version": "1.0",
        "context_fingerprint": "ctx-a",
        "active_set": "as-a",
    }
    runtime.semantic_cache_store(key_fields, {"result": "ok"})
    hit = runtime.semantic_cache_retrieve(key_fields)
    assert hit["hit"] is True
    assert hit["reuse_record"]["kind"] == "reuse_record_artifact"

    malformed = runtime.semantic_cache_retrieve({"task_spec": "task-a"})
    assert malformed["hit"] is False
    assert malformed["reason"] == "governed_key_shape_mismatch"
