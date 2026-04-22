"""Unit tests for FailClosedEnforcer — Phase 2.1 (8 tests + RT-2.1 coverage)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spectrum_systems.execution.fail_closed_enforcer import (
    MANDATORY_FAILURE_FIELDS,
    FailClosedEnforcer,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_enforcer(tmp_path):
    return FailClosedEnforcer(system_id="WPG", storage_dir=str(tmp_path / "failures"))


# ---------------------------------------------------------------------------
# Test 1: ValueError produces failure artifact with all mandatory fields
# ---------------------------------------------------------------------------


def test_value_error_produces_failure_artifact(tmp_enforcer):
    artifact = tmp_enforcer.enforce_failure_artifact(
        ValueError("bad input"), trace_id="TRC-TEST-001"
    )
    for field in MANDATORY_FAILURE_FIELDS:
        assert field in artifact, f"Mandatory field missing: {field}"
        assert artifact[field] is not None


# ---------------------------------------------------------------------------
# Test 2: Failure artifact has trace_id linking back to input
# ---------------------------------------------------------------------------


def test_trace_id_propagated(tmp_enforcer):
    artifact = tmp_enforcer.enforce_failure_artifact(
        RuntimeError("boom"), trace_id="TRC-TRACE-LINK-42"
    )
    assert artifact["trace_id"] == "TRC-TRACE-LINK-42"


# ---------------------------------------------------------------------------
# Test 3: Error classification maps known types to reason codes
# ---------------------------------------------------------------------------


def test_error_classification(tmp_enforcer):
    cases = [
        (ValueError("x"), "VALIDATION_ERROR"),
        (TypeError("x"), "TYPE_ERROR"),
        (KeyError("x"), "MISSING_FIELD"),
        (FileNotFoundError("x"), "RESOURCE_NOT_FOUND"),
        (RuntimeError("x"), "RUNTIME_ERROR"),
    ]
    for exc, expected_code in cases:
        artifact = tmp_enforcer.enforce_failure_artifact(exc, trace_id="TRC-CLS")
        assert artifact["reason_code"] == expected_code, f"Wrong code for {type(exc).__name__}"


# ---------------------------------------------------------------------------
# Test 4: Unknown exception type → UNCLASSIFIED_ERROR
# ---------------------------------------------------------------------------


def test_unknown_exception_classified_as_unclassified(tmp_enforcer):
    class WeirdError(Exception):
        pass

    artifact = tmp_enforcer.enforce_failure_artifact(WeirdError("strange"), trace_id="TRC-WEIRD")
    assert artifact["reason_code"] == "UNCLASSIFIED_ERROR"


# ---------------------------------------------------------------------------
# Test 5: Failure is stored immediately (file exists on disk)
# ---------------------------------------------------------------------------


def test_failure_stored_immediately(tmp_path):
    storage = str(tmp_path / "stored")
    enforcer = FailClosedEnforcer(system_id="TPA", storage_dir=storage)
    artifact = enforcer.enforce_failure_artifact(ValueError("store me"), trace_id="TRC-STORE")
    failure_id = artifact["failure_id"]
    expected_path = Path(storage) / f"{failure_id}.json"
    assert expected_path.exists(), "Failure artifact not persisted to disk"
    with open(expected_path) as fh:
        loaded = json.load(fh)
    assert loaded["failure_id"] == failure_id


# ---------------------------------------------------------------------------
# Test 6: Multiple exceptions on same trace → separate failure artifacts
# ---------------------------------------------------------------------------


def test_multiple_exceptions_same_trace_get_separate_artifacts(tmp_enforcer):
    trace_id = "TRC-MULTI-FAIL"
    a1 = tmp_enforcer.enforce_failure_artifact(ValueError("first"), trace_id=trace_id)
    a2 = tmp_enforcer.enforce_failure_artifact(TypeError("second"), trace_id=trace_id)
    assert a1["failure_id"] != a2["failure_id"]
    assert a1["trace_id"] == a2["trace_id"] == trace_id


# ---------------------------------------------------------------------------
# Test 7: validate_failure_artifact accepts valid artifact
# ---------------------------------------------------------------------------


def test_validate_accepts_valid_artifact(tmp_enforcer):
    artifact = tmp_enforcer.enforce_failure_artifact(RuntimeError("ok"), trace_id="TRC-VALID")
    ok, violations = tmp_enforcer.validate_failure_artifact(artifact)
    assert ok, f"Expected valid artifact, got violations: {violations}"
    assert violations == []


# ---------------------------------------------------------------------------
# Test 8: validate_failure_artifact rejects artifact missing mandatory fields
# ---------------------------------------------------------------------------


def test_validate_rejects_missing_mandatory_fields(tmp_enforcer):
    bad_artifact: Dict = {
        "failure_id": "FAIL-ABCDEF",
        "reason_code": "RUNTIME_ERROR",
        # trace_id missing
        "timestamp": "2026-01-01T00:00:00+00:00",
        # system_id missing
        # human_readable missing
    }
    ok, violations = tmp_enforcer.validate_failure_artifact(bad_artifact)
    assert not ok
    assert "trace_id" in violations
    assert "system_id" in violations
    assert "human_readable" in violations


# ---------------------------------------------------------------------------
# RT-2.1: Exception in WPG system → failure artifact carries correct system_id
# ---------------------------------------------------------------------------


def test_rt_wpg_exception_carries_system_id():
    with tempfile.TemporaryDirectory() as tmp:
        enforcer = FailClosedEnforcer(system_id="WPG", storage_dir=tmp)
        artifact = enforcer.enforce_failure_artifact(RuntimeError("WPG crash"), trace_id="TRC-WPG")
        assert artifact["system_id"] == "WPG"


# ---------------------------------------------------------------------------
# RT-2.1: Context is preserved in artifact
# ---------------------------------------------------------------------------


def test_rt_context_preserved_in_artifact(tmp_enforcer):
    ctx = {"input_artifact_id": "ART-001", "step": "eval"}
    artifact = tmp_enforcer.enforce_failure_artifact(
        ValueError("ctx test"), trace_id="TRC-CTX", context=ctx
    )
    assert artifact["context"]["input_artifact_id"] == "ART-001"
    assert artifact["context"]["step"] == "eval"
