"""
Guardrail tests — tests/transcript_pipeline/test_no_unchecked_routing.py

Enforces that route_with_gate_evidence is the ONLY public routing entrypoint
exported from tlc_router and that the unchecked internal function is not
accessible as a public symbol.

FAIL IF:
- route_artifact is still a public attribute of the module
- _route_artifact_unchecked appears in __all__
- route_with_gate_evidence is absent from __all__
"""
from __future__ import annotations

import pytest

from spectrum_systems.modules.orchestration import tlc_router
from spectrum_systems.modules.orchestration.tlc_router import (
    ArtifactRoutingError,
    route_with_gate_evidence,
)


def test_route_artifact_not_public() -> None:
    assert not hasattr(tlc_router, "route_artifact"), (
        "route_artifact must not be a public attribute; use route_with_gate_evidence"
    )


def test_unchecked_not_in_all() -> None:
    assert "_route_artifact_unchecked" not in tlc_router.__all__


def test_route_with_gate_evidence_in_all() -> None:
    assert "route_with_gate_evidence" in tlc_router.__all__


def test_route_artifact_not_in_all() -> None:
    assert "route_artifact" not in tlc_router.__all__


def test_route_with_gate_evidence_is_callable() -> None:
    assert callable(route_with_gate_evidence)


def test_governed_routing_accepts_valid_gate_evidence() -> None:
    result = route_with_gate_evidence(
        {"artifact_type": "transcript_artifact"},
        {"eval_summary_id": "guardrail-test-001", "gate_status": "passed_gate"},
    )
    assert result == "context_bundle"


def test_governed_routing_blocks_without_gate_evidence() -> None:
    with pytest.raises(ArtifactRoutingError) as exc_info:
        route_with_gate_evidence({"artifact_type": "transcript_artifact"}, None)  # type: ignore[arg-type]
    assert "MISSING_GATE_EVIDENCE" in exc_info.value.reason_codes


def test_governed_routing_blocks_failed_gate() -> None:
    with pytest.raises(ArtifactRoutingError) as exc_info:
        route_with_gate_evidence(
            {"artifact_type": "transcript_artifact"},
            {"eval_summary_id": "guardrail-test-002", "gate_status": "failed_gate"},
        )
    assert "GATE_EVIDENCE_NOT_ROUTABLE" in exc_info.value.reason_codes


def test_governed_routing_blocks_missing_gate() -> None:
    with pytest.raises(ArtifactRoutingError) as exc_info:
        route_with_gate_evidence(
            {"artifact_type": "transcript_artifact"},
            {"eval_summary_id": "guardrail-test-003", "gate_status": "missing_gate"},
        )
    assert "GATE_EVIDENCE_NOT_ROUTABLE" in exc_info.value.reason_codes
