"""
Tests for the Evaluation Framework (Prompt AN).

Covers:
- GoldenCase and GoldenDataset loading and validation
- validate_case_structure: valid and invalid case structures
- load_case: missing files raise GoldenCaseError
- load_all_cases: loads sorted cases from root dir
- GroundingVerifier: grounding pass/fail rules
- GroundingVerifier: hallucination vs grounding_failure classification
- GroundingVerifier: document-level grounding
- compare_structural: exact matching, missing, extra items
- compare_semantic: fuzzy matching and threshold behaviour
- ErrorType taxonomy: all error types exist
- classify_error: correct type assignment for each error category
- RegressionHarness: save/load baseline, compare, regression detection
- EvalRunner: run_case happy path (stub engine)
- EvalRunner: run_all_cases iterates over dataset
- EvalRunner: write_report produces valid JSON
- EvalRunner: deterministic mode flag propagated to engine config
- EvalRunner: engine exception results in FAIL EvalResult
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import pytest

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------

from spectrum_systems.modules.evaluation.golden_dataset import (
    GoldenCase,
    GoldenDataset,
    GoldenCaseError,
    load_all_cases,
    load_case,
    validate_case_structure,
)
from spectrum_systems.modules.evaluation.grounding import (
    GroundingVerifier,
    GroundingResult,
    DocumentGroundingResult,
)
from spectrum_systems.modules.evaluation.comparison import (
    ComparisonResult,
    compare_structural,
    compare_semantic,
)
from spectrum_systems.modules.evaluation.error_taxonomy import (
    EvalError,
    ErrorType,
    classify_error,
)
from spectrum_systems.modules.evaluation.regression import (
    BaselineRecord,
    RegressionHarness,
    RegressionResult,
)
from spectrum_systems.modules.evaluation.eval_runner import (
    EvalResult,
    EvalRunner,
    LatencySummary,
)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture()
def tmp_golden_root(tmp_path: Path) -> Path:
    """Create a minimal valid golden cases root with one case."""
    root = tmp_path / "golden_cases"
    _write_valid_case(root, "case_001")
    return root


@pytest.fixture()
def valid_golden_case(tmp_path: Path) -> GoldenCase:
    root = tmp_path / "golden_cases"
    _write_valid_case(root, "case_001")
    return load_case("case_001", root)


@pytest.fixture()
def baselines_dir(tmp_path: Path) -> Path:
    d = tmp_path / "baselines"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_valid_case(root: Path, case_id: str, *, difficulty: str = "easy") -> None:
    case_dir = root / case_id
    (case_dir / "input").mkdir(parents=True)
    (case_dir / "expected_outputs").mkdir(parents=True)
    (case_dir / "metadata.json").write_text(json.dumps({
        "case_id": case_id,
        "domain": "7ghz",
        "difficulty": difficulty,
        "notes": "Test case",
    }), encoding="utf-8")
    (case_dir / "input" / "transcript.txt").write_text(
        "The committee decided to approve the interference threshold of -114 dBm/MHz.",
        encoding="utf-8",
    )
    (case_dir / "expected_outputs" / "decisions.json").write_text(
        json.dumps([{"text": "Approve interference threshold of -114 dBm/MHz"}]),
        encoding="utf-8",
    )
    (case_dir / "expected_outputs" / "action_items.json").write_text(
        json.dumps([{"text": "Submit coordination package"}]),
        encoding="utf-8",
    )
    (case_dir / "expected_outputs" / "gaps.json").write_text(
        json.dumps([{"text": "Propagation model not aligned"}]),
        encoding="utf-8",
    )
    (case_dir / "expected_outputs" / "contradictions.json").write_text(
        json.dumps([]),
        encoding="utf-8",
    )


class _StubEngine:
    """Stub reasoning engine that returns configurable pass chain records."""

    def __init__(self, record: Optional[Dict[str, Any]] = None) -> None:
        self._record = record or {
            "chain_id": "test-chain",
            "status": "completed",
            "pass_results": [
                {
                    "pass_id": "pass-001",
                    "pass_type": "decision_extraction",
                    "pass_order": 1,
                    "latency_ms": 50,
                    "schema_validation": {"schema_id": None, "status": "skipped", "errors": []},
                    "_raw_output": {"decisions": [{"text": "Approve interference threshold of -114 dBm/MHz"}]},
                    "output_ref": "artifact:pass-001:decision_extraction",
                },
                {
                    "pass_id": "pass-002",
                    "pass_type": "transcript_extraction",
                    "pass_order": 2,
                    "latency_ms": 30,
                    "schema_validation": {"schema_id": None, "status": "skipped", "errors": []},
                    "_raw_output": {"action_items": [{"text": "Submit coordination package"}]},
                    "output_ref": "artifact:pass-002:transcript_extraction",
                },
                {
                    "pass_id": "pass-003",
                    "pass_type": "gap_detection",
                    "pass_order": 3,
                    "latency_ms": 80,
                    "schema_validation": {"schema_id": None, "status": "skipped", "errors": []},
                    "_raw_output": {"gaps": [{"text": "Propagation model not aligned"}]},
                    "output_ref": "artifact:pass-003:gap_detection",
                },
                {
                    "pass_id": "pass-004",
                    "pass_type": "contradiction_detection",
                    "pass_order": 4,
                    "latency_ms": 70,
                    "schema_validation": {"schema_id": None, "status": "skipped", "errors": []},
                    "_raw_output": {"contradictions": []},
                    "output_ref": "artifact:pass-004:contradiction_detection",
                },
            ],
            "intermediate_artifacts": {},
        }
        self.last_config: Optional[Dict[str, Any]] = None

    def run(self, transcript: str, config: dict = None) -> Dict[str, Any]:
        self.last_config = config
        return self._record


class _FailingEngine:
    def run(self, transcript: str, config: dict = None) -> Dict[str, Any]:
        raise RuntimeError("Model invocation failed")


# ===========================================================================
# 1. Golden Dataset Tests
# ===========================================================================

class TestValidateCaseStructure:
    def test_valid_case_returns_no_errors(self, tmp_path: Path) -> None:
        root = tmp_path / "cases"
        _write_valid_case(root, "case_001")
        errors = validate_case_structure(root / "case_001")
        assert errors == []

    def test_missing_directory_returns_error(self, tmp_path: Path) -> None:
        errors = validate_case_structure(tmp_path / "nonexistent")
        assert any("does not exist" in e for e in errors)

    def test_missing_metadata_returns_error(self, tmp_path: Path) -> None:
        case_dir = tmp_path / "case"
        case_dir.mkdir()
        (case_dir / "input").mkdir()
        (case_dir / "expected_outputs").mkdir()
        (case_dir / "input" / "transcript.txt").write_text("text")
        for f in ("decisions.json", "action_items.json", "gaps.json", "contradictions.json"):
            (case_dir / "expected_outputs" / f).write_text("[]")
        errors = validate_case_structure(case_dir)
        assert any("metadata.json" in e for e in errors)

    def test_invalid_difficulty_returns_error(self, tmp_path: Path) -> None:
        root = tmp_path / "cases"
        _write_valid_case(root, "case_001", difficulty="extreme")
        errors = validate_case_structure(root / "case_001")
        assert any("difficulty" in e for e in errors)

    def test_missing_transcript_returns_error(self, tmp_path: Path) -> None:
        root = tmp_path / "cases"
        _write_valid_case(root, "case_001")
        (root / "case_001" / "input" / "transcript.txt").unlink()
        errors = validate_case_structure(root / "case_001")
        assert any("transcript.txt" in e for e in errors)

    def test_missing_decisions_returns_error(self, tmp_path: Path) -> None:
        root = tmp_path / "cases"
        _write_valid_case(root, "case_001")
        (root / "case_001" / "expected_outputs" / "decisions.json").unlink()
        errors = validate_case_structure(root / "case_001")
        assert any("decisions.json" in e for e in errors)

    def test_invalid_json_in_output_returns_error(self, tmp_path: Path) -> None:
        root = tmp_path / "cases"
        _write_valid_case(root, "case_001")
        (root / "case_001" / "expected_outputs" / "decisions.json").write_text(
            "{invalid json}", encoding="utf-8"
        )
        errors = validate_case_structure(root / "case_001")
        assert any("decisions.json" in e for e in errors)


class TestLoadCase:
    def test_load_valid_case(self, tmp_golden_root: Path) -> None:
        case = load_case("case_001", tmp_golden_root)
        assert case.case_id == "case_001"
        assert case.domain == "7ghz"
        assert case.difficulty == "easy"
        assert "interference threshold" in case.transcript.lower()
        assert isinstance(case.expected_decisions, list)
        assert isinstance(case.expected_action_items, list)
        assert isinstance(case.expected_gaps, list)
        assert isinstance(case.expected_contradictions, list)

    def test_load_missing_case_raises(self, tmp_golden_root: Path) -> None:
        with pytest.raises(GoldenCaseError):
            load_case("nonexistent_case", tmp_golden_root)

    def test_expected_outputs_dict_contains_all_keys(self, valid_golden_case: GoldenCase) -> None:
        outputs = valid_golden_case.expected_outputs()
        assert "decisions" in outputs
        assert "action_items" in outputs
        assert "gaps" in outputs
        assert "contradictions" in outputs

    def test_optional_working_paper_sections_absent_by_default(
        self, valid_golden_case: GoldenCase
    ) -> None:
        assert valid_golden_case.expected_working_paper_sections is None
        outputs = valid_golden_case.expected_outputs()
        assert "working_paper_sections" not in outputs

    def test_load_case_with_working_paper_sections(self, tmp_path: Path) -> None:
        root = tmp_path / "cases"
        _write_valid_case(root, "case_wp")
        wp = [{"section": "intro", "content": "summary text"}]
        (root / "case_wp" / "expected_outputs" / "working_paper_sections.json").write_text(
            json.dumps(wp), encoding="utf-8"
        )
        case = load_case("case_wp", root)
        assert case.expected_working_paper_sections == wp


class TestLoadAllCases:
    def test_loads_all_cases_sorted(self, tmp_path: Path) -> None:
        root = tmp_path / "cases"
        _write_valid_case(root, "case_002")
        _write_valid_case(root, "case_001")
        dataset = load_all_cases(root)
        assert len(dataset) == 2
        assert dataset.cases[0].case_id == "case_001"
        assert dataset.cases[1].case_id == "case_002"

    def test_nonexistent_root_raises(self, tmp_path: Path) -> None:
        with pytest.raises(GoldenCaseError):
            load_all_cases(tmp_path / "nonexistent")

    def test_dataset_get_case(self, tmp_golden_root: Path) -> None:
        dataset = load_all_cases(tmp_golden_root)
        case = dataset.get_case("case_001")
        assert case.case_id == "case_001"

    def test_dataset_get_case_missing_raises(self, tmp_golden_root: Path) -> None:
        dataset = load_all_cases(tmp_golden_root)
        with pytest.raises(KeyError):
            dataset.get_case("nonexistent")

    def test_dataset_case_ids(self, tmp_path: Path) -> None:
        root = tmp_path / "cases"
        _write_valid_case(root, "case_003")
        _write_valid_case(root, "case_001")
        dataset = load_all_cases(root)
        assert dataset.case_ids() == ["case_001", "case_003"]


# ===========================================================================
# 2. Grounding Tests
# ===========================================================================

class TestGroundingVerifier:
    @pytest.fixture()
    def verifier(self) -> GroundingVerifier:
        return GroundingVerifier(min_overlap_tokens=1)

    def test_well_grounded_claim_passes(self, verifier: GroundingVerifier) -> None:
        claim = {
            "text": "The committee adopted a -114 dBm/MHz threshold",
            "upstream_pass_refs": ["pass-001"],
        }
        artifacts = {
            "pass-001": "The -114 dBm/MHz interference threshold was approved by the committee."
        }
        result = verifier.verify_claim(claim, artifacts)
        assert result.grounded is True
        assert result.missing_refs == []
        assert result.mismatched_refs == []

    def test_claim_without_refs_fails(self, verifier: GroundingVerifier) -> None:
        claim = {"text": "The threshold was approved"}
        result = verifier.verify_claim(claim, {})
        assert result.grounded is False

    def test_claim_with_missing_ref_fails(self, verifier: GroundingVerifier) -> None:
        claim = {
            "text": "Some claim text",
            "upstream_pass_refs": ["nonexistent-pass"],
        }
        result = verifier.verify_claim(claim, {"other-pass": "some content"})
        assert result.grounded is False
        assert "nonexistent-pass" in result.missing_refs

    def test_claim_with_mismatched_ref_fails(self, verifier: GroundingVerifier) -> None:
        claim = {
            "text": "The interference threshold is -114 dBm/MHz",
            "upstream_pass_refs": ["pass-001"],
        }
        # Artifact has totally unrelated content
        artifacts = {"pass-001": "xyz abc 123 qrs tuv"}
        result = verifier.verify_claim(claim, artifacts)
        assert result.grounded is False
        assert "pass-001" in result.mismatched_refs

    def test_no_silent_passing_on_empty_refs(self, verifier: GroundingVerifier) -> None:
        claim = {"text": "Something", "upstream_pass_refs": []}
        result = verifier.verify_claim(claim, {"pass-001": "something"})
        assert result.grounded is False

    def test_document_all_grounded(self, verifier: GroundingVerifier) -> None:
        doc = {
            "claims": [
                {"text": "threshold approved", "upstream_pass_refs": ["pass-001"]},
                {"text": "action items recorded", "upstream_pass_refs": ["pass-002"]},
            ]
        }
        artifacts = {
            "pass-001": "The threshold was approved in the meeting.",
            "pass-002": "Action items were recorded for coordination.",
        }
        result = verifier.verify_document(doc, artifacts)
        assert result.grounded is True
        assert result.total_claims == 2
        assert result.failed_claims == 0
        assert result.grounding_score == 1.0

    def test_document_with_failed_claim(self, verifier: GroundingVerifier) -> None:
        doc = {
            "claims": [
                {"text": "threshold approved", "upstream_pass_refs": ["pass-001"]},
                {"text": "hallucinated fact with no ref"},
            ]
        }
        artifacts = {"pass-001": "threshold approved"}
        result = verifier.verify_document(doc, artifacts)
        assert result.grounded is False
        assert result.failed_claims == 1
        assert result.grounding_score == 0.5

    def test_document_with_sections(self, verifier: GroundingVerifier) -> None:
        doc = {
            "sections": [
                {
                    "title": "Decisions",
                    "claims": [
                        {"text": "threshold set", "upstream_pass_refs": ["pass-001"]},
                    ],
                }
            ]
        }
        artifacts = {"pass-001": "The threshold was set in the meeting."}
        result = verifier.verify_document(doc, artifacts)
        assert result.grounded is True

    def test_empty_document_is_grounded(self, verifier: GroundingVerifier) -> None:
        result = verifier.verify_document({}, {})
        assert result.grounded is True
        assert result.total_claims == 0
        assert result.grounding_score == 1.0

    def test_dict_artifact_is_searchable(self, verifier: GroundingVerifier) -> None:
        claim = {
            "text": "decision on threshold",
            "upstream_pass_refs": ["pass-001"],
        }
        artifacts = {"pass-001": {"decisions": [{"text": "decision on threshold approved"}]}}
        result = verifier.verify_claim(claim, artifacts)
        assert result.grounded is True


# ===========================================================================
# 3. Comparison Tests
# ===========================================================================

class TestCompareStructural:
    def test_exact_match(self) -> None:
        items = [{"text": "decision A"}, {"text": "decision B"}]
        result = compare_structural(items, items)
        assert result.f1_score == pytest.approx(1.0)
        assert result.missing == []
        assert result.extra == []

    def test_missing_item(self) -> None:
        expected = [{"text": "decision A"}, {"text": "decision B"}]
        actual = [{"text": "decision A"}]
        result = compare_structural(expected, actual)
        assert result.recall < 1.0
        assert len(result.missing) == 1

    def test_extra_item(self) -> None:
        expected = [{"text": "decision A"}]
        actual = [{"text": "decision A"}, {"text": "decision B"}]
        result = compare_structural(expected, actual)
        assert result.precision < 1.0
        assert len(result.extra) == 1

    def test_no_overlap(self) -> None:
        expected = [{"text": "item X"}]
        actual = [{"text": "item Y"}]
        result = compare_structural(expected, actual)
        assert result.f1_score == pytest.approx(0.0)

    def test_empty_expected_and_actual(self) -> None:
        result = compare_structural([], [])
        assert result.f1_score == pytest.approx(1.0)

    def test_empty_actual(self) -> None:
        result = compare_structural([{"text": "item"}], [])
        assert result.recall == pytest.approx(0.0)

    def test_string_items(self) -> None:
        # expected={a,b,c}, actual={a,b,d}: TP=2, FP=1, FN=1 → P=2/3, R=2/3, F1=2/3
        result = compare_structural(["a", "b", "c"], ["a", "b", "d"])
        assert result.f1_score == pytest.approx(2 / 3)


class TestCompareSemantic:
    def test_identical_items_match(self) -> None:
        items = [{"text": "adopt interference threshold"}]
        result = compare_semantic(items, items)
        assert result.f1_score == pytest.approx(1.0)

    def test_paraphrase_matches_above_threshold(self) -> None:
        expected = [{"text": "The committee adopted the interference threshold of -114 dBm/MHz"}]
        actual = [{"text": "Committee approved -114 dBm/MHz interference threshold decision"}]
        result = compare_semantic(expected, actual, threshold=0.2)
        assert result.f1_score > 0.5

    def test_completely_different_items_do_not_match(self) -> None:
        expected = [{"text": "interference threshold adopted"}]
        actual = [{"text": "schedule coordination meeting"}]
        result = compare_semantic(expected, actual, threshold=0.5)
        assert result.f1_score == pytest.approx(0.0)

    def test_empty_lists(self) -> None:
        result = compare_semantic([], [])
        assert result.f1_score == pytest.approx(1.0)

    def test_missing_items_recorded(self) -> None:
        expected = [{"text": "decision A"}, {"text": "decision B"}]
        actual = []
        result = compare_semantic(expected, actual)
        assert len(result.missing) == 2
        assert result.recall == pytest.approx(0.0)

    def test_string_items_semantic(self) -> None:
        expected = ["approve the threshold proposal"]
        actual = ["approved the threshold proposal today"]
        result = compare_semantic(expected, actual, threshold=0.3)
        assert result.f1_score > 0.0


# ===========================================================================
# 4. Error Taxonomy Tests
# ===========================================================================

class TestErrorType:
    def test_all_error_types_exist(self) -> None:
        expected_types = {
            "extraction_error",
            "reasoning_error",
            "grounding_failure",
            "schema_violation",
            "hallucination",
            "regression_failure",
        }
        actual_types = {e.value for e in ErrorType}
        assert expected_types == actual_types


class TestClassifyError:
    def test_schema_errors_produce_schema_violation(self) -> None:
        err = classify_error({"schema_errors": ["field 'x' missing"], "message": "schema failed"})
        assert err.error_type == ErrorType.schema_violation

    def test_missing_refs_produce_grounding_failure(self) -> None:
        err = classify_error({
            "missing_refs": ["pass-001"],
            "mismatched_refs": [],
            "upstream_pass_refs": ["pass-001", "pass-002"],
        })
        assert err.error_type == ErrorType.grounding_failure

    def test_all_refs_missing_produces_hallucination(self) -> None:
        err = classify_error({
            "missing_refs": ["pass-001"],
            "mismatched_refs": [],
            "upstream_pass_refs": ["pass-001"],
        })
        assert err.error_type == ErrorType.hallucination

    def test_reasoning_pass_type_produces_reasoning_error(self) -> None:
        err = classify_error({"pass_type": "decision_extraction", "message": "wrong conclusion"})
        assert err.error_type == ErrorType.reasoning_error

    def test_regression_flag_produces_regression_failure(self) -> None:
        err = classify_error({"regression": True, "message": "score dropped"})
        assert err.error_type == ErrorType.regression_failure

    def test_fallback_produces_extraction_error(self) -> None:
        err = classify_error({"pass_type": "transcript_extraction", "message": "failed"})
        assert err.error_type == ErrorType.extraction_error

    def test_schema_violation_takes_priority_over_grounding(self) -> None:
        err = classify_error({
            "schema_errors": ["missing field"],
            "missing_refs": ["pass-001"],
            "upstream_pass_refs": ["pass-001"],
        })
        assert err.error_type == ErrorType.schema_violation


# ===========================================================================
# 5. Regression Harness Tests
# ===========================================================================

class TestRegressionHarness:
    def test_no_baseline_returns_no_regression(self, baselines_dir: Path) -> None:
        harness = RegressionHarness(baselines_dir=baselines_dir)
        result = harness.compare("case_001", 0.8, 0.7, 0.9)
        assert result.has_baseline is False
        assert result.regression_detected is False

    def test_save_and_load_baseline(self, baselines_dir: Path) -> None:
        harness = RegressionHarness(baselines_dir=baselines_dir)
        record = BaselineRecord(
            case_id="case_001",
            structural_score=0.9,
            semantic_score=0.85,
            grounding_score=1.0,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )
        harness.save_baseline(record)
        loaded = harness.load_baseline("case_001")
        assert loaded is not None
        assert loaded.case_id == "case_001"
        assert loaded.structural_score == pytest.approx(0.9)

    def test_no_regression_when_scores_stable(self, baselines_dir: Path) -> None:
        harness = RegressionHarness(baselines_dir=baselines_dir)
        record = BaselineRecord(
            case_id="case_001",
            structural_score=0.9,
            semantic_score=0.85,
            grounding_score=1.0,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )
        harness.save_baseline(record)
        result = harness.compare("case_001", 0.9, 0.85, 1.0)
        assert result.regression_detected is False
        assert result.has_baseline is True

    def test_regression_detected_when_score_drops_beyond_threshold(
        self, baselines_dir: Path
    ) -> None:
        harness = RegressionHarness(
            baselines_dir=baselines_dir,
            thresholds={"structural_score": 0.05, "semantic_score": 0.05, "grounding_score": 0.05},
        )
        record = BaselineRecord(
            case_id="case_001",
            structural_score=0.9,
            semantic_score=0.85,
            grounding_score=1.0,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )
        harness.save_baseline(record)
        # Drop structural by 0.2 — exceeds 0.05 threshold
        result = harness.compare("case_001", 0.7, 0.85, 1.0)
        assert result.regression_detected is True
        regressions = [d for d in result.score_deltas if d.is_regression]
        assert any(d.dimension == "structural_score" for d in regressions)

    def test_small_drop_within_threshold_is_not_regression(self, baselines_dir: Path) -> None:
        harness = RegressionHarness(
            baselines_dir=baselines_dir,
            thresholds={"structural_score": 0.05, "semantic_score": 0.05, "grounding_score": 0.05},
        )
        record = BaselineRecord(
            case_id="case_001",
            structural_score=0.9,
            semantic_score=0.85,
            grounding_score=1.0,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )
        harness.save_baseline(record)
        result = harness.compare("case_001", 0.87, 0.85, 1.0)
        assert result.regression_detected is False

    def test_improvement_is_not_regression(self, baselines_dir: Path) -> None:
        harness = RegressionHarness(baselines_dir=baselines_dir)
        record = BaselineRecord(
            case_id="case_001",
            structural_score=0.7,
            semantic_score=0.7,
            grounding_score=0.8,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )
        harness.save_baseline(record)
        result = harness.compare("case_001", 0.9, 0.9, 1.0)
        assert result.regression_detected is False


# ===========================================================================
# 6. EvalRunner Tests
# ===========================================================================

class TestEvalRunnerRunCase:
    @pytest.fixture()
    def runner(self, tmp_path: Path) -> EvalRunner:
        return EvalRunner(
            reasoning_engine=_StubEngine(),
            output_dir=tmp_path / "outputs",
        )

    @pytest.fixture()
    def case(self, tmp_path: Path) -> GoldenCase:
        root = tmp_path / "golden_cases"
        _write_valid_case(root, "case_001")
        return load_case("case_001", root)

    def test_run_case_returns_eval_result(
        self, runner: EvalRunner, case: GoldenCase
    ) -> None:
        result = runner.run_case(case)
        assert isinstance(result, EvalResult)
        assert result.case_id == "case_001"

    def test_run_case_produces_scores(
        self, runner: EvalRunner, case: GoldenCase
    ) -> None:
        result = runner.run_case(case)
        assert 0.0 <= result.structural_score <= 1.0
        assert 0.0 <= result.semantic_score <= 1.0
        assert 0.0 <= result.grounding_score <= 1.0

    def test_engine_exception_produces_fail_result(
        self, tmp_path: Path, case: GoldenCase
    ) -> None:
        runner = EvalRunner(
            reasoning_engine=_FailingEngine(),
            output_dir=tmp_path / "outputs",
        )
        result = runner.run_case(case)
        assert result.pass_fail is False
        assert any(e.error_type == ErrorType.extraction_error for e in result.error_types)

    def test_schema_violation_sets_schema_valid_false(
        self, tmp_path: Path, case: GoldenCase
    ) -> None:
        bad_record = {
            "chain_id": "bad-chain",
            "status": "completed",
            "pass_results": [
                {
                    "pass_id": "p1",
                    "pass_type": "transcript_extraction",
                    "pass_order": 1,
                    "latency_ms": 10,
                    "schema_validation": {
                        "schema_id": "some-schema",
                        "status": "failed",
                        "errors": ["required field missing"],
                    },
                    "_raw_output": {"action_items": []},
                    "output_ref": "artifact:p1:transcript_extraction",
                }
            ],
            "intermediate_artifacts": {},
        }
        runner = EvalRunner(
            reasoning_engine=_StubEngine(record=bad_record),
            output_dir=tmp_path / "outputs",
        )
        result = runner.run_case(case)
        assert result.schema_valid is False
        assert any(e.error_type == ErrorType.schema_violation for e in result.error_types)

    def test_regression_detected_when_baseline_fails(
        self, tmp_path: Path, case: GoldenCase
    ) -> None:
        baselines_dir = tmp_path / "baselines"
        harness = RegressionHarness(
            baselines_dir=baselines_dir,
            thresholds={"structural_score": 0.01, "semantic_score": 0.01, "grounding_score": 0.01},
        )
        # Save a baseline that is only achievable with perfect scores.
        # Use a stub engine that returns empty outputs so scores collapse to 0.
        harness.save_baseline(BaselineRecord(
            case_id="case_001",
            structural_score=0.9,
            semantic_score=0.9,
            grounding_score=1.0,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        ))
        # Engine returns no decisions/action_items/gaps → structural_score=0 → regression
        empty_record = {
            "chain_id": "empty-chain",
            "status": "completed",
            "pass_results": [],
            "intermediate_artifacts": {},
        }
        runner = EvalRunner(
            reasoning_engine=_StubEngine(record=empty_record),
            regression_harness=harness,
            output_dir=tmp_path / "outputs",
        )
        result = runner.run_case(case)
        assert result.regression_detected is True

    def test_latency_tracked_in_result(
        self, runner: EvalRunner, case: GoldenCase
    ) -> None:
        result = runner.run_case(case)
        assert result.latency_summary.total_latency_ms >= 0
        assert isinstance(result.latency_summary.per_pass_latency, dict)


class TestEvalRunnerDeterministicMode:
    def test_deterministic_mode_passes_temperature_zero(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "golden_cases"
        _write_valid_case(root, "case_001")
        case = load_case("case_001", root)
        engine = _StubEngine()
        runner = EvalRunner(
            reasoning_engine=engine,
            deterministic=True,
            output_dir=tmp_path / "outputs",
        )
        runner.run_case(case)
        assert engine.last_config is not None
        assert engine.last_config.get("temperature") == 0
        assert engine.last_config.get("seed") == 0

    def test_non_deterministic_mode_does_not_set_temperature(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "golden_cases"
        _write_valid_case(root, "case_001")
        case = load_case("case_001", root)
        engine = _StubEngine()
        runner = EvalRunner(
            reasoning_engine=engine,
            deterministic=False,
            output_dir=tmp_path / "outputs",
        )
        runner.run_case(case)
        config = engine.last_config or {}
        assert "temperature" not in config


class TestEvalRunnerRunAll:
    def test_run_all_cases_returns_one_result_per_case(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "golden_cases"
        _write_valid_case(root, "case_001")
        _write_valid_case(root, "case_002")
        dataset = load_all_cases(root)
        runner = EvalRunner(
            reasoning_engine=_StubEngine(),
            output_dir=tmp_path / "outputs",
        )
        results = runner.run_all_cases(dataset)
        assert len(results) == 2
        case_ids = {r.case_id for r in results}
        assert "case_001" in case_ids
        assert "case_002" in case_ids


class TestEvalRunnerWriteReport:
    def test_write_report_creates_valid_json(self, tmp_path: Path) -> None:
        root = tmp_path / "golden_cases"
        _write_valid_case(root, "case_001")
        dataset = load_all_cases(root)
        output_path = tmp_path / "outputs" / "eval_results.json"
        runner = EvalRunner(
            reasoning_engine=_StubEngine(),
            output_dir=tmp_path / "outputs",
        )
        results = runner.run_all_cases(dataset)
        written_path = runner.write_report(results, output_path=output_path)
        assert written_path.exists()
        report = json.loads(written_path.read_text(encoding="utf-8"))
        assert "summary" in report
        assert "results" in report
        assert report["summary"]["total_cases"] == 1
        assert isinstance(report["results"], list)

    def test_write_report_summary_counts(self, tmp_path: Path) -> None:
        root = tmp_path / "golden_cases"
        _write_valid_case(root, "case_001")
        _write_valid_case(root, "case_002")
        dataset = load_all_cases(root)
        output_path = tmp_path / "outputs" / "eval_results.json"
        runner = EvalRunner(
            reasoning_engine=_StubEngine(),
            output_dir=tmp_path / "outputs",
        )
        results = runner.run_all_cases(dataset)
        runner.write_report(results, output_path=output_path)
        report = json.loads(output_path.read_text(encoding="utf-8"))
        assert report["summary"]["total_cases"] == 2


# ===========================================================================
# 7. EvalResult Serialisation
# ===========================================================================

class TestEvalResultToDict:
    def test_to_dict_round_trip(self, tmp_path: Path) -> None:
        root = tmp_path / "golden_cases"
        _write_valid_case(root, "case_001")
        case = load_case("case_001", root)
        runner = EvalRunner(
            reasoning_engine=_StubEngine(),
            output_dir=tmp_path / "outputs",
        )
        result = runner.run_case(case)
        d = result.to_dict()
        assert d["case_id"] == "case_001"
        assert isinstance(d["pass_fail"], bool)
        assert "structural_score" in d
        assert "semantic_score" in d
        assert "grounding_score" in d
        assert "latency_summary" in d
        assert "error_types" in d
        # Ensure it's JSON-serialisable
        json.dumps(d)
