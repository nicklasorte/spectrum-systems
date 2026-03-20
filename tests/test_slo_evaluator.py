"""Tests for BH–BJ SLO Evaluator (slo_evaluator.py).

Covers:
- healthy / degraded / breached SLO status
- SLI mapping from validator execution results
- threshold edge cases
- fail-closed behaviour on malformed input
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.slo_evaluator import (  # noqa: E402
    map_validator_results_to_slis,
    compute_slo_status,
    _GOVERNED_SLIS,
    _HEALTHY_THRESHOLD,
    _DEGRADED_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vr(name: str, status: str) -> Dict[str, Any]:
    return {
        "validator_name": name,
        "status": status,
        "blocking": True,
        "reason_codes": [],
        "warnings": [],
        "errors": [],
        "details": {},
    }


def _make_ve_result(
    requested: List[str],
    passed: List[str],
    failed: List[str],
) -> Dict[str, Any]:
    """Build a minimal ValidatorExecutionResult for testing."""
    validator_results = []
    for name in requested:
        status = "pass" if name in passed else "fail"
        validator_results.append(_make_vr(name, status))
    return {
        "execution_id": "test-exec-001",
        "validators_requested": requested,
        "validators_run": passed + failed,
        "validators_passed": passed,
        "validators_failed": failed,
        "validator_results": validator_results,
        "overall_status": "pass" if not failed else "fail",
        "failure_reason_codes": [],
        "evaluated_at": "2026-01-01T00:00:00+00:00",
        "schema_version": "1.0.0",
    }


_ALL_VALIDATORS = [
    "validate_runtime_compatibility",
    "validate_bundle_contract",
    "validate_schema_conformance",
    "validate_traceability_integrity",
    "validate_artifact_completeness",
    "validate_cross_artifact_consistency",
]


# ---------------------------------------------------------------------------
# map_validator_results_to_slis
# ---------------------------------------------------------------------------

class TestMapValidatorResultsToSlis:
    def test_all_passing_returns_ones(self):
        ve = _make_ve_result(_ALL_VALIDATORS, _ALL_VALIDATORS, [])
        slis = map_validator_results_to_slis(ve)
        assert set(slis.keys()) == _GOVERNED_SLIS
        assert slis["completeness"] == 1.0
        assert slis["timeliness"] == 1.0
        assert slis["traceability"] == 1.0
        assert slis["traceability_integrity"] == 1.0

    def test_all_failing_returns_zeros(self):
        ve = _make_ve_result(_ALL_VALIDATORS, [], _ALL_VALIDATORS)
        slis = map_validator_results_to_slis(ve)
        assert slis["completeness"] == 0.0
        assert slis["timeliness"] == 0.0
        assert slis["traceability"] == 0.0
        assert slis["traceability_integrity"] == 0.0

    def test_traceability_integrity_fail_gives_zero(self):
        passed = [v for v in _ALL_VALIDATORS if v != "validate_traceability_integrity"]
        failed = ["validate_traceability_integrity"]
        ve = _make_ve_result(_ALL_VALIDATORS, passed, failed)
        slis = map_validator_results_to_slis(ve)
        assert slis["traceability_integrity"] == 0.0

    def test_completeness_partial(self):
        requested = _ALL_VALIDATORS
        passed = _ALL_VALIDATORS[:3]
        failed = _ALL_VALIDATORS[3:]
        ve = _make_ve_result(requested, passed, failed)
        slis = map_validator_results_to_slis(ve)
        assert slis["completeness"] == pytest.approx(3 / 6)

    def test_empty_validators_requested(self):
        ve = _make_ve_result([], [], [])
        slis = map_validator_results_to_slis(ve)
        assert slis["completeness"] == 0.0
        assert slis["timeliness"] == 0.0
        assert slis["traceability"] == 0.0
        assert slis["traceability_integrity"] == 0.0

    def test_returns_all_four_slis(self):
        ve = _make_ve_result(_ALL_VALIDATORS, _ALL_VALIDATORS, [])
        slis = map_validator_results_to_slis(ve)
        assert "completeness" in slis
        assert "timeliness" in slis
        assert "traceability" in slis
        assert "traceability_integrity" in slis

    def test_fail_closed_on_none_input(self):
        slis = map_validator_results_to_slis(None)  # type: ignore[arg-type]
        assert slis["completeness"] == 0.0
        assert slis["traceability_integrity"] == 0.0

    def test_fail_closed_on_non_dict_input(self):
        slis = map_validator_results_to_slis("bad")  # type: ignore[arg-type]
        assert slis["completeness"] == 0.0

    def test_values_in_range(self):
        ve = _make_ve_result(_ALL_VALIDATORS[:4], _ALL_VALIDATORS[:2], _ALL_VALIDATORS[2:4])
        slis = map_validator_results_to_slis(ve)
        for v in slis.values():
            assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# compute_slo_status
# ---------------------------------------------------------------------------

class TestComputeSloStatus:
    def _healthy_slis(self) -> Dict[str, float]:
        return {
            "completeness": 1.0,
            "timeliness": 1.0,
            "traceability": 1.0,
            "traceability_integrity": 1.0,
        }

    def _degraded_slis(self) -> Dict[str, float]:
        # All above degraded threshold but below healthy
        return {
            "completeness": 0.90,
            "timeliness": 0.90,
            "traceability": 0.90,
            "traceability_integrity": 0.90,
        }

    def _breached_slis(self) -> Dict[str, float]:
        # At least one below degraded threshold
        return {
            "completeness": 0.5,
            "timeliness": 1.0,
            "traceability": 1.0,
            "traceability_integrity": 1.0,
        }

    def test_healthy(self):
        result = compute_slo_status(self._healthy_slis())
        assert result["slo_status"] == "healthy"
        assert result["violations"] == []

    def test_degraded(self):
        result = compute_slo_status(self._degraded_slis())
        assert result["slo_status"] == "degraded"
        assert result["violations"] == []

    def test_breached(self):
        result = compute_slo_status(self._breached_slis())
        assert result["slo_status"] == "breached"
        assert "completeness" in result["violations"]

    def test_scores_included(self):
        slis = self._healthy_slis()
        result = compute_slo_status(slis)
        assert result["scores"] == slis

    def test_custom_thresholds_healthy(self):
        slis = {k: 0.80 for k in _GOVERNED_SLIS}
        result = compute_slo_status(slis, thresholds={"healthy": 0.75, "degraded": 0.60})
        assert result["slo_status"] == "healthy"

    def test_custom_thresholds_breached(self):
        slis = {k: 0.80 for k in _GOVERNED_SLIS}
        result = compute_slo_status(slis, thresholds={"healthy": 0.95, "degraded": 0.85})
        assert result["slo_status"] == "breached"

    def test_all_zero_slis_breached(self):
        slis = {k: 0.0 for k in _GOVERNED_SLIS}
        result = compute_slo_status(slis)
        assert result["slo_status"] == "breached"
        assert len(result["violations"]) == 4

    def test_fail_closed_on_bad_input(self):
        result = compute_slo_status("not-a-dict")  # type: ignore[arg-type]
        assert result["slo_status"] == "breached"

    def test_multiple_violations_listed(self):
        slis = {
            "completeness": 0.0,
            "timeliness": 0.0,
            "traceability": 1.0,
            "traceability_integrity": 1.0,
        }
        result = compute_slo_status(slis)
        assert "completeness" in result["violations"]
        assert "timeliness" in result["violations"]
        assert "traceability" not in result["violations"]

    def test_exactly_at_healthy_threshold_is_healthy(self):
        slis = {k: _HEALTHY_THRESHOLD for k in _GOVERNED_SLIS}
        result = compute_slo_status(slis)
        assert result["slo_status"] == "healthy"

    def test_just_below_healthy_threshold_is_degraded(self):
        slis = {k: _HEALTHY_THRESHOLD - 0.01 for k in _GOVERNED_SLIS}
        result = compute_slo_status(slis)
        assert result["slo_status"] == "degraded"

    def test_exactly_at_degraded_threshold_is_degraded(self):
        slis = {k: _DEGRADED_THRESHOLD for k in _GOVERNED_SLIS}
        result = compute_slo_status(slis)
        assert result["slo_status"] == "degraded"

    def test_just_below_degraded_threshold_is_breached(self):
        slis = {
            "completeness": _DEGRADED_THRESHOLD - 0.01,
            "timeliness": 1.0,
            "traceability": 1.0,
            "traceability_integrity": 1.0,
        }
        result = compute_slo_status(slis)
        assert result["slo_status"] == "breached"
