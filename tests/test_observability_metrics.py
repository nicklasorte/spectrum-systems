"""
Tests for the Observability + Metrics Layer (Prompt AP).

Covers:
- ObservabilityRecord: construction with all required fields
- ObservabilityRecord: validate_against_schema returns no errors for valid record
- ObservabilityRecord: validate_against_schema reports errors for invalid records
- ObservabilityRecord: to_dict / from_dict round-trip
- ObservabilityRecord.from_eval_result: correct field mapping from EvalResult
- ObservabilityRecord.from_feedback: human_disagrees always True
- ObservabilityRecord.from_feedback: "unclear" failure_type normalised
- MetricsStore: save and load round-trip
- MetricsStore: load non-existent raises FileNotFoundError
- MetricsStore: list returns all records
- MetricsStore: list with filters
- MetricsStore: aggregate returns summary dict
- MetricsStore: save validates record and raises ValueError on bad record
- compute_pass_metrics: empty list returns empty result
- compute_pass_metrics: aggregates by pass_type
- compute_error_distribution: counts by error_type
- compute_error_distribution: identifies top error type
- compute_human_disagreement: overall and per-pass rates
- compute_grounding_failure_rate: overall failure rate
- compute_latency_stats: mean, p95, max
- compute_weakest_passes: ordered by failure rate
- compare_runs: deltas computed correctly
- save_snapshot / load_snapshot: round-trip
- EvalRunner: emits ObservabilityRecord when metrics_store configured
- EvalRunner: no emission when metrics_store is None (no-op)
- create_feedback_from_review: emits ObservabilityRecord when metrics_store provided
- Schema: observability_record.schema.json validates valid records
- Schema: observability_record.schema.json rejects records missing required fields
"""
from __future__ import annotations

import json
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from spectrum_systems.modules.observability.metrics import (
    MetricsStore,
    ObservabilityRecord,
)
from spectrum_systems.modules.observability.aggregation import (
    compute_error_distribution,
    compute_grounding_failure_rate,
    compute_human_disagreement,
    compute_latency_stats,
    compute_pass_metrics,
    compute_weakest_passes,
)
from spectrum_systems.modules.observability.trends import (
    compare_runs,
    load_snapshot,
    save_snapshot,
)
from spectrum_systems.modules.evaluation.error_taxonomy import ErrorType, EvalError
from spectrum_systems.modules.evaluation.eval_runner import (
    EvalResult,
    EvalRunner,
    LatencySummary,
)
from spectrum_systems.modules.feedback.human_feedback import HumanFeedbackRecord
from spectrum_systems.modules.feedback.feedback_ingest import create_feedback_from_review


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_PATH = _REPO_ROOT / "contracts" / "schemas" / "observability_record.schema.json"


