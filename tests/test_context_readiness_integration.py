from __future__ import annotations

from spectrum_systems.modules.wpg.context_governance import evaluate_context_readiness_integration


def test_context_readiness_integration_blocks_when_context_invalid() -> None:
    admission_result = {
        "admission_status": "fail",
        "enforcement_action": "BLOCK",
        "blocking_reasons": ["missing_required_component:slides"],
    }
    readiness = evaluate_context_readiness_integration(admission_result)
    assert readiness["readiness_decision"] == "BLOCK"
    assert "missing_required_component:slides" in readiness["blocking_reasons"]
