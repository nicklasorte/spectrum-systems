"""Tests verifying validator_engine has no silent-pass stubs.

Every registered validator must either fully implement its logic or fail closed
(status='blocked'). No validator may silently return status='pass' when it is
not yet implemented.
"""
from __future__ import annotations

import importlib
import inspect

import pytest

from spectrum_systems.modules.runtime import validator_engine as ve


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_artifact(artifact_id: str = "test-artifact-001") -> dict:
    return {
        "artifact_id": artifact_id,
        "artifact_type": "test_artifact",
    }


def _make_context() -> dict:
    return {
        "runtime_environment": {"version": "1.0.0", "stage": "test"},
    }


# ---------------------------------------------------------------------------
# Stub / silent-pass tests
# ---------------------------------------------------------------------------

class TestNoSilentStubs:
    """Verify the governed stub emits a fail-closed result, not a silent pass."""

    def test_stub_not_implemented_returns_blocked(self) -> None:
        """_stub_not_implemented must return status='blocked', never 'pass'."""
        result = ve._stub_not_implemented("test_validator", {}, {})
        assert result["status"] == "blocked", (
            f"_stub_not_implemented must return 'blocked' but returned '{result['status']}'"
        )

    def test_stub_not_implemented_is_blocking(self) -> None:
        result = ve._stub_not_implemented("test_validator", {}, {})
        assert result["blocking"] is True, "_stub_not_implemented must be blocking=True"

    def test_stub_not_implemented_has_reason_code(self) -> None:
        result = ve._stub_not_implemented("test_validator", {}, {})
        assert "not_implemented" in result["reason_codes"], (
            "reason_codes must include 'not_implemented'"
        )

    def test_stub_not_implemented_has_error_message(self) -> None:
        result = ve._stub_not_implemented("test_validator", {}, {})
        assert result["errors"], "_stub_not_implemented must populate errors list"

    def test_stub_not_implemented_never_silently_passes(self) -> None:
        """Parameterised check: calling the stub with any name must not return pass."""
        for name in ["validate_foo", "validate_bar", "some_validator"]:
            result = ve._stub_not_implemented(name, {}, {})
            assert result["status"] != "pass", (
                f"Stub for '{name}' silently passed — fail-closed violation"
            )


# ---------------------------------------------------------------------------
# Registry completeness tests
# ---------------------------------------------------------------------------

class TestValidatorRegistry:
    """Verify registered validators are implemented, not just stubs."""

    def test_canonical_validators_are_registered(self) -> None:
        registry = ve.get_validator_registry()
        for name in ve.CANONICAL_VALIDATOR_ORDER:
            assert name in registry, f"Canonical validator '{name}' missing from registry"

    def test_registered_validators_are_callable(self) -> None:
        registry = ve.get_validator_registry()
        for name, entry in registry.items():
            assert callable(entry.get("callable_ref")), (
                f"Registry entry '{name}' has non-callable callable_ref"
            )

    def test_no_validator_silently_passes_on_empty_input(self) -> None:
        """Run each registered validator against empty input and verify it doesn't
        silently pass without checking anything meaningful."""
        registry = ve.get_validator_registry()
        silent_passers = []
        for name, entry in registry.items():
            fn = entry.get("callable_ref")
            if fn is None:
                continue
            try:
                result = fn(name, {}, {})
            except Exception:
                continue
            if result.get("status") == "pass" and name in (
                "validate_traceability_integrity",
                "validate_artifact_completeness",
                "validate_cross_artifact_consistency",
            ):
                # These validators check artifact_id and structure; empty dict
                # must fail or warn, not pass.
                silent_passers.append(name)
        assert not silent_passers, (
            f"Validators silently passed on empty input: {silent_passers}"
        )

    def test_runtime_compatibility_fails_without_env(self) -> None:
        """validate_runtime_compatibility must fail when runtime_environment missing."""
        result = ve._validate_runtime_compatibility(
            "validate_runtime_compatibility", {}, {}
        )
        assert result["status"] in ("fail", "blocked"), (
            "runtime_compatibility must fail without runtime_environment in context"
        )

    def test_traceability_integrity_fails_without_artifact_id(self) -> None:
        """validate_traceability_integrity must fail when artifact_id is absent."""
        result = ve._validate_traceability_integrity(
            "validate_traceability_integrity", {}, {}
        )
        assert result["status"] in ("fail", "blocked"), (
            "traceability_integrity must fail when artifact has no artifact_id"
        )

    def test_bundle_contract_fails_on_non_dict(self) -> None:
        result = ve._validate_bundle_contract(
            "validate_bundle_contract", "not_a_dict", {}
        )
        assert result["status"] in ("fail", "blocked")

    def test_schema_conformance_fails_on_non_dict(self) -> None:
        result = ve._validate_schema_conformance(
            "validate_schema_conformance", 42, {}
        )
        assert result["status"] in ("fail", "blocked")


# ---------------------------------------------------------------------------
# run_validators integration
# ---------------------------------------------------------------------------

class TestRunValidators:
    """Integration tests for the canonical run_validators entry point."""

    def test_run_validators_returns_structured_result(self) -> None:
        artifact = _make_minimal_artifact()
        context = _make_context()
        result = ve.run_validators(
            names=["validate_runtime_compatibility", "validate_bundle_contract"],
            artifact=artifact,
            context=context,
        )
        assert "execution_id" in result
        assert "results" in result
        assert "overall_status" in result

    def test_run_validators_unknown_name_blocks(self) -> None:
        """Unknown validator names must not silently pass."""
        artifact = _make_minimal_artifact()
        context = _make_context()
        result = ve.run_validators(
            names=["validate_completely_unknown_xyz"],
            artifact=artifact,
            context=context,
        )
        assert result["overall_status"] == "blocked", (
            "Unknown validator must cause overall_status='blocked'"
        )
