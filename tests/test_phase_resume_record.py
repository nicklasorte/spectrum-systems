from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.wpg.phase_governance import (
    build_phase_checkpoint_record,
    build_phase_resume_record,
)


def test_phase_resume_record_is_governed() -> None:
    checkpoint = build_phase_checkpoint_record(
        phase_id="PHASE_C",
        phase_label="Critique memory",
        status="FIX_REQUIRED",
        trace_id="trace-1",
        completed_step_refs=["WPG-35"],
        blocking_reason_codes=["retrieval_confidence_low"],
    )
    resume = build_phase_resume_record(
        checkpoint=checkpoint,
        next_executable_slice="FIX-17",
        remaining_required_slices=["FIX-17", "PHASE-C-VAL"],
    )
    validate_artifact(resume, "phase_resume_record")
    assert resume["next_executable_slice"] == "FIX-17"
