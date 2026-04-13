from spectrum_systems.modules.runtime.drx import (
    build_drift_response_plan,
    detect_drift_signals,
    emit_eval_expansion_record,
    emit_invariant_gap_record,
)
from spectrum_systems.modules.runtime.jsx import (
    build_active_judgment_set,
    detect_judgment_conflicts,
    supersede_judgment,
)


def test_jsx_active_set_supersession_and_conflict_detection() -> None:
    judgments = [
        {"judgment_id": "J1", "status": "active", "policy_key": "k", "policy_value": "a"},
        {"judgment_id": "J2", "status": "deprecated", "policy_key": "k", "policy_value": "b"},
    ]
    active = build_active_judgment_set(judgments=judgments)
    assert active["active_judgment_ids"] == ["J1"]
    sup = supersede_judgment(old_judgment_id="J1", new_judgment_id="J3", reason="new evidence")
    assert sup["new_judgment_id"] == "J3"
    conflict = detect_judgment_conflicts(judgments=judgments)
    assert conflict["has_conflicts"] is True


def test_drx_drift_and_artifact_generation() -> None:
    signal = detect_drift_signals(metrics={"override_rate": 0.2}, thresholds={"override_rate": 0.1})
    assert signal["drift_detected"] is True
    plan = build_drift_response_plan(signal_record=signal, runbook_ref="docs/runbooks/drift.md")
    assert plan["action_count"] == 1
    gaps = emit_invariant_gap_record(cycle_id="MNT-1", gaps=["missing_trace_link"])
    expansion = emit_eval_expansion_record(cycle_id="MNT-1", expansion_targets=["ctx_staleness_gate"])
    assert gaps["cycle_id"] == expansion["cycle_id"]
