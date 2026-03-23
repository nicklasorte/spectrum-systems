"""Tests for BN.8 Validator Execution Engine."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

import pytest

from spectrum_systems.modules.runtime.validator_engine import (  # noqa: E402
    CANONICAL_VALIDATOR_ORDER,
    SCHEMA_VERSION,
    get_validator_registry,
    list_registered_validators,
    resolve_validator,
    run_validators,
    summarize_validator_execution,
    validate_validator_result,
)
from spectrum_systems.modules.runtime.control_executor import (  # noqa: E402
    execute_control_signals,
)
from spectrum_systems.modules.runtime.trace_engine import start_trace  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUIRED_VALIDATOR_NAMES = [
    "validate_runtime_compatibility",
    "validate_bundle_contract",
    "validate_schema_conformance",
    "validate_traceability_integrity",
    "validate_artifact_completeness",
    "validate_cross_artifact_consistency",
]


def _artifact() -> Dict[str, Any]:
    return {"artifact_id": "ART-001", "payload": {"x": 1}}


def _ctx(**overrides: Any) -> Dict[str, Any]:
    trace_id = overrides.pop(
        "trace_id",
        start_trace({"source": "validator-engine-tests", "run_id": "run-test-001"}),
    )
    c = {
        "artifact": _artifact(),
        "stage": "synthesis",
        "runtime_environment": "test",
        "trace_id": trace_id,
        "run_id": "run-test-001",
        "source_artifact_id": "ART-001",
    }
    c.update(overrides)
    return c


def _base_signals(**overrides: Any) -> Dict[str, Any]:
    base = {
        "continuation_mode": "continue",
        "required_inputs": [],
        "required_validators": [],
        "repair_actions": [],
        "rerun_recommended": False,
        "human_review_required": False,
        "escalation_required": False,
        "publication_allowed": True,
        "decision_grade_allowed": True,
        "traceability_required": False,
        "control_signal_reason_codes": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. Registry lists all required validators
# ---------------------------------------------------------------------------

def test_registry_contains_all_required_validators():
    registry = get_validator_registry()
    for name in _REQUIRED_VALIDATOR_NAMES:
        assert name in registry, f"Missing required validator: {name}"


def test_registry_entries_have_required_metadata_keys():
    registry = get_validator_registry()
    required_keys = {"validator_name", "callable_ref", "description", "stage_applicability", "blocking_by_default", "output_schema"}
    for name, entry in registry.items():
        missing = required_keys - set(entry.keys())
        assert not missing, f"Registry entry '{name}' missing keys: {missing}"


# ---------------------------------------------------------------------------
# 2. Resolve known validator
# ---------------------------------------------------------------------------

def test_resolve_known_validator_returns_callable_and_metadata():
    fn, entry = resolve_validator("validate_schema_conformance")
    assert callable(fn)
    assert entry["validator_name"] == "validate_schema_conformance"
    assert "description" in entry


# ---------------------------------------------------------------------------
# 3. Unknown validator fails closed
# ---------------------------------------------------------------------------

def test_resolve_unknown_validator_raises_key_error():
    with pytest.raises(KeyError, match="not registered"):
        resolve_validator("validate_not_a_real_validator")


def test_run_validators_unknown_name_returns_blocked():
    result = run_validators(["validate_not_registered"], _ctx())
    assert result["overall_status"] == "blocked"
    assert "validate_not_registered" in result["validators_failed"]
    assert "unknown_validator" in result["failure_reason_codes"]


# ---------------------------------------------------------------------------
# 4. Canonical execution order enforced
# ---------------------------------------------------------------------------

def test_canonical_order_is_defined():
    assert len(CANONICAL_VALIDATOR_ORDER) == 6
    assert CANONICAL_VALIDATOR_ORDER[0] == "validate_runtime_compatibility"
    assert CANONICAL_VALIDATOR_ORDER[-1] == "validate_cross_artifact_consistency"


def test_run_validators_normalises_to_canonical_order():
    # Request in reversed canonical order — expect canonical order in output.
    requested = list(reversed(CANONICAL_VALIDATOR_ORDER))
    result = run_validators(requested, _ctx())
    assert result["validators_run"] == CANONICAL_VALIDATOR_ORDER


def test_caller_provided_order_ignored_in_favour_of_canonical():
    # Provide a non-canonical order with just two validators.
    arbitrary_order = ["validate_schema_conformance", "validate_runtime_compatibility"]
    canonical_expected = ["validate_runtime_compatibility", "validate_schema_conformance"]
    result = run_validators(arbitrary_order, _ctx())
    assert result["validators_run"] == canonical_expected


# ---------------------------------------------------------------------------
# 5. Successful validator run produces pass result
# ---------------------------------------------------------------------------

def test_all_registered_validators_pass_with_valid_artifact():
    result = run_validators(list(CANONICAL_VALIDATOR_ORDER), _ctx())
    assert result["overall_status"] == "pass"
    assert result["validators_passed"] == list(CANONICAL_VALIDATOR_ORDER)
    assert result["validators_failed"] == []


def test_run_validators_result_has_required_top_level_fields():
    result = run_validators(["validate_schema_conformance"], _ctx())
    required = {"execution_id", "validators_requested", "validators_run", "validators_passed",
                "validators_failed", "validator_results", "overall_status", "failure_reason_codes",
                "evaluated_at", "schema_version"}
    assert required.issubset(set(result.keys()))


def test_schema_version_constant_present():
    result = run_validators(["validate_schema_conformance"], _ctx())
    assert result["schema_version"] == SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 6. Failing validator produces blocked overall result
# ---------------------------------------------------------------------------

def test_failing_validator_produces_fail_or_blocked_overall():
    # No artifact_id → traceability fails.
    ctx = _ctx(artifact={"payload": {"x": 1}})
    result = run_validators(["validate_traceability_integrity"], ctx)
    assert result["overall_status"] in ("fail", "blocked")
    assert "validate_traceability_integrity" in result["validators_failed"]


def test_missing_runtime_environment_causes_failure():
    ctx = {"artifact": _artifact()}  # no runtime_environment
    result = run_validators(["validate_runtime_compatibility"], ctx)
    assert result["overall_status"] in ("fail", "blocked")
    assert "validate_runtime_compatibility" in result["validators_failed"]


# ---------------------------------------------------------------------------
# 7. Malformed validator result fails closed
# ---------------------------------------------------------------------------

def test_malformed_validator_result_fails_closed(monkeypatch):
    """Patch a validator callable to return a malformed result."""
    import spectrum_systems.modules.runtime.validator_engine as ve

    original = ve._REGISTRY["validate_schema_conformance"]["callable_ref"]
    ve._REGISTRY["validate_schema_conformance"]["callable_ref"] = lambda n, a, c: {"bad_key": "no_structure"}
    try:
        result = run_validators(["validate_schema_conformance"], _ctx())
        assert result["overall_status"] == "blocked"
        assert "validate_schema_conformance" in result["validators_failed"]
        assert "malformed_validator_result" in result["failure_reason_codes"]
    finally:
        ve._REGISTRY["validate_schema_conformance"]["callable_ref"] = original


# ---------------------------------------------------------------------------
# 8. Validator exception fails closed
# ---------------------------------------------------------------------------

def test_validator_exception_fails_closed(monkeypatch):
    """Patch a validator callable to raise an exception."""
    import spectrum_systems.modules.runtime.validator_engine as ve

    def _raise(n, a, c):
        raise RuntimeError("boom")

    original = ve._REGISTRY["validate_bundle_contract"]["callable_ref"]
    ve._REGISTRY["validate_bundle_contract"]["callable_ref"] = _raise
    try:
        result = run_validators(["validate_bundle_contract"], _ctx())
        assert result["overall_status"] == "blocked"
        assert "validate_bundle_contract" in result["validators_failed"]
        assert "validator_exception" in result["failure_reason_codes"]
    finally:
        ve._REGISTRY["validate_bundle_contract"]["callable_ref"] = original


# ---------------------------------------------------------------------------
# 9. Not-implemented validator does not silently pass
# ---------------------------------------------------------------------------

def test_not_implemented_stub_does_not_silently_pass():
    """Register a stub validator and confirm it fails closed."""
    import spectrum_systems.modules.runtime.validator_engine as ve
    from spectrum_systems.modules.runtime.validator_engine import _stub_not_implemented

    # Temporarily add a stub
    ve._REGISTRY["validate_stub_test"] = {
        "validator_name": "validate_stub_test",
        "callable_ref": _stub_not_implemented,
        "description": "Test stub",
        "stage_applicability": ["*"],
        "blocking_by_default": True,
        "output_schema": None,
    }
    try:
        result = run_validators(["validate_stub_test"], _ctx())
        # Stub must block, not pass
        assert result["overall_status"] == "blocked"
        assert "validate_stub_test" in result["validators_failed"]
        assert "not_implemented" in result["failure_reason_codes"]
    finally:
        ve._REGISTRY.pop("validate_stub_test", None)


# ---------------------------------------------------------------------------
# 10. Integration with control_executor preserved (BN.6 backward compatibility)
# ---------------------------------------------------------------------------

def test_control_executor_uses_validator_engine_for_known_validators():
    cs = _base_signals(required_validators=["validate_schema_conformance"])
    result = execute_control_signals(cs, _ctx())
    assert result["execution_status"] == "success"
    assert "validate_schema_conformance" in result["validators_run"]


def test_control_executor_unknown_validator_still_blocks():
    cs = _base_signals(required_validators=["validate_not_registered"])
    result = execute_control_signals(cs, _ctx())
    assert result["execution_status"] == "blocked"
    assert "validate_not_registered" in result["validators_failed"]


def test_control_executor_all_canonical_validators_success():
    cs = _base_signals(required_validators=list(CANONICAL_VALIDATOR_ORDER))
    result = execute_control_signals(cs, _ctx())
    assert result["execution_status"] == "success"
    assert len(result["validators_run"]) == len(CANONICAL_VALIDATOR_ORDER)


# ---------------------------------------------------------------------------
# 11. Structured result schema validation
# ---------------------------------------------------------------------------

def test_run_validators_result_passes_schema_validation():
    from jsonschema import Draft202012Validator
    from spectrum_systems.contracts import load_schema

    schema = load_schema("validator_execution_result")
    validator = Draft202012Validator(schema)
    result = run_validators(list(CANONICAL_VALIDATOR_ORDER), _ctx())
    errors = list(validator.iter_errors(result))
    assert errors == [], f"Schema validation failed: {errors}"


def test_validator_outputs_single_canonical_shape_for_all_paths():
    from jsonschema import Draft202012Validator
    from spectrum_systems.contracts import load_schema

    schema = load_schema("validator_execution_result")
    validator = Draft202012Validator(schema)

    valid_result = run_validators(["validate_schema_conformance"], _ctx())
    malformed_input_result = run_validators(["validate_bundle_contract"], _ctx(artifact="not-a-dict"))
    missing_trace_result = run_validators(["validate_schema_conformance"], _ctx(trace_id="not-a-real-trace-id"))

    for output in (valid_result, malformed_input_result, missing_trace_result):
        errors = list(validator.iter_errors(output))
        assert errors == [], f"Schema validation failed for output: {errors}"

    canonical_keys = set(valid_result.keys())
    assert set(malformed_input_result.keys()) == canonical_keys
    assert set(missing_trace_result.keys()) == canonical_keys


def test_validator_never_returns_unvalidated_artifact(monkeypatch):
    import spectrum_systems.modules.runtime.validator_engine as ve

    def _invalid_schema():
        return {
            "type": "object",
            "required": ["nonexistent_required_field"],
            "properties": {},
            "additionalProperties": True,
        }

    monkeypatch.setattr(ve, "_load_validator_execution_result_schema", _invalid_schema)
    with pytest.raises(ValueError, match="failed schema validation"):
        run_validators(["validate_schema_conformance"], _ctx())


def test_validate_validator_result_accepts_well_formed_result():
    well_formed = {
        "validator_name": "test_validator",
        "status": "pass",
        "blocking": True,
        "reason_codes": [],
        "warnings": [],
        "errors": [],
        "details": {},
    }
    assert validate_validator_result(well_formed) == []


def test_validate_validator_result_rejects_missing_keys():
    bad = {"validator_name": "test", "status": "pass"}  # missing required keys
    errors = validate_validator_result(bad)
    assert len(errors) > 0


def test_validate_validator_result_rejects_invalid_status():
    bad = {
        "validator_name": "test",
        "status": "unknown_status",
        "blocking": True,
        "reason_codes": [],
        "warnings": [],
        "errors": [],
        "details": {},
    }
    errors = validate_validator_result(bad)
    assert any("invalid status" in e for e in errors)


def test_validate_validator_result_rejects_non_dict():
    errors = validate_validator_result("not a dict", validator_name="x")
    assert len(errors) == 1
    assert "non-dict" in errors[0]


# ---------------------------------------------------------------------------
# 12. Repeated runs are deterministic
# ---------------------------------------------------------------------------

def test_repeated_runs_produce_deterministic_results():
    ctx = _ctx()
    validators = list(CANONICAL_VALIDATOR_ORDER)
    first = run_validators(validators, ctx)
    second = run_validators(validators, ctx)
    # execution_id is UUID-random; compare everything else
    assert first["overall_status"] == second["overall_status"]
    assert first["validators_run"] == second["validators_run"]
    assert first["validators_passed"] == second["validators_passed"]
    assert first["validators_failed"] == second["validators_failed"]
    assert first["failure_reason_codes"] == second["failure_reason_codes"]
    assert first["validators_requested"] == second["validators_requested"]


def test_control_executor_execution_is_deterministic():
    cs = _base_signals(required_validators=["validate_schema_conformance"])
    first = execute_control_signals(cs, _ctx())
    second = execute_control_signals(cs, _ctx())
    assert first["execution_status"] == second["execution_status"]
    assert first["validators_run"] == second["validators_run"]
    assert first["validators_failed"] == second["validators_failed"]


# ---------------------------------------------------------------------------
# 13. Caller-provided order ignored in favour of canonical order
# ---------------------------------------------------------------------------

def test_reversed_request_order_still_runs_canonical_order():
    reversed_order = list(reversed(CANONICAL_VALIDATOR_ORDER))
    result = run_validators(reversed_order, _ctx())
    assert result["validators_run"] == CANONICAL_VALIDATOR_ORDER
    assert result["validators_requested"] == reversed_order  # original preserved


# ---------------------------------------------------------------------------
# 14. First blocking validator is identifiable
# ---------------------------------------------------------------------------

def test_first_blocking_validator_identifiable_in_summary():
    ctx = _ctx(artifact={"payload": {"x": 1}})  # no artifact_id → traceability fails
    result = run_validators(list(CANONICAL_VALIDATOR_ORDER), ctx)
    summary = summarize_validator_execution(result)
    assert "first_blocking_failure" in summary


def test_first_blocking_validator_is_correct(monkeypatch):
    """With a bad artifact (missing artifact_id), traceability should block first."""
    ctx = _ctx(artifact={"payload": {}})  # no artifact_id, has payload
    # validate_runtime_compatibility passes (env present)
    # validate_bundle_contract passes (dict)
    # validate_schema_conformance passes (dict)
    # validate_traceability_integrity FAILS (no artifact_id)
    result = run_validators(list(CANONICAL_VALIDATOR_ORDER), ctx)
    vrs = result.get("validator_results") or []
    first_blocked = next(
        (vr["validator_name"] for vr in vrs if vr.get("blocking") and vr.get("status") != "pass"),
        None,
    )
    assert first_blocked == "validate_traceability_integrity"


# ---------------------------------------------------------------------------
# 15. Summaries are deterministic
# ---------------------------------------------------------------------------

def test_summaries_are_deterministic():
    result = run_validators(list(CANONICAL_VALIDATOR_ORDER), _ctx())
    summary1 = summarize_validator_execution(result)
    summary2 = summarize_validator_execution(result)
    assert summary1 == summary2


def test_summary_contains_expected_fields():
    result = run_validators(["validate_schema_conformance"], _ctx())
    summary = summarize_validator_execution(result)
    assert "overall_status" in summary
    assert "validators_run" in summary
    assert "validators_failed" in summary
    assert "first_blocking_failure" in summary


# ---------------------------------------------------------------------------
# 16. Backward compatibility with BN.6 control execution flow
# ---------------------------------------------------------------------------

def test_bn6_execution_result_schema_still_valid():
    from spectrum_systems.modules.runtime.control_executor import validate_execution_result
    cs = _base_signals(required_validators=list(CANONICAL_VALIDATOR_ORDER))
    result = execute_control_signals(cs, _ctx())
    assert validate_execution_result(result) == []


def test_bn6_continue_mode_still_works():
    cs = _base_signals(required_validators=["validate_schema_conformance"])
    result = execute_control_signals(cs, _ctx())
    assert result["execution_status"] == "success"
    assert result["validators_run"] == ["validate_schema_conformance"]


def test_bn6_missing_validator_still_blocks():
    cs = _base_signals(required_validators=["validate_not_registered"])
    result = execute_control_signals(cs, _ctx())
    assert result["execution_status"] == "blocked"
    assert "validate_not_registered" in result["validators_failed"]


def test_list_registered_validators_order():
    """list_registered_validators must return canonical names first, in order."""
    names = list_registered_validators()
    canonical_in_list = [n for n in names if n in CANONICAL_VALIDATOR_ORDER]
    assert canonical_in_list == CANONICAL_VALIDATOR_ORDER


def test_execution_id_is_unique_across_runs():
    result1 = run_validators(["validate_schema_conformance"], _ctx())
    result2 = run_validators(["validate_schema_conformance"], _ctx())
    assert result1["execution_id"] != result2["execution_id"]


def test_event_vocabulary_consistent():
    import spectrum_systems.modules.runtime.validator_engine as ve

    for event_type in ve.GOVERNED_EVENT_TYPES:
        assert event_type == event_type.lower()
        assert " " not in event_type
