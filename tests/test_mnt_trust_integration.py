from __future__ import annotations

import copy

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.mnt_trust_integration import (
    MNTIntegrationError,
    apply_fix_pack,
    build_cross_system_evidence_chain,
    build_platform_slo_error_budget_layer,
    build_unified_certification_bundle,
    check_certification_input_coverage,
    check_observability_completeness,
    classify_replay_mismatch,
    detect_evidence_fragmentation,
    detect_guard_duplication,
    detect_superseded_artifact_leaks,
    enforce_platform_promotion_hard_gate,
    generate_drift_debt_signals,
    generate_override_hotspots,
    reconstruct_critical_path,
    run_map_closeout_gate,
    run_maintain_stage_engine,
    run_redteam_round,
    run_simplification_pass,
    validate_active_set_registry,
    validate_cross_system_replay,
)


def _stage_records() -> dict[str, dict[str, str]]:
    stages = ["admission", "orchestration", "policy", "execution", "review", "repair", "enforcement", "certification"]
    return {
        stage: {"artifact_ref": f"{stage}:artifact", "lineage_ref": f"lineage:{stage}"}
        for stage in stages
    }


def test_mnt_contract_examples_validate() -> None:
    validate_artifact(load_example("mnt_trust_integration_bundle"), "mnt_trust_integration_bundle")
    validate_artifact(load_example("mnt_maintain_cycle_report"), "mnt_maintain_cycle_report")


def test_mnt_01_map_closeout_gate() -> None:
    gate = run_map_closeout_gate(
        map_record={"projection_scope": "mediation_projection_only", "source_artifact_hash": "h1", "lineage_ref": "lineage:map"},
        map_eval={"evaluation_status": "pass"},
        map_readiness={"readiness_status": "candidate_only"},
        replay_ok=True,
    )
    assert gate["status"] == "pass"


def test_mnt_02_to_05b_evidence_chain_bundle_replay_observability_and_fragmentation() -> None:
    chain = build_cross_system_evidence_chain(stage_records=_stage_records(), trace_id="trace-mnt-1")
    replay = validate_cross_system_replay(prior_chain=chain, replay_chain=copy.deepcopy(chain))
    observability = check_observability_completeness(chain=chain)
    bundle = build_unified_certification_bundle(
        evidence_chain=chain,
        replay_result=replay,
        observability_result=observability,
        cde_certification_ref="closure_decision_artifact:cde-1",
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-mnt-1",
    )
    assert bundle["input_coverage"]["status"] == "pass"
    assert reconstruct_critical_path(chain) == ["admission", "orchestration", "policy", "execution", "review", "repair", "enforcement", "certification"]

    fragmentation = detect_evidence_fragmentation(
        artifacts=[{"group": "a"}, {"group": "b"}, {"group": "c"}],
        max_groups=2,
    )
    assert fragmentation["fragmented"] is True


def test_mnt_03a_and_04a_coverage_and_replay_classifier() -> None:
    coverage = check_certification_input_coverage({"evidence_chain_ref": "ok", "replay_ref": "ok"})
    assert coverage["status"] == "fail"
    assert "observability_ref" in coverage["missing_inputs"]

    mismatch = classify_replay_mismatch(
        prior={"trace_id": "t1", "schema_version": "1", "artifact_hash": "a", "policy_version": "p1"},
        replay={"trace_id": "t2", "schema_version": "2", "artifact_hash": "b", "policy_version": "p2", "hidden_state_detected": True},
    )
    assert mismatch == ["artifact_substitution", "hidden_state", "policy_version_mismatch", "schema_drift", "trace_gap"]


def test_mnt_07_to_10a_drift_hotspots_supersession_simplification_maintain_and_eval_growth() -> None:
    drift = generate_drift_debt_signals(
        replay_failures=1,
        missing_evals=2,
        schema_bypasses=0,
        override_pressure=3,
        promotion_fragility=1,
        evidence_gaps=2,
    )
    hotspots = generate_override_hotspots([
        {"module": "faq"},
        {"module": "faq"},
        {"module": "map"},
    ])
    assert hotspots["hotspots"][0] == {"module": "faq", "count": 2}

    active_set = {"policy": ["v2"], "judgment": ["j3"]}
    assert validate_active_set_registry(active_set)["status"] == "pass"
    leaks = detect_superseded_artifact_leaks(active_set=active_set, observed_refs=["policy:v1", "judgment:j3"])
    assert leaks["status"] == "fail"

    duplication = detect_guard_duplication(["guard:trace", "guard:trace", "guard:replay"])
    simplified = run_simplification_pass(["guard:trace", "guard:trace", "guard:replay"])
    assert duplication["duplicate_guards"] == ["guard:trace"]
    assert simplified["after"] == 2

    maintain = run_maintain_stage_engine(drift_signals=drift, recurring_failures=["replay_drift", "replay_drift", "missing_eval"])
    assert maintain["authority_boundary_status"] == "non_authoritative"
    assert any(item["status"] == "admitted" for item in maintain["eval_expansion"])


def test_mnt_rt1_fx1_rt2_fx2_every_exploit_becomes_eval_test_guard() -> None:
    rt1_exploits = run_redteam_round([
        {"fixture_id": "RT1-CHAIN-GAP", "failure": "missing_chain_link", "should_block": True, "observed": "accepted"},
        {"fixture_id": "RT1-BLOCKED", "failure": "ok", "should_block": True, "observed": "blocked"},
    ])
    fx1 = apply_fix_pack(exploits=rt1_exploits)
    assert fx1["regression_tests"] == ["RT1-CHAIN-GAP"]
    assert fx1["hardened_guards"] == ["guard:missing_chain_link"]

    rt2_exploits = run_redteam_round([
        {"fixture_id": "RT2-SUPERSESSION-LEAK", "failure": "superseded_leak", "should_block": True, "observed": "accepted"},
    ])
    fx2 = apply_fix_pack(exploits=rt2_exploits)
    assert fx2["converted_to_evals"][0]["eval_id"] == "eval-RT2-SUPERSESSION-LEAK"


def test_mnt_11_and_12_slo_and_promotion_gate() -> None:
    slo = build_platform_slo_error_budget_layer(
        {
            "replay_integrity": 0.95,
            "eval_coverage": 0.8,
            "trace_completeness": 0.9,
            "certification_health": 0.85,
            "evidence_chain_completeness": 0.88,
        }
    )
    assert slo["status"] == "degraded"

    gate = enforce_platform_promotion_hard_gate(
        certification_bundle_ok=True,
        replay_ok=True,
        observability_ok=True,
        evidence_chain_ok=False,
    )
    assert gate["status"] == "blocked"
    assert gate["missing"] == ["evidence_chain"]


def test_mnt_fail_closed_on_missing_chain_stage() -> None:
    stages = _stage_records()
    stages.pop("repair")
    with pytest.raises(MNTIntegrationError, match="missing_chain_stages"):
        build_cross_system_evidence_chain(stage_records=stages, trace_id="trace-mnt-fail")
