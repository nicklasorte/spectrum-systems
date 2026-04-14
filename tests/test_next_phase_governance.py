from __future__ import annotations

from spectrum_systems.modules.runtime.next_phase_governance import (
    PromotionEnvelopeInput,
    build_abstention_record,
    build_context_preflight_result,
    build_evidence_sufficiency_result,
    build_query_index_manifest,
    build_synthesized_trust_signal,
    evaluate_promotion_trust_envelope,
    filter_active_records,
    retrieve_prx_precedents,
    normalize_translation_artifact,
    quarantine_simulated_for_promotion,
    translate_source_to_artifact,
    validate_ail_synthesis_non_authoritative,
    validate_cross_artifact_consistency,
    validate_hnx_semantic_handoff,
    validate_jsx_active_set,
)


def test_translation_and_normalization_are_deterministic() -> None:
    source = {"source_id": "abc", "payload": {"A": "Hello   World"}, "classification": "trusted"}
    a1 = translate_source_to_artifact(source)
    a2 = translate_source_to_artifact(source)
    assert a1["record_id"] == a2["record_id"]

    n1 = normalize_translation_artifact(a1)
    n2 = normalize_translation_artifact(a2)
    assert n1["payload"]["fingerprint"] == n2["payload"]["fingerprint"]
    assert n1["payload"]["canonical_payload"] == {"A": "hello world"}


def test_context_preflight_blocks_when_requirements_not_met() -> None:
    bundle = {
        "trace_id": "trace-1",
        "record_id": "ctx-1",
        "provenance": {"inputs": ["source-a"]},
    }
    result = build_context_preflight_result(
        bundle=bundle,
        required_sources={"source-a", "source-b"},
        freshness_ok=False,
        conflicts=["conflict-1"],
    )
    assert result["status"] == "block"
    assert "context_insufficient" in result["reason_codes"]


def test_evidence_and_abstention_wiring() -> None:
    evd = build_evidence_sufficiency_result(1, threshold=2)
    assert evd["status"] == "insufficient"

    abs_record = build_abstention_record("insufficient_evidence", "trace-evd")
    assert abs_record["status"] == "abstain"
    assert abs_record["escalation_required"] is True


def test_simulation_quarantine_and_promotion_lock() -> None:
    artifacts = [
        {"artifact_type": "eval_slice_summary", "provenance": {"simulated": True}},
        {"artifact_type": "judgment_record", "provenance": {"simulated": False}},
    ]
    blocked = quarantine_simulated_for_promotion(artifacts)
    assert blocked == ["simulated_artifact_blocked:eval_slice_summary"]

    envelope = evaluate_promotion_trust_envelope(
        PromotionEnvelopeInput(
            context_ready=True,
            required_evals_present=True,
            evidence_sufficient=True,
            judgment_present=True,
            consistency_ok=True,
            replay_ok=True,
            active_policy=True,
            control_clearance=True,
            no_simulated_evidence=False,
        )
    )
    assert envelope["promotion_allowed"] is False
    assert "simulated_evidence_not_allowed" in envelope["blocking_reasons"]


def test_consistency_active_set_query_and_signal() -> None:
    consistency = validate_cross_artifact_consistency(
        trace_ids={"t1", "t2"}, policy_active=False, replay_ok=True
    )
    assert consistency["consistent"] is False
    assert "trace_mismatch" in consistency["reason_codes"]

    records = [
        {"id": "a", "retired": False, "superseded": False},
        {"id": "b", "retired": True, "superseded": False},
        {"id": "c", "retired": False, "superseded": True},
    ]
    assert [r["id"] for r in filter_active_records(records)] == ["a"]

    manifest = build_query_index_manifest({"why_did_this_block": ["trace-1"]})
    assert "why_did_this_block" in manifest["payload"]["queries"]

    signal = build_synthesized_trust_signal(
        context_trust_score=0.6,
        evidence_sufficient=False,
        consistency_ok=False,
        override_rate=0.1,
    )
    assert signal["freeze_triggered"] is True


def test_jsx_stale_active_set_rejection() -> None:
    result = validate_jsx_active_set(
        [
            {"id": "j-1", "active": True, "retired": False, "superseded": False},
            {"id": "j-2", "active": True, "retired": True, "superseded": False},
        ]
    )
    assert result["valid"] is False
    assert result["stale_active_records"] == ["j-2"]
    assert "stale_active_set_rejected" in result["reason_codes"]


def test_prx_retrieval_excludes_stale_precedents_by_default() -> None:
    precedents = [
        {"id": "p-1", "retired": False, "superseded": False, "scope_tags": ["route"]},
        {"id": "p-2", "retired": True, "superseded": False, "scope_tags": ["route"]},
        {"id": "p-3", "retired": False, "superseded": True, "scope_tags": ["route"]},
        {"id": "p-4", "retired": False, "superseded": False, "scope_tags": ["policy"]},
    ]
    eligible = retrieve_prx_precedents(precedents, in_scope_tags={"route"})
    assert [row["id"] for row in eligible] == ["p-1"]


def test_ail_synthesis_is_non_authoritative() -> None:
    signal = build_synthesized_trust_signal(
        context_trust_score=0.8,
        evidence_sufficient=True,
        consistency_ok=True,
        override_rate=0.0,
    )
    validation = validate_ail_synthesis_non_authoritative(signal)
    assert validation["valid"] is True

    leaked = validate_ail_synthesis_non_authoritative({"status": "promote"})
    assert leaked["valid"] is False
    assert leaked["reason_codes"] == ["ail_authority_leak_blocked"]


def test_hnx_semantic_handoff_completeness() -> None:
    result = validate_hnx_semantic_handoff({"reset": True, "resume": True, "review": True, "fix": True, "promotion": False})
    assert result["complete"] is False
    assert result["missing"] == ["promotion"]
