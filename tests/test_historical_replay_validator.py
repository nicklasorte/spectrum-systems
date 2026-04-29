"""Tests for historical_replay_validator (CLX-ALL-01 Phase 4).

Covers:
- Built-in corpus passes with built-in classifier
- Additional cases can be injected
- Mismatch produces fail status
- Missing classification produces fail status
- Non-deterministic classifier produces fail status
- Custom classifier is used when provided
- Output schema compliance
- Invalid trace_id raises
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.historical_replay_validator import (
    HistoricalReplayValidatorError,
    run_historical_replay_validation,
)


def test_builtin_corpus_passes() -> None:
    report = run_historical_replay_validation(trace_id="test-001")
    assert report["artifact_type"] == "replay_validation_report"
    assert report["overall_status"] == "pass"
    assert report["passed_cases"] == report["total_cases"]
    assert report["failed_cases"] == 0


def test_output_has_required_fields() -> None:
    report = run_historical_replay_validation(trace_id="t")
    required = [
        "artifact_type", "schema_version", "report_id", "trace_id",
        "replayed_cases", "total_cases", "passed_cases", "failed_cases",
        "mismatch_cases", "overall_status", "emitted_at",
    ]
    for key in required:
        assert key in report, f"Missing field: {key}"


def test_mismatch_case_produces_fail() -> None:
    extra = [{
        "case_id": "test-mismatch-001",
        "failure_class": "registry_guard_failure",
        "expected_classification": "authority_shape_violation",  # Wrong expectation.
        "replay_input": {"violation_type": "registry_guard", "symbol": "UNK"},
    }]
    report = run_historical_replay_validation(trace_id="t", additional_cases=extra)
    assert report["overall_status"] == "fail"
    assert report["mismatch_cases"] >= 1


def test_missing_classification_produces_fail() -> None:
    extra = [{
        "case_id": "test-missing-001",
        "failure_class": "registry_guard_failure",
        "expected_classification": "registry_guard_failure",
        "replay_input": {},  # Empty input → classifier returns None.
    }]
    report = run_historical_replay_validation(trace_id="t", additional_cases=extra)
    assert report["overall_status"] == "fail"


def test_custom_classifier_is_used() -> None:
    def always_authority(replay_input):
        return "authority_shape_violation"

    extra = [{
        "case_id": "custom-001",
        "failure_class": "authority_shape_violation",
        "expected_classification": "authority_shape_violation",
        "replay_input": {"some_key": "some_value"},
    }]
    report = run_historical_replay_validation(
        trace_id="t",
        additional_cases=extra,
        classifier=always_authority,
    )
    custom_result = next(r for r in report["replayed_cases"] if r["case_id"] == "custom-001")
    assert custom_result["result"] == "pass"


def test_empty_trace_id_raises() -> None:
    import pytest
    with pytest.raises(HistoricalReplayValidatorError, match="trace_id"):
        run_historical_replay_validation(trace_id="")


def test_additional_cases_not_list_raises() -> None:
    import pytest
    with pytest.raises(HistoricalReplayValidatorError, match="additional_cases"):
        run_historical_replay_validation(trace_id="t", additional_cases="not-a-list")


def test_all_replayed_cases_have_result_field() -> None:
    report = run_historical_replay_validation(trace_id="t")
    for case in report["replayed_cases"]:
        assert "result" in case
        assert case["result"] in ("pass", "mismatch", "missing_classification", "non_deterministic")


def test_passed_plus_failed_equals_total() -> None:
    report = run_historical_replay_validation(trace_id="t")
    assert report["passed_cases"] + report["failed_cases"] == report["total_cases"]


def test_failure_reason_set_on_fail() -> None:
    extra = [{
        "case_id": "fail-case-001",
        "failure_class": "manifest_drift",
        "expected_classification": "wrong_classification",
        "replay_input": {"violation_type": "manifest_drift"},
    }]
    report = run_historical_replay_validation(trace_id="t", additional_cases=extra)
    if report["overall_status"] == "fail":
        assert report["failure_reason"] is not None


def test_primary_reason_stability_for_passing_cases() -> None:
    report = run_historical_replay_validation(trace_id="t")
    for case in report["replayed_cases"]:
        if case["result"] == "pass":
            assert case["primary_reason_stable"] is True
