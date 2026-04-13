from __future__ import annotations

import copy

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.rdx_hardening import (
    RDXHardeningError,
    build_execution_loop_readiness_handoff,
    build_governance_bundle,
    build_roadmap_selection_record,
    build_rework_debt_record,
    build_selection_conflict_record,
    build_selection_effectiveness,
    build_selection_readiness,
    build_umbrella_selection_record,
    detect_pass_through_wrappers,
    detect_progression_artifact_misuse,
    enforce_rdx_boundary,
    evaluate_selection,
    run_rdx_boundary_redteam,
    run_rdx_semantic_redteam,
    select_next_governed_batch,
    validate_progression_vs_closure,
    validate_selection_replay,
    validate_selection_to_tlc_integrity,
    verify_hnx_closeout_dependency_gate,
)


def _roadmap() -> dict:
    return {
        "roadmap_id": "RM-001",
        "trace_id": "trace-rdx-001",
        "lineage_ref": "lineage:rdx:001",
        "dependency_graph_ref": "dep:1",
        "trust_signal_ref": "trust:1",
        "batches": [
            {
                "batch_id": "BATCH-TRUST-01",
                "umbrella_id": "UMB-TRUST-01",
                "status": "not_started",
                "depends_on": ["BATCH-BASE-01"],
                "priority": 20,
                "trust_gap_tag": "trust-core",
                "slice_ids": ["S1", "S2"],
            },
            {
                "batch_id": "BATCH-CAP-01",
                "umbrella_id": "UMB-CAP-01",
                "status": "not_started",
                "depends_on": ["BATCH-BASE-01"],
                "priority": 1,
                "trust_gap_tag": "capability",
                "slice_ids": ["S3", "S4"],
            },
            {
                "batch_id": "BATCH-BASE-01",
                "umbrella_id": "UMB-BASE-01",
                "status": "completed",
                "depends_on": [],
                "priority": 0,
                "trust_gap_tag": "foundation",
                "slice_ids": ["S0A", "S0B"],
            },
        ],
        "umbrellas": [
            {"umbrella_id": "UMB-TRUST-01", "batch_ids": ["BATCH-TRUST-01", "BATCH-CAP-01"]},
            {"umbrella_id": "UMB-BASE-01", "batch_ids": ["BATCH-BASE-01", "BATCH-TRUST-01"]},
        ],
    }


def test_rdx_contract_examples_validate() -> None:
    for name in (
        "rdx_roadmap_selection_record",
        "rdx_batch_selection_record",
        "rdx_umbrella_selection_record",
        "rdx_execution_loop_readiness_handoff_record",
        "rdx_selection_eval_result",
        "rdx_selection_conflict_record",
        "rdx_selection_readiness_record",
        "rdx_selection_effectiveness_record",
        "rdx_rework_debt_record",
        "rdx_roadmap_governance_bundle",
    ):
        validate_artifact(load_example(name), name)


def test_rdx_01_02_03_boundary_fencing_and_deterministic_selection() -> None:
    failures = enforce_rdx_boundary(
        consumed_inputs=["roadmap_artifact", "trust_gap_signals", "pqx_execution_record"],
        emitted_outputs=["rdx_batch_selection_record", "closure_decision_artifact"],
        claimed_actions=["execute_work_slice:B1"],
    )
    assert "invalid_upstream_input:pqx_execution_record" in failures
    assert "invalid_downstream_output:closure_decision_artifact" in failures
    assert "forbidden_owner_overlap:execute_work_slice:B1" in failures

    selection_a = select_next_governed_batch(roadmap=_roadmap(), trust_gap_priority=["trust-core", "capability"], now="2026-04-13T00:00:00Z")
    selection_b = select_next_governed_batch(roadmap=_roadmap(), trust_gap_priority=["trust-core", "capability"], now="2026-04-13T00:00:00Z")
    assert selection_a == selection_b
    assert selection_a["selected_batch_id"] == "BATCH-TRUST-01"


def test_rdx_04_06_07_08_and_08a_08b_checks() -> None:
    roadmap = _roadmap()
    selection = select_next_governed_batch(roadmap=roadmap, trust_gap_priority=["trust-core", "capability"], now="2026-04-13T00:00:00Z")
    eval_result = evaluate_selection(
        roadmap=roadmap,
        selection_record=selection,
        owner="RDX",
        trust_gap_priority=["trust-core", "capability"],
        evaluated_at="2026-04-13T00:00:00Z",
    )
    assert eval_result["evaluation_status"] == "pass"

    replay_ok, replay_fails = validate_selection_replay(
        prior_input=roadmap,
        replay_input=copy.deepcopy(roadmap),
        prior_selection=selection,
        replay_selection=copy.deepcopy(selection),
        prior_eval=eval_result,
        replay_eval=copy.deepcopy(eval_result),
    )
    assert replay_ok is True
    assert replay_fails == []

    progression_fails = validate_progression_vs_closure(
        progression_refs=["batch_progression:B1"],
        closure_refs=["closure_decision_artifact:CDE-1"],
        non_authority_assertions=["rdx_not_closure_authority"],
    )
    assert progression_fails == []

    wrapper_roadmap = _roadmap()
    wrapper_roadmap["batches"][0]["slice_ids"] = ["BATCH-TRUST-01"]
    assert "batch_pass_through_wrapper:BATCH-TRUST-01" in detect_pass_through_wrappers(roadmap=wrapper_roadmap)


