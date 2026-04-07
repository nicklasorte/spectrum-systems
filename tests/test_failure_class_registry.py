from __future__ import annotations

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.failure_diagnosis_engine import build_failure_diagnosis_artifact


def test_failure_class_registry_example_is_valid() -> None:
    validate_artifact(load_example("failure_class_registry"), "failure_class_registry")


def test_unknown_failure_escalates() -> None:
    registry = load_example("failure_class_registry")
    assert registry["classes"]["unknown_failure"]["escalation_required"] is True


def test_failure_mapping_is_deterministic() -> None:
    kwargs = {
        "failure_source_type": "pytest_summary",
        "source_artifact_refs": ["pytest:sample"],
        "failure_payload": {
            "observed_failure_summary": "no class marker",
            "failing_tests": [{"test_name": "t::x", "failure_message": "boom", "markers": []}],
        },
        "emitted_at": "2026-04-07T00:00:00Z",
        "run_id": "run-a",
        "trace_id": "trace-a",
    }
    one = build_failure_diagnosis_artifact(**kwargs)
    two = build_failure_diagnosis_artifact(**kwargs)
    assert one["primary_root_cause"] == "unknown_failure"
    assert one == two
