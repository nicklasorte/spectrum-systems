from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.failure_diagnosis_engine import (
    build_eval_candidate_artifact,
    build_failure_diagnosis_artifact,
)


def _diagnosis() -> dict:
    return build_failure_diagnosis_artifact(
        failure_source_type="pytest_summary",
        source_artifact_refs=["pytest:sample"],
        failure_payload={
            "observed_failure_summary": "contract behavior changed",
            "failing_tests": [
                {
                    "test_name": "tests/test_contracts.py::test_manifest_registry_alignment",
                    "failure_message": "mismatch",
                    "markers": ["contract_behavior_changed"],
                }
            ],
        },
        emitted_at="2026-04-07T00:00:00Z",
        run_id="run-eval",
        trace_id="trace-eval",
    )


def test_eval_candidate_generated_and_valid() -> None:
    candidate = build_eval_candidate_artifact(failure_diagnosis_artifact=_diagnosis(), trace_refs=["trace-eval"])
    validate_artifact(candidate, "eval_candidate_artifact")


def test_eval_candidate_is_deterministic() -> None:
    one = build_eval_candidate_artifact(failure_diagnosis_artifact=_diagnosis(), trace_refs=["trace-eval"])
    two = build_eval_candidate_artifact(failure_diagnosis_artifact=_diagnosis(), trace_refs=["trace-eval"])
    assert one == two