def test_rdx_08c_08d_08e_05_09_artifacts_and_fail_closed() -> None:
    debt = build_rework_debt_record(
        selection_history=[
            {"deferred_batch_ids": ["BATCH-TRUST-01"]},
            {"deferred_batch_ids": ["BATCH-TRUST-01"]},
            {"deferred_batch_ids": ["BATCH-TRUST-01", "BATCH-CAP-01"]},
        ],
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-rdx-001",
    )
    assert debt["debt_status"] == "elevated"

    tlc_fails = validate_selection_to_tlc_integrity(
        handoff_record={"selected_batch_id": "BATCH-TRUST-01", "selected_umbrella_id": "UMB-TRUST-01", "lineage_ref": "lineage:rdx:001"},
        tlc_input={"selected_batch_id": "BATCH-TRUST-01", "selected_umbrella_id": "UMB-TRUST-01", "lineage_ref": "lineage:rdx:001"},
    )
    assert tlc_fails == []

    misuse = detect_progression_artifact_misuse(
        consumer_artifacts=[
            {"artifact_id": "x", "source_ref": "rdx_selection_readiness_record:1", "used_for": "closure_evidence"}
        ]
    )
    assert misuse == ["progression_artifact_misused:x"]

    readiness = build_selection_readiness(
        eval_result={"fail_reasons": []}, dependency_failures=[], created_at="2026-04-13T00:00:00Z", trace_id="trace-rdx-001"
    )
    assert readiness["readiness_status"] == "candidate_only"

    effectiveness = build_selection_effectiveness(
        outcomes=[
            {"trust_gap_closed": True, "dependency_violation": False, "rework": False},
            {"trust_gap_closed": True, "dependency_violation": False, "rework": False},
            {"trust_gap_closed": True, "dependency_violation": False, "rework": False},
            {"trust_gap_closed": False, "dependency_violation": False, "rework": True},
        ],
        window_id="WIN-001",
        created_at="2026-04-13T00:00:00Z",
    )
    assert effectiveness["value_status"] == "improving"

    with pytest.raises(RDXHardeningError, match="selection_effectiveness_requires_outcomes"):
        build_selection_effectiveness(outcomes=[], window_id="W", created_at="2026-04-13T00:00:00Z")


def test_rdx_rt1_fx1_rt2_fx2_exploits_become_regressions_and_bundle() -> None:
    rt1_findings = run_rdx_boundary_redteam(
        fixtures=[
            {"fixture_id": "RT1-OWNER-LEAK", "should_fail_closed": True, "observed": "accepted"},
            {"fixture_id": "RT1-SCHEMA-MALFORM", "should_fail_closed": True, "observed": "blocked"},
        ]
    )
    assert [row["fixture_id"] for row in rt1_findings] == ["RT1-OWNER-LEAK"]

    rt2_findings = run_rdx_semantic_redteam(
        fixtures=[
            {"fixture_id": "RT2-TRUST-GAP-INVERSION", "semantic_risk": True, "observed": "accepted"},
            {"fixture_id": "RT2-DEPENDENCY-INVERSION", "semantic_risk": True, "observed": "blocked"},
        ]
    )
    assert [row["fixture_id"] for row in rt2_findings] == ["RT2-TRUST-GAP-INVERSION"]

    conflict = build_selection_conflict_record(
        trace_id="trace-rdx-001",
        created_at="2026-04-13T00:00:00Z",
        conflict_codes=["RT1-OWNER-LEAK", "RT2-TRUST-GAP-INVERSION"],
    )
    assert len(conflict["conflict_codes"]) == 2

    roadmap = _roadmap()
    roadmap_record = build_roadmap_selection_record(
        roadmap=roadmap,
        selected_umbrella_id="UMB-TRUST-01",
        reason_codes=["dependency_satisfied", "trust_gap_priority_applied"],
        evaluated_at="2026-04-13T00:00:00Z",
    )
    batch_record = select_next_governed_batch(roadmap=roadmap, trust_gap_priority=["trust-core", "capability"], now="2026-04-13T00:00:00Z")
    umbrella_record = build_umbrella_selection_record(roadmap=roadmap, selected_umbrella_id="UMB-TRUST-01", evaluated_at="2026-04-13T00:00:00Z")
    handoff = build_execution_loop_readiness_handoff(
        trace_id="trace-rdx-001",
        selected_batch_id=batch_record["selected_batch_id"],
        selected_umbrella_id=roadmap_record["selected_umbrella_id"],
        lineage_ref="lineage:rdx:001",
        readiness_status="candidate_only",
        created_at="2026-04-13T00:00:00Z",
    )
    eval_result = {"eval_id": "rse-1"}
    readiness = {"readiness_id": "rsr-1"}
    effectiveness = {"effectiveness_id": "rseff-1"}
    debt = {"debt_id": "rrd-1"}
    bundle = build_governance_bundle(
        roadmap_selection=roadmap_record,
        batch_selection=batch_record,
        umbrella_selection=umbrella_record,
        handoff=handoff,
        eval_result=eval_result,
        readiness=readiness,
        effectiveness=effectiveness,
        rework_debt=debt,
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-rdx-001",
    )
    assert bundle["artifact_type"] == "rdx_roadmap_governance_bundle"


def test_hnx_gate_dependency_for_rdx_is_checked() -> None:
    closeout = verify_hnx_closeout_dependency_gate(
        hnx_closeout_status="closed",
        replay_match=True,
        stop_guard_ok=True,
        checkpoint_resume_ok=True,
    )
    assert closeout["closeout_status"] == "closed"
