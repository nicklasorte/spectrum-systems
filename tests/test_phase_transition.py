from __future__ import annotations

from spectrum_systems.modules.wpg.phase_governance import build_phase_checkpoint_record, default_phase_registry, evaluate_phase_transition


def test_phase_transition_blocks_on_open_redteam() -> None:
    checkpoint = build_phase_checkpoint_record(phase_id="PHASE_C", phase_label="Critique memory", status="COMPLETE", trace_id="t1", completed_step_refs=["WPG-35"])
    result = evaluate_phase_transition(phase_checkpoint_record=checkpoint, phase_registry=default_phase_registry("t1"), requested_action="continue", redteam_open_high=1)
    assert result["decision"] == "BLOCK"
