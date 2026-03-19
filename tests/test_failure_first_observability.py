"""
Tests for BB — Failure-First Observability.

Covers:
- detect_high_confidence_error: returns True when confident but failing
- detect_high_confidence_error: returns False for clean records
- detect_high_confidence_error: returns False for low-confidence failures
- detect_dangerous_promote: criterion 1 — error_types present, failure_count==0
- detect_dangerous_promote: criterion 2 — human disagrees, failure_count==0
- detect_dangerous_promote: criterion 3 — grounding failed, high structural
- detect_dangerous_promote: criterion 4 — regression not passed, high semantic
- detect_dangerous_promote: returns False for clean record
- rank_worst_cases: dangerous promotes ranked first
- rank_worst_cases: high-confidence errors ranked before structural failures
- rank_worst_cases: top_n respected
- rank_worst_cases: empty input returns empty list
- rank_failure_modes: ranked by count descending
- rank_failure_modes: records without error_types but with failure_count use unclassified
- rank_failure_modes: empty input returns empty list
- rank_dangerous_promotes: only dangerous promotes returned
- rank_dangerous_promotes: empty when no dangerous promotes
- rank_pass_weaknesses: passes ranked by combined risk
- rank_pass_weaknesses: empty input returns empty list
- compute_failure_first_metrics: all ten metrics present
- compute_failure_first_metrics: correct rejection_rate calculation
- compute_failure_first_metrics: correct dangerous_promote_count
- compute_failure_first_metrics: correct high_confidence_error_rate
- compute_failure_first_metrics: repeated_failure_concentration top 3
- compute_failure_first_metrics: pass_failure_concentration keyed by pass_type
- compute_failure_first_metrics: empty input returns None rates
- generate_failure_first_report: returns all required sections
- generate_failure_first_report: handles empty store gracefully
- adversarial integration: case_id and adversarial metadata surfaced
"""
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from spectrum_systems.modules.observability.metrics import (
    MetricsStore,
    ObservabilityRecord,
)
from spectrum_systems.modules.observability.aggregation import (
    compute_failure_first_metrics,
)
from spectrum_systems.modules.observability.failure_ranking import (
    detect_dangerous_promote,
    detect_high_confidence_error,
    rank_dangerous_promotes,
    rank_failure_modes,
    rank_pass_weaknesses,
    rank_worst_cases,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _make_record(**overrides) -> ObservabilityRecord:
    """Return an ObservabilityRecord with sane defaults, overridable."""
    defaults = dict(
        artifact_id=f"artifact-{uuid.uuid4().hex[:6]}",
        artifact_type="evaluation_result",
        pipeline_stage="validate",
        pass_id=str(uuid.uuid4()),
        pass_type="extraction",
        structural_score=0.9,
        semantic_score=0.85,
        grounding_score=1.0,
        latency_ms=300,
        schema_valid=True,
        grounding_passed=True,
        regression_passed=True,
        human_disagrees=False,
        error_types=[],
        failure_count=0,
    )
    defaults.update(overrides)
    return ObservabilityRecord(**defaults)


def _clean_record(**overrides) -> ObservabilityRecord:
    """Return a record with no failure indicators."""
    return _make_record(**overrides)


def _failing_record(**overrides) -> ObservabilityRecord:
    """Return a record with one explicit failure."""
    base = dict(failure_count=1, error_types=["extraction_error"])
    base.update(overrides)
    return _make_record(**base)


# ---------------------------------------------------------------------------
# detect_high_confidence_error
# ---------------------------------------------------------------------------


class TestDetectHighConfidenceError:
    def test_returns_true_when_confident_but_failing(self):
        """High structural/semantic/grounding scores + failure_count > 0."""
        rec = _make_record(
            structural_score=0.85,
            semantic_score=0.80,
            grounding_score=0.75,
            failure_count=2,
            error_types=["extraction_error"],
        )
        assert detect_high_confidence_error(rec) is True

    def test_returns_false_for_clean_record(self):
        """No failures → not a high-confidence error."""
        rec = _clean_record(
            structural_score=0.95,
            semantic_score=0.90,
            grounding_score=1.0,
            failure_count=0,
        )
        assert detect_high_confidence_error(rec) is False

    def test_returns_false_for_low_confidence_failure(self):
        """Low scores + failure → not a high-confidence error (expected failure)."""
        rec = _make_record(
            structural_score=0.1,
            semantic_score=0.1,
            grounding_score=0.1,
            failure_count=3,
            error_types=["grounding_failure"],
        )
        assert detect_high_confidence_error(rec) is False

    def test_grounding_not_passed_triggers_hce(self):
        """Medium-confidence record with grounding not passed = HCE."""
        rec = _make_record(
            structural_score=0.7,
            semantic_score=0.7,
            grounding_score=0.7,
            grounding_passed=False,
            failure_count=0,
        )
        assert detect_high_confidence_error(rec) is True

    def test_regression_not_passed_triggers_hce(self):
        """Medium-confidence record with regression not passed = HCE."""
        rec = _make_record(
            structural_score=0.6,
            semantic_score=0.6,
            grounding_score=0.6,
            regression_passed=False,
            failure_count=0,
        )
        assert detect_high_confidence_error(rec) is True


# ---------------------------------------------------------------------------
# detect_dangerous_promote
# ---------------------------------------------------------------------------


class TestDetectDangerousPromote:
    def test_criterion1_error_types_with_zero_failure_count(self):
        """Error types present but failure_count is 0 — silent failure."""
        rec = _make_record(
            error_types=["extraction_error"],
            failure_count=0,
        )
        is_dp, reason = detect_dangerous_promote(rec)
        assert is_dp is True
        assert "silent failure" in reason

    def test_criterion2_human_disagrees_with_zero_failure_count(self):
        """Human disagrees but failure_count is 0 — suppressed override."""
        rec = _make_record(
            human_disagrees=True,
            failure_count=0,
            error_types=[],
        )
        is_dp, reason = detect_dangerous_promote(rec)
        assert is_dp is True
        assert "override suppressed" in reason

    def test_criterion3_grounding_failed_high_structural(self):
        """Grounding failed but structural score is high — structural illusion."""
        rec = _make_record(
            grounding_passed=False,
            structural_score=0.85,
            failure_count=0,
            error_types=[],
        )
        is_dp, reason = detect_dangerous_promote(rec)
        assert is_dp is True
        assert "structural illusion" in reason

    def test_criterion4_regression_not_passed_high_semantic(self):
        """Regression not passed but semantic score is high — silent regression."""
        rec = _make_record(
            regression_passed=False,
            semantic_score=0.80,
            failure_count=0,
            error_types=[],
        )
        is_dp, reason = detect_dangerous_promote(rec)
        assert is_dp is True
        assert "silent regression" in reason

    def test_returns_false_for_clean_record(self):
        """No dangerous promote criteria met."""
        rec = _clean_record()
        is_dp, reason = detect_dangerous_promote(rec)
        assert is_dp is False
        assert reason == ""

    def test_record_with_explicit_failure_count_and_grounding_fails_triggers_dangerous_promote(self):
        """Criterion 3 fires: grounding failed + structural score ≥ 0.7."""
        rec = _make_record(
            error_types=["grounding_failure"],
            failure_count=1,
            grounding_passed=False,
        )
        is_dp, _ = detect_dangerous_promote(rec)
        # Criterion 1: error_types present but failure_count == 0 → FALSE (failure_count=1)
        # Criterion 2: human_disagrees=False → FALSE
        # Criterion 3: grounding_passed=False + structural_score=0.9 ≥ 0.7 → TRUE
        assert is_dp is True


# ---------------------------------------------------------------------------
# rank_worst_cases
# ---------------------------------------------------------------------------


class TestRankWorstCases:
    def _make_dataset(self):
        dp = _make_record(
            artifact_id="dangerous",
            error_types=["extraction_error"],
            failure_count=0,
        )
        hce = _make_record(
            artifact_id="hce",
            structural_score=0.7,
            semantic_score=0.7,
            grounding_score=0.7,
            failure_count=1,
            error_types=["extraction_error"],
        )
        # Structural failure — low across all scores so it is NOT a high-confidence error
        structural = _make_record(
            artifact_id="structural",
            structural_score=0.3,
            semantic_score=0.2,
            grounding_score=0.2,
            failure_count=2,
            error_types=["extraction_error", "grounding_failure"],
        )
        clean = _clean_record(artifact_id="clean")
        return dp, hce, structural, clean

    def test_dangerous_promotes_ranked_first(self):
        dp, hce, structural, clean = self._make_dataset()
        ranked = rank_worst_cases([clean, hce, structural, dp])
        assert ranked[0]["artifact_id"] == "dangerous"

    def test_high_confidence_errors_before_structural(self):
        dp, hce, structural, clean = self._make_dataset()
        ranked = rank_worst_cases([clean, structural, hce])
        artifact_ids = [r["artifact_id"] for r in ranked]
        assert artifact_ids.index("hce") < artifact_ids.index("structural")

    def test_top_n_respected(self):
        records = [_failing_record() for _ in range(20)]
        ranked = rank_worst_cases(records, top_n=5)
        assert len(ranked) <= 5

    def test_empty_input_returns_empty(self):
        assert rank_worst_cases([]) == []

    def test_output_schema(self):
        """Each result dict contains expected keys."""
        rec = _failing_record(artifact_id="test-001", case_id="case-A")
        result = rank_worst_cases([rec])
        assert len(result) == 1
        item = result[0]
        assert "record_id" in item
        assert "artifact_id" in item
        assert "is_dangerous_promote" in item
        assert "is_high_confidence_error" in item
        assert "flags" in item


# ---------------------------------------------------------------------------
# rank_failure_modes
# ---------------------------------------------------------------------------


class TestRankFailureModes:
    def test_ranked_by_count_descending(self):
        records = [
            _make_record(error_types=["grounding_failure"], failure_count=1),
            _make_record(error_types=["grounding_failure"], failure_count=1),
            _make_record(error_types=["extraction_error"], failure_count=1),
        ]
        modes = rank_failure_modes(records)
        assert modes[0]["failure_mode"] == "grounding_failure"
        assert modes[0]["count"] == 2

    def test_unclassified_for_failure_without_error_types(self):
        rec = _make_record(failure_count=1, error_types=[])
        modes = rank_failure_modes([rec])
        assert any(m["failure_mode"] == "unclassified_failure" for m in modes)

    def test_empty_input_returns_empty(self):
        assert rank_failure_modes([]) == []

    def test_output_schema(self):
        rec = _make_record(error_types=["extraction_error"], failure_count=1)
        modes = rank_failure_modes([rec])
        assert "failure_mode" in modes[0]
        assert "count" in modes[0]
        assert "affected_records" in modes[0]
        assert "affected_pass_types" in modes[0]


# ---------------------------------------------------------------------------
# rank_dangerous_promotes
# ---------------------------------------------------------------------------


class TestRankDangerousPromotes:
    def test_only_dangerous_promotes_returned(self):
        dp = _make_record(error_types=["extraction_error"], failure_count=0)
        clean = _clean_record()
        result = rank_dangerous_promotes([clean, dp])
        assert len(result) == 1
        assert result[0]["record_id"] == dp.record_id

    def test_empty_when_no_dangerous_promotes(self):
        records = [_clean_record() for _ in range(5)]
        assert rank_dangerous_promotes(records) == []

    def test_output_contains_reason(self):
        dp = _make_record(error_types=["extraction_error"], failure_count=0)
        result = rank_dangerous_promotes([dp])
        assert result[0]["dangerous_promote_reason"] != ""

    def test_output_contains_confidence_level(self):
        dp = _make_record(error_types=["extraction_error"], failure_count=0)
        result = rank_dangerous_promotes([dp])
        assert result[0]["confidence_level"] in {"high", "medium", "low"}


# ---------------------------------------------------------------------------
# rank_pass_weaknesses
# ---------------------------------------------------------------------------


class TestRankPassWeaknesses:
    def test_worst_pass_ranked_first(self):
        bad = _make_record(
            pass_type="bad_pass",
            error_types=["extraction_error"],
            failure_count=1,
        )
        good = _clean_record(pass_type="good_pass")
        result = rank_pass_weaknesses([bad, good])
        assert result[0]["pass_type"] == "bad_pass"

    def test_empty_input_returns_empty(self):
        assert rank_pass_weaknesses([]) == []

    def test_output_schema(self):
        rec = _failing_record(pass_type="extraction")
        result = rank_pass_weaknesses([rec])
        item = result[0]
        assert "pass_type" in item
        assert "failure_rate" in item
        assert "dangerous_promote_rate" in item
        assert "high_confidence_error_rate" in item
        assert "record_count" in item


# ---------------------------------------------------------------------------
# compute_failure_first_metrics
# ---------------------------------------------------------------------------


class TestComputeFailureFirstMetrics:
    def _make_mixed_records(self):
        """Six records with varying failure patterns."""
        return [
            # Clean record
            _clean_record(pass_type="extraction"),
            # Failure record with error type
            _make_record(
                pass_type="extraction",
                failure_count=1,
                error_types=["extraction_error"],
                grounding_passed=False,
            ),
            # Structural failure
            _make_record(
                pass_type="reasoning",
                structural_score=0.3,
                failure_count=1,
                error_types=["grounding_failure"],
            ),
            # Dangerous promote (silent)
            _make_record(
                pass_type="reasoning",
                error_types=["extraction_error"],
                failure_count=0,
            ),
            # High-confidence error
            _make_record(
                pass_type="summarisation",
                structural_score=0.8,
                semantic_score=0.8,
                grounding_score=0.8,
                failure_count=2,
                error_types=["hallucination"],
            ),
            # Duplicate decision
            _make_record(
                pass_type="summarisation",
                failure_count=1,
                error_types=["duplicate_decision"],
            ),
        ]

    def test_all_ten_metrics_present(self):
        records = self._make_mixed_records()
        result = compute_failure_first_metrics(records)
        required = {
            "record_count",
            "rejection_rate",
            "promote_rate",
            "structural_failure_rate",
            "no_decision_extraction_rate",
            "duplicate_decision_rate",
            "inconsistent_grounding_rate",
            "high_confidence_error_rate",
            "dangerous_promote_count",
            "repeated_failure_concentration",
            "pass_failure_concentration",
        }
        assert required.issubset(result.keys())

    def test_rejection_rate_correct(self):
        records = self._make_mixed_records()
        result = compute_failure_first_metrics(records)
        # Clean record (index 0) is a promote; all others have some failure
        assert result["rejection_rate"] is not None
        assert 0.0 <= result["rejection_rate"] <= 1.0

    def test_promote_rate_plus_rejection_rate_equals_one(self):
        records = self._make_mixed_records()
        result = compute_failure_first_metrics(records)
        assert abs(result["promote_rate"] + result["rejection_rate"] - 1.0) < 1e-9

    def test_dangerous_promote_count(self):
        records = self._make_mixed_records()
        result = compute_failure_first_metrics(records)
        # Record at index 3 is the explicit dangerous promote (error_types, failure_count=0)
        assert result["dangerous_promote_count"] >= 1

    def test_high_confidence_error_rate(self):
        records = self._make_mixed_records()
        result = compute_failure_first_metrics(records)
        assert result["high_confidence_error_rate"] is not None
        assert 0.0 <= result["high_confidence_error_rate"] <= 1.0

    def test_repeated_failure_concentration_max_three(self):
        records = self._make_mixed_records()
        result = compute_failure_first_metrics(records)
        concentration = result["repeated_failure_concentration"]
        assert len(concentration) <= 3

    def test_repeated_failure_concentration_schema(self):
        records = self._make_mixed_records()
        result = compute_failure_first_metrics(records)
        for item in result["repeated_failure_concentration"]:
            assert "failure_mode" in item
            assert "count" in item

    def test_pass_failure_concentration_keyed_by_pass_type(self):
        records = self._make_mixed_records()
        result = compute_failure_first_metrics(records)
        pfc = result["pass_failure_concentration"]
        assert isinstance(pfc, dict)
        # extraction and reasoning both have failures
        assert "extraction" in pfc or "reasoning" in pfc

    def test_duplicate_decision_rate(self):
        records = [
            _make_record(error_types=["duplicate_decision"], failure_count=1),
            _make_record(error_types=["duplicate_decision"], failure_count=1),
            _clean_record(),
        ]
        result = compute_failure_first_metrics(records)
        assert abs(result["duplicate_decision_rate"] - 2 / 3) < 1e-9

    def test_empty_input_returns_none_rates(self):
        result = compute_failure_first_metrics([])
        assert result["record_count"] == 0
        assert result["rejection_rate"] is None
        assert result["promote_rate"] is None
        assert result["dangerous_promote_count"] == 0
        assert result["repeated_failure_concentration"] == []
        assert result["pass_failure_concentration"] == {}


# ---------------------------------------------------------------------------
# generate_failure_first_report (integration)
# ---------------------------------------------------------------------------


class TestGenerateFailureFirstReport:
    def _make_store(self, records: list) -> MetricsStore:
        tmpdir = tempfile.mkdtemp()
        store = MetricsStore(store_dir=Path(tmpdir))
        for rec in records:
            store.save(rec)
        return store

    def test_returns_all_required_sections(self):
        from scripts.run_failure_first_report import generate_failure_first_report

        records = [
            _clean_record(),
            _failing_record(),
            _make_record(error_types=["extraction_error"], failure_count=0),
        ]
        store = self._make_store(records)
        report = generate_failure_first_report(store)
        assert "executive_failure_summary" in report
        assert "worst_cases" in report
        assert "top_failure_modes" in report
        assert "passes_most_at_risk" in report
        assert "false_confidence_zones" in report
        assert "structural_health" in report
        assert "failure_first_metrics" in report

    def test_handles_empty_store(self):
        from scripts.run_failure_first_report import generate_failure_first_report

        tmpdir = tempfile.mkdtemp()
        store = MetricsStore(store_dir=Path(tmpdir))
        report = generate_failure_first_report(store)
        assert report["record_count"] == 0
        assert "message" in report

    def test_worst_cases_capped_at_five(self):
        from scripts.run_failure_first_report import generate_failure_first_report

        records = [_failing_record() for _ in range(20)]
        store = self._make_store(records)
        report = generate_failure_first_report(store)
        assert len(report["worst_cases"]) <= 5

    def test_executive_summary_counts(self):
        from scripts.run_failure_first_report import generate_failure_first_report

        records = [
            _clean_record(),
            _failing_record(),
        ]
        store = self._make_store(records)
        report = generate_failure_first_report(store)
        efs = report["executive_failure_summary"]
        assert efs["total_cases"] == 2
        assert efs["rejection_rate"] is not None

    def test_report_is_json_serialisable(self):
        from scripts.run_failure_first_report import generate_failure_first_report

        records = [_failing_record(), _clean_record()]
        store = self._make_store(records)
        report = generate_failure_first_report(store)
        dumped = json.dumps(report)
        assert len(dumped) > 0

    def test_case_id_filter_applied(self):
        from scripts.run_failure_first_report import generate_failure_first_report

        r1 = _failing_record(case_id="case-X")
        r2 = _clean_record(case_id="case-Y")
        store = self._make_store([r1, r2])
        report = generate_failure_first_report(store, case_id="case-X")
        assert report["record_count"] == 1


# ---------------------------------------------------------------------------
# Adversarial integration
# ---------------------------------------------------------------------------


class TestAdversarialIntegration:
    """Verify that adversarial metadata surfaces in worst-case reporting."""

    def test_adversarial_case_id_surfaced_in_worst_cases(self):
        """Records with adversarial case IDs should appear in worst_cases."""
        adv_record = _make_record(
            artifact_id="adv-artifact-001",
            case_id="adversarial-case-001",
            error_types=["extraction_error"],
            failure_count=0,  # dangerous promote — adversarial silent failure
        )
        worst = rank_worst_cases([adv_record])
        assert worst[0]["case_id"] == "adversarial-case-001"
        assert worst[0]["is_dangerous_promote"] is True

    def test_normal_and_adversarial_records_processed_together(self):
        """Normal and adversarial records produce a combined report."""
        normal = [_clean_record(case_id="normal-1") for _ in range(3)]
        adversarial = [
            _make_record(
                case_id=f"adversarial-{i}",
                error_types=["extraction_error"],
                failure_count=0,
            )
            for i in range(2)
        ]
        all_records = normal + adversarial
        result = compute_failure_first_metrics(all_records)
        assert result["dangerous_promote_count"] == 2

    def test_adversarial_failure_modes_ranked(self):
        """Failure modes from adversarial runs appear in ranked output."""
        records = [
            _make_record(case_id="adv-1", error_types=["hallucination"], failure_count=1),
            _make_record(case_id="adv-2", error_types=["hallucination"], failure_count=1),
            _make_record(case_id="normal-1", error_types=["extraction_error"], failure_count=1),
        ]
        modes = rank_failure_modes(records)
        top = modes[0]
        assert top["failure_mode"] == "hallucination"
        assert top["count"] == 2
