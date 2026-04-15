from __future__ import annotations

from spectrum_systems.modules.wpg.phase_governance import build_phase_checkpoint_record


def test_phase_checkpoint_record_tracks_state() -> None:
    out = build_phase_checkpoint_record(phase_id="PHASE_C", phase_label="Critique memory", status="COMPLETE", trace_id="t1", completed_step_refs=["WPG-35"])
    assert out["phase_id"] == "PHASE_C"
