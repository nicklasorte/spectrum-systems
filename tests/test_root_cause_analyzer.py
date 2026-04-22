"""Tests for Phase 4.2: RootCauseAnalyzer."""

import pytest

from spectrum_systems.debugging.root_cause_analyzer import (
    CODE_BUG,
    EXTERNAL_DEPENDENCY,
    INPUT_CORRUPTION,
    RESOURCE_LIMIT,
    RootCauseAnalyzer,
)


@pytest.fixture()
def analyzer():
    return RootCauseAnalyzer()


# ---------------------------------------------------------------------------
# test_input_corruption_detected
# ---------------------------------------------------------------------------
def test_input_corruption_detected(analyzer):
    artifact = {"failure_id": "f-1", "reason_code": "VALIDATION_ERROR"}
    cause, detail = analyzer.analyze_failure(artifact, [], {})
    assert cause == INPUT_CORRUPTION
    assert "validation" in detail["cause"].lower()


# ---------------------------------------------------------------------------
# test_code_bug_detected
# ---------------------------------------------------------------------------
def test_code_bug_detected(analyzer):
    artifact = {
        "failure_id": "f-2",
        "reason_code": "EXECUTION_ERROR",
        "stack_trace": "Traceback ...\nAssertionError: expected True",
    }
    cause, detail = analyzer.analyze_failure(artifact, [], {})
    assert cause == CODE_BUG
    assert "stack_trace" in detail


# ---------------------------------------------------------------------------
# test_resource_limit_detected
# ---------------------------------------------------------------------------
def test_resource_limit_detected(analyzer):
    artifact = {"failure_id": "f-3", "reason_code": "TIMEOUT"}
    system_state = {"available_memory": 512}
    cause, detail = analyzer.analyze_failure(artifact, [], system_state)
    assert cause == RESOURCE_LIMIT
    assert detail["available_memory_mb"] == 512


# ---------------------------------------------------------------------------
# test_external_dependency_detected
# ---------------------------------------------------------------------------
def test_external_dependency_detected(analyzer):
    artifact = {"failure_id": "f-4", "reason_code": "UNKNOWN"}
    cause, detail = analyzer.analyze_failure(artifact, [], {})
    assert cause == EXTERNAL_DEPENDENCY


# ---------------------------------------------------------------------------
# test_rca_report_generated
# ---------------------------------------------------------------------------
def test_rca_report_generated(analyzer):
    artifact = {"failure_id": "f-5", "reason_code": "VALIDATION_ERROR"}
    cause, detail = analyzer.analyze_failure(artifact, [], {})
    assert "cause" in detail
    assert "suggestion" in detail
    assert "failure_id" in detail


# ---------------------------------------------------------------------------
# test_rca_within_5_minutes (latency guard — RCA must be synchronous)
# ---------------------------------------------------------------------------
def test_rca_within_5_minutes(analyzer):
    import time

    artifact = {"failure_id": "f-6", "reason_code": "VALIDATION_ERROR"}
    start = time.perf_counter()
    analyzer.analyze_failure(artifact, [], {})
    elapsed_s = time.perf_counter() - start
    # Must complete synchronously in well under 5 minutes
    assert elapsed_s < 1.0
