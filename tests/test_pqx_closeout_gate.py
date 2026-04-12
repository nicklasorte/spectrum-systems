from __future__ import annotations

from spectrum_systems.modules.runtime.pqx_closeout_gate import evaluate_pqx_closeout_gate


def test_pqx_closeout_gate_passes_with_required_artifacts_and_consumers() -> None:
    result = evaluate_pqx_closeout_gate(
        emitted_artifact_types=[
            "pqx_slice_execution_record",
            "pqx_bundle_execution_record",
            "pqx_execution_closure_record",
        ],
        ci_gate_consumers=["pqx_hardening_bundle"],
        downstream_consumers=["SEL", "CDE"],
    )
    assert result["closeout_status"] == "pass"


def test_pqx_closeout_gate_fails_when_artifacts_or_consumers_missing() -> None:
    result = evaluate_pqx_closeout_gate(
        emitted_artifact_types=["pqx_slice_execution_record"],
        ci_gate_consumers=[],
        downstream_consumers=["SEL"],
    )
    assert result["closeout_status"] == "fail"
    assert "missing_required_pqx_hardening_artifacts" in result["fail_reasons"]
