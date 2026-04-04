from __future__ import annotations

import copy

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.runtime.roadmap_signal_steering import (
    build_artifact_lifecycle_status_record,
    build_drift_detection_record,
    build_roadmap_signal_bundle,
    select_priority_batch,
    steering_enforcement,
)


def test_drift_detection_classification_is_deterministic() -> None:
    findings = [
        {
            "drift_type": "artifact_drift",
            "severity_score": 0.2,
            "affected_component": "artifact_registry",
            "violated_invariant": "lineage_required",
            "reason_codes": ["missing_lineage"],
            "required_action": "restore_lineage",
        },
        {
            "drift_type": "roadmap_drift",
            "severity_score": 0.95,
            "affected_component": "roadmap_selector",
            "violated_invariant": "trust_capability_order",
            "reason_codes": ["capability_gt_trust"],
            "required_action": "block_and_harden",
        },
    ]
    left = build_drift_detection_record(findings_input=findings, created_at="2026-04-04T00:00:00Z", trace_id="trace-ltv-c-test")
    right = build_drift_detection_record(findings_input=findings, created_at="2026-04-04T00:00:00Z", trace_id="trace-ltv-c-test")

    assert left == right
    assert left["severity_summary"]["block"] == 1
    assert left["findings"][0]["drift_type"] == "roadmap_drift"


def test_artifact_aging_reduces_retrieval_weight_for_stale() -> None:
    record = build_artifact_lifecycle_status_record(
        artifact_id="policy-1",
        artifact_type="policy",
        lifecycle_state="stale",
        stale_days=35,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-ltv-c-test",
    )
    assert record["retrieval_weight"] < 1.0
    assert record["trust_penalty"] > 0
    assert "stale_policy_triggers_freeze_warning" in record["warnings"]


def test_roadmap_feeder_outputs_expected_fields() -> None:
    drift = copy.deepcopy(load_example("drift_detection_record"))
    bundle = build_roadmap_signal_bundle(
        roadmap_id="RDX-CANVAS-2026-04-04",
        drift_detection_record=drift,
        override_hotspots=["policy_scope"],
        missing_eval_coverage=["batch-i-replay"],
        replay_mismatches=["replay_result:RPL-100"],
        judgment_conflicts=["precedent_conflict_record:PCF-100"],
        budget_burn_rate=0.81,
        trust_posture_snapshot_ref="trust_posture_snapshot:TPS-1A2B3C4D5E6F",
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-ltv-c-test",
    )
    assert bundle["missing_eval_coverage"] == ["batch-i-replay"]
    assert bundle["drift_severity_summary"]["freeze_candidate"] >= 0
    assert bundle["recommended_priority_adjustments"]


def test_drift_driven_priority_changes_selected_batch() -> None:
    bundle = copy.deepcopy(load_example("roadmap_signal_bundle"))
    bundle["recommended_priority_adjustments"] = [
        {"priority_class": "eval_coverage", "reason": "missing_eval_coverage", "weight": 90, "target_batch_id": "BATCH-J"}
    ]
    selected = select_priority_batch(["BATCH-I", "BATCH-J"], bundle)
    assert selected == "BATCH-J"


def test_freeze_and_block_behavior() -> None:
    freeze_bundle = copy.deepcopy(load_example("roadmap_signal_bundle"))
    block_bundle = copy.deepcopy(load_example("roadmap_signal_bundle"))
    block_bundle["drift_severity_summary"]["block"] = 1

    assert steering_enforcement(freeze_bundle)[0] == "freeze"
    assert steering_enforcement(block_bundle)[0] == "block"


def test_bundle_used_for_handoff_summary_fields() -> None:
    bundle = copy.deepcopy(load_example("roadmap_signal_bundle"))
    assert "top_block_reasons" in bundle
    assert "trust_posture_snapshot_ref" in bundle
