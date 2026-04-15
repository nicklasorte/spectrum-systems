from datetime import datetime, timedelta, timezone

import pytest

from spectrum_systems.modules.runtime.roadmap_long_fabric import (
    RoadmapOrchestratorError,
    apply_redteam_fixpack,
    compose_cde_posture,
    prioritize_control_signals,
    run_composition_pipeline,
    run_redteam_reference_integrity,
    run_redteam_shadow_ownership,
    run_redteam_signal_priority,
)


def _ts(hours_ago: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_inputs() -> dict:
    return {
        "lin": {"artifact_ref": "lin_lineage_report:lin-001", "created_at": _ts(1)},
        "rep": {"artifact_ref": "rep_replay_report:rep-001", "created_at": _ts(1)},
        "evl": {"artifact_ref": "evl_eval_report:evl-001", "created_at": _ts(1)},
        "evd": {"artifact_ref": "evd_evidence_report:evd-001", "created_at": _ts(1)},
        "obs": {"artifact_ref": "obs_observability_report:obs-001", "created_at": _ts(1)},
        "dag": {"artifact_ref": "dag_dependency_report:dag-001", "created_at": _ts(1)},
        "dep": {"artifact_ref": "dep_chain_report:dep-001", "created_at": _ts(1)},
        "slo": {"artifact_ref": "slo_signal:slo-001", "created_at": _ts(1)},
        "cap": {"artifact_ref": "cap_signal:cap-001", "created_at": _ts(1)},
        "qos": {"artifact_ref": "qos_signal:qos-001", "created_at": _ts(1)},
    }


def test_pipeline_aex_to_cde_composition_flow() -> None:
    # Simulates AEX -> TLC -> TPA -> PQX upstream completion by consuming canonical refs only.
    artifacts = run_composition_pipeline(canonical_inputs=_canonical_inputs(), signal_scores={"slo": 0.2, "cap": 0.3, "qos": 0.9})
    assert artifacts["rdx"]["artifact_type"] == "rdx_global_execution_validity_report"
    assert artifacts["prg"]["artifact_type"] == "prg_prioritized_control_signal_bundle"
    assert artifacts["cde"]["artifact_type"] == "cde_composite_posture_bundle"
    assert artifacts["cde"]["outcome"] == "halt"


def test_ownership_boundary_lineage_and_replay_sources_remain_external() -> None:
    artifacts = run_composition_pipeline(canonical_inputs=_canonical_inputs(), signal_scores={"slo": 0.8, "cap": 0.2, "qos": 0.1})
    rdx = artifacts["rdx"]
    assert rdx["lin_lineage_report_ref"].startswith("lin_lineage_report:")
    assert rdx["rep_replay_report_ref"].startswith("rep_replay_report:")
    assert "lineage_complete" not in str(rdx)
    assert "replay_score" not in str(rdx)


def test_missing_lineage_fails_closed() -> None:
    inputs = _canonical_inputs()
    inputs["lin"]["artifact_ref"] = ""
    with pytest.raises(RoadmapOrchestratorError):
        run_composition_pipeline(canonical_inputs=inputs, signal_scores={"slo": 0.4, "cap": 0.4, "qos": 0.4})


def test_missing_replay_fails_closed() -> None:
    inputs = _canonical_inputs()
    inputs["rep"]["artifact_ref"] = ""
    with pytest.raises(RoadmapOrchestratorError):
        run_composition_pipeline(canonical_inputs=inputs, signal_scores={"slo": 0.4, "cap": 0.4, "qos": 0.4})


def test_stale_reference_fails_closed() -> None:
    inputs = _canonical_inputs()
    inputs["lin"]["created_at"] = _ts(72)
    with pytest.raises(RoadmapOrchestratorError):
        run_composition_pipeline(canonical_inputs=inputs, signal_scores={"slo": 0.2, "cap": 0.2, "qos": 0.2})


def test_prg_resolves_conflicting_signals_by_priority() -> None:
    gp = run_composition_pipeline(canonical_inputs=_canonical_inputs(), signal_scores={"slo": 0.1, "cap": 0.2, "qos": 0.3})["rdx"]
    prg = prioritize_control_signals(
        global_posture=gp,
        slo_signal_ref="slo_signal:slo-001",
        cap_signal_ref="cap_signal:cap-001",
        qos_signal_ref="qos_signal:qos-001",
        signal_scores={"slo": 0.7, "cap": 0.6, "qos": 0.2},
    )
    assert prg["ranked_signal_refs"][0] == "slo_signal:slo-001"


def test_long_roadmap_simulation_100_steps() -> None:
    inputs = _canonical_inputs()
    outcomes = []
    for step in range(100):
        scores = {"slo": (step % 7) / 10.0, "cap": (step % 5) / 10.0, "qos": (step % 3) / 10.0}
        artifacts = run_composition_pipeline(canonical_inputs=inputs, signal_scores=scores)
        outcomes.append(artifacts["cde"]["outcome"])
    assert len(outcomes) == 100
    assert set(outcomes).issubset({"continue", "halt", "recut", "escalate"})


def test_redteam_round_1_shadow_ownership_then_fix() -> None:
    rt = run_redteam_shadow_ownership(runtime_source="lineage_complete=True")
    assert rt["status"] == "fail"
    fix = apply_redteam_fixpack(redteam_report=rt)
    assert "reference_only_enforcement" in fix["guards_added"]


def test_redteam_round_2_reference_integrity_then_fix() -> None:
    rt = run_redteam_reference_integrity(refs=["lin_lineage_report:lin-1", "bad-ref"], stale_found=True)
    assert rt["status"] == "fail"
    fix = apply_redteam_fixpack(redteam_report=rt)
    assert fix["status"] == "partial"


def test_redteam_round_3_signal_overload_then_fix() -> None:
    rt = run_redteam_signal_priority(ranked_signal_refs=["slo_signal:s1", "qos_signal:q1"])
    assert rt["status"] == "fail"
    fix = apply_redteam_fixpack(redteam_report=rt)
    assert "halt_visibility_guard" in fix["guards_added"]


def test_compose_cde_uses_references_only() -> None:
    outputs = run_composition_pipeline(canonical_inputs=_canonical_inputs(), signal_scores={"slo": 0.2, "cap": 0.1, "qos": 0.0})
    cde = compose_cde_posture(
        global_posture=outputs["rdx"],
        prioritized_signals=outputs["prg"],
        slo_signal_ref="slo_signal:slo-001",
        cap_signal_ref="cap_signal:cap-001",
        qos_signal_ref="qos_signal:qos-001",
    )
    for key in [
        "rdx_global_execution_validity_report_ref",
        "prg_prioritized_control_signal_bundle_ref",
        "slo_signal_ref",
        "cap_signal_ref",
        "qos_signal_ref",
    ]:
        assert ":" in cde[key]
