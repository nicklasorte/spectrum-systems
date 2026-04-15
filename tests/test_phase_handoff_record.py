from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.wpg.phase_governance import (
    build_phase_checkpoint_record,
    build_phase_handoff_record,
    build_phase_resume_record,
)


def test_phase_handoff_tracks_blockers() -> None:
    checkpoint = build_phase_checkpoint_record(
        phase_id="PHASE_D",
        phase_label="Judgment and learning",
        status="BLOCKED",
        trace_id="trace-2",
        completed_step_refs=["JDG-03"],
        blocking_reason_codes=["phase_validation_failed"],
    )
    resume = build_phase_resume_record(
        checkpoint=checkpoint,
        next_executable_slice="FIX-18",
        remaining_required_slices=["FIX-18"],
    )
    handoff = build_phase_handoff_record(
        checkpoint=checkpoint,
        resume_record=resume,
        handoff_notes=["Address JDG rationale calibration regressions."],
    )
    validate_artifact(handoff, "phase_handoff_record")
    assert handoff["blockers"] == ["phase_validation_failed"]