def _make_record(**overrides) -> ObservabilityRecord:
    defaults = dict(
        artifact_id="artifact-001",
        artifact_type="evaluation_result",
        pipeline_stage="validate",
        pass_id="pass-abc",
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


def _make_eval_result(**overrides) -> EvalResult:
    defaults = dict(
        case_id="case_001",
        pass_fail=True,
        structural_score=0.9,
        semantic_score=0.85,
        grounding_score=1.0,
        latency_summary=LatencySummary(
            per_pass_latency={"extraction": 200},
            total_latency_ms=200,
        ),
        error_types=[],
        schema_valid=True,
        regression_detected=False,
    )
    defaults.update(overrides)
    return EvalResult(**defaults)


def _make_feedback_record(**overrides) -> HumanFeedbackRecord:
    defaults = dict(
        artifact_id="artifact-001",
        artifact_type="working_paper",
        target_level="claim",
        target_id="claim-abc",
        reviewer_id="reviewer-1",
        reviewer_role="engineer",
        action="accept",
        original_text="The system operates at 5 GHz.",
        rationale="Matches transcript verbatim.",
        source_of_truth="transcript",
        failure_type="unclear",
        severity="low",
        golden_dataset=False,
        prompts=False,
        retrieval_memory=False,
    )
    defaults.update(overrides)
    return HumanFeedbackRecord(**defaults)


def _store_in_tmpdir() -> MetricsStore:
    tmp = tempfile.mkdtemp()
    return MetricsStore(store_dir=Path(tmp))


# ---------------------------------------------------------------------------
# ObservabilityRecord construction and validation
# ---------------------------------------------------------------------------

class TestObservabilityRecord:
    def test_construction_valid(self):
        rec = _make_record()
        assert rec.artifact_id == "artifact-001"
        assert rec.pass_type == "extraction"
        assert rec.structural_score == 0.9

    def test_auto_uuid_and_timestamp(self):
        rec = _make_record()
        assert rec.record_id  # non-empty
        assert rec.timestamp  # non-empty

    def test_validate_valid_record_no_errors(self):
        rec = _make_record()
        errors = rec.validate_against_schema()
        assert errors == []

    def test_validate_empty_artifact_id(self):
        rec = _make_record(artifact_id="")
        errors = rec.validate_against_schema()
        assert any("artifact_id" in e for e in errors)

    def test_validate_invalid_pipeline_stage(self):
        rec = _make_record(pipeline_stage="invalid_stage")
        errors = rec.validate_against_schema()
        assert any("pipeline_stage" in e for e in errors)

    def test_validate_score_out_of_range(self):
        rec = _make_record(structural_score=1.5)
        errors = rec.validate_against_schema()
        assert any("structural_score" in e for e in errors)

    def test_validate_negative_latency(self):
        rec = _make_record(latency_ms=-1)
        errors = rec.validate_against_schema()
        assert any("latency_ms" in e for e in errors)

    def test_validate_unknown_error_type(self):
        rec = _make_record(error_types=["not_a_real_error"])
        errors = rec.validate_against_schema()
        assert any("error_types" in e for e in errors)

    def test_validate_negative_failure_count(self):
        rec = _make_record(failure_count=-1)
        errors = rec.validate_against_schema()
        assert any("failure_count" in e for e in errors)

    def test_validate_pipeline_stage_all_values(self):
        for stage in ("observe", "interpret", "validate", "learn"):
            rec = _make_record(pipeline_stage=stage)
            assert rec.validate_against_schema() == []

    def test_tokens_used_optional(self):
        rec = _make_record(tokens_used=500)
        assert rec.tokens_used == 500
        errors = rec.validate_against_schema()
        assert errors == []

    def test_case_id_optional(self):
        rec = _make_record(case_id="case_001")
        assert rec.case_id == "case_001"
        errors = rec.validate_against_schema()
        assert errors == []

    def test_to_dict_from_dict_roundtrip(self):
        original = _make_record(
            case_id="case_001",
            error_types=["extraction_error"],
            failure_count=1,
            tokens_used=100,
        )
        d = original.to_dict()
        restored = ObservabilityRecord.from_dict(d)
        assert restored.artifact_id == original.artifact_id
        assert restored.pass_type == original.pass_type
        assert restored.structural_score == original.structural_score
        assert restored.error_types == original.error_types
        assert restored.failure_count == original.failure_count
        assert restored.case_id == original.case_id
        assert restored.tokens_used == original.tokens_used

    def test_to_dict_structure(self):
        rec = _make_record()
        d = rec.to_dict()
        assert "record_id" in d
        assert "timestamp" in d
        assert "context" in d
        assert "pass_info" in d
        assert "metrics" in d
        assert "flags" in d
        assert "error_summary" in d
        # context
        assert d["context"]["artifact_id"] == "artifact-001"
        assert d["context"]["pipeline_stage"] == "validate"
        # flags
        assert d["flags"]["human_disagrees"] is False
        # no case_id in context when not set
        assert "case_id" not in d["context"]

    def test_to_dict_includes_case_id_when_set(self):
        rec = _make_record(case_id="case_x")
        d = rec.to_dict()
        assert d["context"]["case_id"] == "case_x"

    def test_from_eval_result_basic(self):
        er = _make_eval_result()
        rec = ObservabilityRecord.from_eval_result(er)
        assert rec.artifact_id == "case_001"
        assert rec.case_id == "case_001"
        assert rec.structural_score == 0.9
        assert rec.semantic_score == 0.85
        assert rec.grounding_score == 1.0
        assert rec.latency_ms == 200
        assert rec.schema_valid is True
        assert rec.regression_passed is True
        assert rec.human_disagrees is False
        assert rec.failure_count == 0

    def test_from_eval_result_with_errors(self):
        er = _make_eval_result(
            error_types=[
                EvalError(error_type=ErrorType.extraction_error, message="Test error"),
            ],
            schema_valid=False,
            regression_detected=True,
        )
        rec = ObservabilityRecord.from_eval_result(er)
        assert rec.schema_valid is False
        assert rec.regression_passed is False
        assert rec.failure_count == 1
        assert "extraction_error" in rec.error_types

    def test_from_eval_result_grounding_passed_logic(self):
        # grounding_score < 1.0 → grounding_passed should be False
        er = _make_eval_result(
            grounding_score=0.5,
            error_types=[
                EvalError(error_type=ErrorType.grounding_failure, message="grounding fail"),
            ],
        )
        rec = ObservabilityRecord.from_eval_result(er)
        assert rec.grounding_passed is False

    def test_from_eval_result_human_disagrees_when_overrides(self):
        er = _make_eval_result(human_feedback_overrides=[{"some": "override"}])
        rec = ObservabilityRecord.from_eval_result(er)
        assert rec.human_disagrees is True

    def test_from_feedback_human_disagrees_always_true(self):
        fb = _make_feedback_record(action="accept")
        rec = ObservabilityRecord.from_feedback(fb)
        assert rec.human_disagrees is True

    def test_from_feedback_maps_failure_type(self):
        fb = _make_feedback_record(failure_type="grounding_failure")
        rec = ObservabilityRecord.from_feedback(fb)
        assert "grounding_failure" in rec.error_types
        assert rec.grounding_passed is False

    def test_from_feedback_unclear_normalised(self):
        fb = _make_feedback_record(failure_type="unclear")
        rec = ObservabilityRecord.from_feedback(fb)
        # "unclear" is normalised to "extraction_error"
        assert "extraction_error" in rec.error_types

    def test_from_feedback_default_pipeline_stage(self):
        fb = _make_feedback_record()
        rec = ObservabilityRecord.from_feedback(fb)
        assert rec.pipeline_stage == "learn"
        assert rec.pass_type == "human_feedback"
        assert rec.failure_count == 1


# ---------------------------------------------------------------------------
# MetricsStore
# ---------------------------------------------------------------------------

class TestMetricsStore:
    def test_save_and_load(self):
        store = _store_in_tmpdir()
        rec = _make_record()
        store.save(rec)
        loaded = store.load(rec.record_id)
        assert loaded.record_id == rec.record_id
        assert loaded.artifact_id == rec.artifact_id

    def test_load_nonexistent_raises(self):
        store = _store_in_tmpdir()
        with pytest.raises(FileNotFoundError):
            store.load("nonexistent-id")

    def test_save_invalid_record_raises(self):
        store = _store_in_tmpdir()
        rec = _make_record(pipeline_stage="bad_stage")
        with pytest.raises(ValueError, match="failed validation"):
            store.save(rec)

    def test_list_returns_all_records(self):
        store = _store_in_tmpdir()
        for i in range(3):
            store.save(_make_record(artifact_id=f"artifact-{i}"))
        records = store.list()
        assert len(records) == 3

    def test_list_with_artifact_id_filter(self):
        store = _store_in_tmpdir()
        store.save(_make_record(artifact_id="target"))
        store.save(_make_record(artifact_id="other"))
        records = store.list(filters={"artifact_id": "target"})
        assert len(records) == 1
        assert records[0].artifact_id == "target"

    def test_list_with_pass_type_filter(self):
        store = _store_in_tmpdir()
        store.save(_make_record(pass_type="extraction"))
        store.save(_make_record(pass_type="reasoning"))
        records = store.list(filters={"pass_type": "reasoning"})
        assert len(records) == 1
        assert records[0].pass_type == "reasoning"

    def test_list_with_human_disagrees_filter(self):
        store = _store_in_tmpdir()
        store.save(_make_record(human_disagrees=True))
        store.save(_make_record(human_disagrees=False))
        records = store.list(filters={"human_disagrees": True})
        assert len(records) == 1
        assert records[0].human_disagrees is True

    def test_aggregate_empty_store(self):
        store = _store_in_tmpdir()
        result = store.aggregate()
        assert result["record_count"] == 0
        assert result["avg_structural_score"] is None

    def test_aggregate_with_records(self):
        store = _store_in_tmpdir()
        store.save(_make_record(structural_score=0.8, latency_ms=200))
        store.save(_make_record(structural_score=0.6, latency_ms=400))
        result = store.aggregate()
        assert result["record_count"] == 2
        assert abs(result["avg_structural_score"] - 0.7) < 1e-9
        assert result["avg_latency_ms"] == 300.0


# ---------------------------------------------------------------------------
# Aggregation functions
# ---------------------------------------------------------------------------

class TestAggregation:
    def _make_records(self):
        return [
            _make_record(
                pass_type="extraction",
                structural_score=0.9,
                semantic_score=0.85,
                grounding_score=1.0,
                latency_ms=100,
                failure_count=0,
                human_disagrees=False,
                grounding_passed=True,
                error_types=[],
            ),
            _make_record(
                pass_type="reasoning",
                structural_score=0.5,
                semantic_score=0.4,
                grounding_score=0.6,
                latency_ms=500,
                failure_count=2,
                human_disagrees=True,
                grounding_passed=False,
                error_types=["reasoning_error", "grounding_failure"],
            ),
            _make_record(
                pass_type="extraction",
                structural_score=0.7,
                semantic_score=0.6,
                grounding_score=0.8,
                latency_ms=200,
                failure_count=1,
                human_disagrees=False,
                grounding_passed=False,
                error_types=["extraction_error"],
            ),
        ]

    def test_compute_pass_metrics_empty(self):
        result = compute_pass_metrics([])
        assert result["by_pass_type"] == {}
        assert result["overall"] == {}

    def test_compute_pass_metrics_by_pass_type(self):
        records = self._make_records()
        result = compute_pass_metrics(records)
        by_pt = result["by_pass_type"]
        assert "extraction" in by_pt
        assert "reasoning" in by_pt
        assert by_pt["extraction"]["record_count"] == 2
        assert by_pt["reasoning"]["record_count"] == 1
        # avg structural for extraction: (0.9 + 0.7) / 2 = 0.8
        assert abs(by_pt["extraction"]["avg_structural_score"] - 0.8) < 1e-9

    def test_compute_pass_metrics_overall(self):
        records = self._make_records()
        result = compute_pass_metrics(records)
        overall = result["overall"]
        assert overall["record_count"] == 3
        # failure rate: 2/3 have failure_count > 0
        assert abs(overall["failure_rate"] - 2 / 3) < 1e-9

    def test_compute_error_distribution_empty(self):
        result = compute_error_distribution([])
        assert result["total_error_count"] == 0
        assert result["top_error_type"] is None

    def test_compute_error_distribution(self):
        records = self._make_records()
        result = compute_error_distribution(records)
        by_type = result["by_error_type"]
        assert by_type.get("extraction_error", 0) == 1
        assert by_type.get("reasoning_error", 0) == 1
        assert by_type.get("grounding_failure", 0) == 1
        assert result["total_error_count"] == 3

    def test_compute_error_distribution_top_type(self):
        records = [
            _make_record(error_types=["extraction_error"]),
            _make_record(error_types=["extraction_error"]),
            _make_record(error_types=["reasoning_error"]),
        ]
        result = compute_error_distribution(records)
        assert result["top_error_type"] == "extraction_error"

    def test_compute_human_disagreement_empty(self):
        result = compute_human_disagreement([])
        assert result["overall_disagreement_rate"] is None

    def test_compute_human_disagreement_rate(self):
        records = self._make_records()
        result = compute_human_disagreement(records)
        # 1 out of 3 disagrees
        assert abs(result["overall_disagreement_rate"] - 1 / 3) < 1e-9

    def test_compute_human_disagreement_by_pass_type(self):
        records = self._make_records()
        result = compute_human_disagreement(records)
        by_pt = result["by_pass_type"]
        # reasoning: 1/1 disagrees
        assert by_pt["reasoning"] == 1.0
        # extraction: 0/2 disagrees
        assert by_pt["extraction"] == 0.0

    def test_compute_grounding_failure_rate_empty(self):
        result = compute_grounding_failure_rate([])
        assert result["overall_failure_rate"] is None

    def test_compute_grounding_failure_rate(self):
        records = self._make_records()
        result = compute_grounding_failure_rate(records)
        # 2 out of 3 failed grounding
        assert abs(result["overall_failure_rate"] - 2 / 3) < 1e-9

    def test_compute_latency_stats_empty(self):
        result = compute_latency_stats([])
        assert result["mean_ms"] is None
        assert result["p95_ms"] is None
        assert result["max_ms"] is None

    def test_compute_latency_stats(self):
        records = self._make_records()
        result = compute_latency_stats(records)
        # latencies: 100, 500, 200
        assert result["mean_ms"] == pytest.approx(800 / 3)
        assert result["max_ms"] == 500
        assert result["p95_ms"] <= 500

    def test_compute_weakest_passes_ordered(self):
        records = self._make_records()
        weakest = compute_weakest_passes(records)
        # reasoning has higher failure rate
        assert len(weakest) >= 1
        # sorted descending by failure_rate
        for i in range(len(weakest) - 1):
            assert weakest[i]["failure_rate"] >= weakest[i + 1]["failure_rate"]


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------

class TestTrends:
    def _current_records(self):
        return [
            _make_record(
                structural_score=0.9,
                grounding_score=1.0,
                latency_ms=100,
                failure_count=0,
                grounding_passed=True,
                human_disagrees=False,
            ),
        ]

    def _previous_records(self):
        return [
            _make_record(
                structural_score=0.7,
                grounding_score=0.8,
                latency_ms=200,
                failure_count=1,
                grounding_passed=False,
                human_disagrees=True,
            ),
        ]

    def test_compare_runs_returns_structure(self):
        result = compare_runs(self._current_records(), self._previous_records())
        assert "current" in result
        assert "previous" in result
        assert "deltas" in result
        assert "computed_at" in result

    def test_compare_runs_score_improvement(self):
        result = compare_runs(self._current_records(), self._previous_records())
        # structural improved: 0.9 - 0.7 = +0.2
        assert result["deltas"]["structural_score"] == pytest.approx(0.2, abs=1e-9)

    def test_compare_runs_latency_improvement(self):
        result = compare_runs(self._current_records(), self._previous_records())
        # Latency improved (lower): prev=200, curr=100 → positive delta (improvement)
        assert result["deltas"]["latency_ms"] == pytest.approx(100.0, abs=1e-9)

    def test_compare_runs_empty_current(self):
        result = compare_runs([], self._previous_records())
        assert result["current"]["record_count"] == 0

    def test_compare_runs_both_empty(self):
        result = compare_runs([], [])
        assert result["deltas"]["structural_score"] is None

    def test_save_and_load_snapshot(self, tmp_path):
        records = self._current_records()
        save_snapshot(records, label="test_run", history_dir=tmp_path)
        loaded = load_snapshot("test_run", history_dir=tmp_path)
        assert loaded is not None
        assert loaded["snapshot_label"] == "test_run"
        assert loaded["record_count"] == 1

    def test_load_snapshot_missing_returns_none(self, tmp_path):
        result = load_snapshot("nonexistent", history_dir=tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# EvalRunner integration
# ---------------------------------------------------------------------------

class _StubEngine:
    """Minimal engine stub that returns an empty pass chain record."""

    def run(self, transcript, config):
        return {
            "pass_results": [],
            "intermediate_artifacts": {},
        }


def _write_minimal_case(root: Path, case_id: str) -> None:
    """Write minimal golden case files for testing."""
    case_dir = root / case_id
    (case_dir / "input").mkdir(parents=True)
    (case_dir / "expected_outputs").mkdir(parents=True)
    (case_dir / "metadata.json").write_text(
        json.dumps({"case_id": case_id, "domain": "test", "difficulty": "easy", "notes": "Test"}),
        encoding="utf-8",
    )
    (case_dir / "input" / "transcript.txt").write_text("Test transcript.", encoding="utf-8")
    (case_dir / "expected_outputs" / "decisions.json").write_text(json.dumps([]), encoding="utf-8")
    (case_dir / "expected_outputs" / "action_items.json").write_text(json.dumps([]), encoding="utf-8")
    (case_dir / "expected_outputs" / "gaps.json").write_text(json.dumps([]), encoding="utf-8")
    (case_dir / "expected_outputs" / "contradictions.json").write_text(json.dumps([]), encoding="utf-8")


class TestEvalRunnerObservability:
    def test_no_emission_without_metrics_store(self, tmp_path):
        """EvalRunner with no metrics_store should not fail."""
        from spectrum_systems.modules.evaluation.golden_dataset import load_case

        root = tmp_path / "golden_cases"
        _write_minimal_case(root, "case_001")
        case = load_case("case_001", root)

        runner = EvalRunner(reasoning_engine=_StubEngine())
        result = runner.run_case(case)
        assert result.case_id == "case_001"

    def test_emission_with_metrics_store(self, tmp_path):
        """EvalRunner emits an ObservabilityRecord when metrics_store is set."""
        from spectrum_systems.modules.evaluation.golden_dataset import load_case

        root = tmp_path / "golden_cases"
        _write_minimal_case(root, "case_emit")
        case = load_case("case_emit", root)

        store = _store_in_tmpdir()
        runner = EvalRunner(reasoning_engine=_StubEngine(), metrics_store=store)
        runner.run_case(case)

        records = store.list()
        assert len(records) == 1
        assert records[0].case_id == "case_emit"
        assert records[0].artifact_type == "evaluation_result"
        assert records[0].pipeline_stage == "validate"

    def test_multiple_cases_emit_multiple_records(self, tmp_path):
        from spectrum_systems.modules.evaluation.golden_dataset import load_case, GoldenDataset

        root = tmp_path / "golden_cases"
        cases = []
        for i in range(3):
            cid = f"case_{i:03d}"
            _write_minimal_case(root, cid)
            cases.append(load_case(cid, root))

        store = _store_in_tmpdir()
        runner = EvalRunner(reasoning_engine=_StubEngine(), metrics_store=store)
        from spectrum_systems.modules.evaluation.golden_dataset import GoldenDataset
        dataset = GoldenDataset(cases=cases)
        runner.run_all_cases(dataset)

        records = store.list()
        assert len(records) == 3


# ---------------------------------------------------------------------------
# Feedback integration
# ---------------------------------------------------------------------------

class TestFeedbackObservability:
    def _make_artifact(self):
        return {"artifact_id": "artifact-fb-001", "artifact_type": "working_paper"}

    def _make_reviewer_input(self):
        return {
            "reviewer_id": "reviewer-1",
            "reviewer_role": "engineer",
            "target_level": "claim",
            "target_id": "claim-001",
            "action": "accept",
            "original_text": "Original AI text.",
            "rationale": "Correct.",
            "source_of_truth": "transcript",
            "failure_type": "unclear",
            "severity": "low",
            "should_update": {
                "golden_dataset": False,
                "prompts": False,
                "retrieval_memory": False,
            },
        }

    def test_feedback_emits_observability_record(self, tmp_path):
        fb_store_dir = tmp_path / "feedback"
        obs_store_dir = tmp_path / "observability"
        from spectrum_systems.modules.feedback.human_feedback import FeedbackStore

        fb_store = FeedbackStore(store_dir=fb_store_dir)
        obs_store = MetricsStore(store_dir=obs_store_dir)

        create_feedback_from_review(
            artifact=self._make_artifact(),
            reviewer_input=self._make_reviewer_input(),
            store=fb_store,
            metrics_store=obs_store,
        )

        records = obs_store.list()
        assert len(records) == 1
        assert records[0].human_disagrees is True
        assert records[0].pipeline_stage == "learn"
        assert records[0].artifact_id == "artifact-fb-001"

    def test_feedback_no_emission_without_metrics_store(self, tmp_path):
        fb_store_dir = tmp_path / "feedback"
        from spectrum_systems.modules.feedback.human_feedback import FeedbackStore

        fb_store = FeedbackStore(store_dir=fb_store_dir)

        # Should not raise
        create_feedback_from_review(
            artifact=self._make_artifact(),
            reviewer_input=self._make_reviewer_input(),
            store=fb_store,
            metrics_store=None,
        )


# ---------------------------------------------------------------------------
# JSON Schema validation
# ---------------------------------------------------------------------------

class TestObservabilityRecordSchema:
    def _load_schema(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            pytest.skip("jsonschema not installed")
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        return Draft202012Validator(schema)

    def test_schema_file_exists(self):
        assert _SCHEMA_PATH.exists(), f"Schema not found at {_SCHEMA_PATH}"

    def test_schema_validates_valid_record(self):
        validator = self._load_schema()
        rec = _make_record(case_id="case_001", tokens_used=100)
        errors = list(validator.iter_errors(rec.to_dict()))
        assert errors == [], [str(e) for e in errors]

    def test_schema_rejects_missing_record_id(self):
        validator = self._load_schema()
        rec = _make_record()
        d = rec.to_dict()
        del d["record_id"]
        errors = list(validator.iter_errors(d))
        assert errors

    def test_schema_rejects_missing_context(self):
        validator = self._load_schema()
        rec = _make_record()
        d = rec.to_dict()
        del d["context"]
        errors = list(validator.iter_errors(d))
        assert errors

    def test_schema_rejects_invalid_pipeline_stage(self):
        validator = self._load_schema()
        rec = _make_record()
        d = rec.to_dict()
        d["context"]["pipeline_stage"] = "bad_stage"
        errors = list(validator.iter_errors(d))
        assert errors

    def test_schema_rejects_invalid_error_type(self):
        validator = self._load_schema()
        rec = _make_record()
        d = rec.to_dict()
        d["error_summary"]["error_types"] = ["not_a_valid_type"]
        errors = list(validator.iter_errors(d))
        assert errors

    def test_schema_rejects_score_out_of_range(self):
        validator = self._load_schema()
        rec = _make_record()
        d = rec.to_dict()
        d["metrics"]["structural_score"] = 1.5
        errors = list(validator.iter_errors(d))
        assert errors

    def test_schema_rejects_additional_properties(self):
        validator = self._load_schema()
        rec = _make_record()
        d = rec.to_dict()
        d["unexpected_field"] = "should_fail"
        errors = list(validator.iter_errors(d))
        assert errors
