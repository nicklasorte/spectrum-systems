from __future__ import annotations

import pytest

from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline


def test_wpg_pipeline_emits_phase_governance_artifacts() -> None:
    bundle = run_wpg_pipeline(
        {"segments": [{"segment_id": "s1", "speaker": "A", "agency": "FCC", "text": "Can we proceed? Yes we can proceed."}]},
        run_id="phase-aware",
        trace_id="phase-aware",
    )
    assert "phase_transition_policy_result" in bundle["artifact_chain"]
    assert "phase_resume_record" in bundle["artifact_chain"]
    assert "phase_handoff_record" in bundle["artifact_chain"]


def test_wpg_pipeline_blocks_when_checkpoint_blocked() -> None:
    with pytest.raises(Exception):
        run_wpg_pipeline(
            {"segments": [{"segment_id": "s1", "speaker": "A", "agency": "FCC", "text": "Can we proceed?"}]},
            run_id="phase-block",
            trace_id="phase-block",
            phase_checkpoint_record={
                "artifact_type": "phase_checkpoint_record",
                "schema_version": "1.0.0",
                "trace_id": "phase-block",
                "phase_id": "PHASE_A",
                "phase_label": "Core hardening",
                "status": "BLOCKED",
                "blocking_reason_codes": ["required_reviews_open"],
                "required_fix_refs": ["FIX-14"],
                "required_review_refs": ["RTX-10"],
                "completed_step_refs": ["WPG-25"],
                "next_phase": "PHASE_B",
                "resume_ready": False,
                "policy_version": "1.0.0",
                "replay_signature_refs": ["sig:block"]
            },
        )
