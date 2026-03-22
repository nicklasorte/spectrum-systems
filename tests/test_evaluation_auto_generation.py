from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402

from spectrum_systems.contracts import load_schema  # noqa: E402
from spectrum_systems.modules.runtime.evaluation_auto_generation import (  # noqa: E402
    EvalCaseGenerationError,
    generate_eval_case_from_failure,
)


def _blocked_context() -> dict:
    return {
        "artifact": {
            "artifact_id": "ART-FAIL-001",
            "trace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        },
        "stage": "synthesis",
        "runtime_environment": "test",
    }


def _blocked_integration() -> dict:
    return {
        "execution_status": "blocked",
        "continuation_allowed": False,
        "publication_blocked": True,
        "decision_blocked": True,
        "execution_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "execution_result": {"actions_taken": []},
    }


def _validate_failure_eval_case(artifact: dict) -> None:
    schema = load_schema("failure_eval_case")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(artifact)


def test_generated_failure_eval_case_is_schema_valid() -> None:
    artifact = generate_eval_case_from_failure(_blocked_context(), _blocked_integration())
    assert artifact["artifact_type"] == "failure_eval_case"
    _validate_failure_eval_case(artifact)


def test_generation_is_deterministic() -> None:
    first = generate_eval_case_from_failure(_blocked_context(), _blocked_integration())
    second = generate_eval_case_from_failure(_blocked_context(), _blocked_integration())
    assert first == second


def test_generation_fail_closed_when_continuation_allowed() -> None:
    integration = _blocked_integration()
    integration["continuation_allowed"] = True
    with pytest.raises(EvalCaseGenerationError):
        generate_eval_case_from_failure(_blocked_context(), integration)


def test_indeterminate_failure_mode_maps_to_indeterminate() -> None:
    integration = _blocked_integration()
    integration["execution_result"] = {
        "actions_taken": [
            {"status": "indeterminate"},
        ]
    }
    artifact = generate_eval_case_from_failure(_blocked_context(), integration)
    assert artifact["expected_output_spec"]["failure_mode"] == "indeterminate"


def test_threshold_breach_failure_mode_maps_when_blocked_flags_set() -> None:
    artifact = generate_eval_case_from_failure(_blocked_context(), _blocked_integration())
    assert artifact["expected_output_spec"]["failure_mode"] == "threshold_breach"
