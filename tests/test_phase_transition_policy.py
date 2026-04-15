from __future__ import annotations

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.wpg.phase_governance import evaluate_phase_transition


def test_phase_transition_allows_complete_checkpoint() -> None:
    checkpoint = load_example("phase_checkpoint_record")
    registry = load_example("phase_registry")
    result = evaluate_phase_transition(
        phase_checkpoint_record=checkpoint,
        phase_registry=registry,
        requested_action="continue",
        redteam_open_high=0,
        validation_passed=True,
    )
    assert result["decision"] == "ALLOW"
    assert result["may_advance"] is True
    assert result["next_phase"] == "PHASE_B"


def test_phase_transition_blocks_on_open_high_redteam() -> None:
    checkpoint = load_example("phase_checkpoint_record")
    registry = load_example("phase_registry")
    result = evaluate_phase_transition(
        phase_checkpoint_record=checkpoint,
        phase_registry=registry,
        requested_action="continue",
        redteam_open_high=1,
        validation_passed=True,
    )
    assert result["decision"] == "BLOCK"
    assert "high_severity_redteam_open" in result["reason_codes"]
    assert result["may_advance"] is False
