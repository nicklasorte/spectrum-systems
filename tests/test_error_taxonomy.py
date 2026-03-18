"""
Tests for the Error Taxonomy System (Prompt AU).

Covers:
- Catalog schema validation
- Catalog loading, lookup, and list operations
- normalize_eval_error: correct codes for each failure type
- normalize_feedback_error: correct codes for each action/failure_type
- normalize_observability_error: correct codes from flag/score signals
- normalize_regression_error: correct REGRESS.* codes from dimensions
- ErrorClassificationRecord: round-trip serialisation
- ErrorClassificationRecord: schema validation
- ErrorClassificationRecord: save/load/list_all
- ErrorClassifier: classify_eval_result
- ErrorClassifier: classify_feedback_record
- ErrorClassifier: classify_observability_record
- ErrorClassifier: classify_regression_report
- ErrorClassifier: classify_many
- Backward compatibility bridge: map_legacy_error_type
- Backward compatibility bridge: map_failure_type_string
- Backward compatibility bridge: infer_from_grounding_failure
- Backward compatibility bridge: infer_from_regression_dimension
- Aggregation: count_by_family
- Aggregation: count_by_subtype
- Aggregation: count_by_remediation_target
- Aggregation: count_by_source_system
- Aggregation: count_by_pass_type
- Aggregation: identify_highest_impact_subtypes
- CLI smoke test: --all flag with no records
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime, timezone

import pytest

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------

from spectrum_systems.modules.error_taxonomy.catalog import (
    ErrorSubtype,
    ErrorFamily,
    ErrorTaxonomyCatalog,
)
from spectrum_systems.modules.error_taxonomy.normalize import (
    ClassificationResult,
    normalize_eval_error,
    normalize_feedback_error,
    normalize_observability_error,
    normalize_regression_error,
)
from spectrum_systems.modules.error_taxonomy.classify import (
    ErrorClassificationRecord,
    ErrorClassifier,
)
from spectrum_systems.modules.error_taxonomy.bridge import (
    map_legacy_error_type,
    map_failure_type_string,
    infer_from_grounding_failure,
    infer_from_regression_dimension,
)
from spectrum_systems.modules.error_taxonomy.aggregation import (
    count_by_family,
    count_by_subtype,
    count_by_remediation_target,
    count_by_source_system,
    count_by_pass_type,
    identify_highest_impact_subtypes,
)
from spectrum_systems.modules.evaluation.error_taxonomy import ErrorType


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture()
def catalog() -> ErrorTaxonomyCatalog:
    return ErrorTaxonomyCatalog.load_catalog()


@pytest.fixture()
def tmp_store(tmp_path: Path) -> Path:
    return tmp_path / "error_classifications"


@pytest.fixture()
def classifier(tmp_store: Path) -> ErrorClassifier:
    cat = ErrorTaxonomyCatalog.load_catalog()
    return ErrorClassifier(catalog=cat, store_dir=tmp_store)


def _make_record(
    *,
    error_codes: List[str],
    source_system: str = "evaluation",
    pass_type: str = "extraction",
    artifact_id: str = "artifact-001",
) -> ErrorClassificationRecord:
    """Build a minimal ErrorClassificationRecord for testing."""
    return ErrorClassificationRecord(
        classification_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        context={
            "source_system": source_system,
            "artifact_id": artifact_id,
            "pass_type": pass_type,
        },
        classifications=[
            {
                "error_code": code,
                "confidence": 0.85,
                "evidence_source": "test",
                "explanation": f"Test entry for {code}",
            }
            for code in error_codes
        ],
        raw_inputs={"test": True},
        taxonomy_version="1.0.0",
    )


# ===========================================================================
# 1. Catalog Schema Validation
# ===========================================================================

class TestCatalogSchemaValidation:
    def test_catalog_validates_against_schema(self, catalog: ErrorTaxonomyCatalog) -> None:
        errors = catalog.validate_against_schema()
        assert errors == [], f"Catalog schema errors: {errors}"

    def test_catalog_has_required_properties(self, catalog: ErrorTaxonomyCatalog) -> None:
        assert catalog.taxonomy_id
        assert catalog.version
        assert catalog.description

    def test_catalog_has_all_required_families(self, catalog: ErrorTaxonomyCatalog) -> None:
        expected = {"INPUT", "EXTRACT", "REASON", "GROUND", "SCHEMA", "HALLUC", "REGRESS", "RETRIEVE", "HUMAN"}
        actual = {f.family_code for f in catalog.list_families()}
        assert expected.issubset(actual), f"Missing families: {expected - actual}"

    def test_all_required_subtypes_present(self, catalog: ErrorTaxonomyCatalog) -> None:
        required_codes = [
            "INPUT.BAD_TRANSCRIPT_QUALITY",
            "INPUT.BAD_SLIDE_QUALITY",
            "INPUT.MISSING_CONTEXT",
            "EXTRACT.MISSED_DECISION",
            "EXTRACT.MISSED_ACTION_ITEM",
            "EXTRACT.FALSE_EXTRACTION",
            "EXTRACT.SPAN_BOUNDARY_ERROR",
            "REASON.BAD_INFERENCE",
            "REASON.CONTRADICTION_MISSED",
            "REASON.GAP_MISSED",
            "REASON.OVERSTATED_CONCLUSION",
            "GROUND.MISSING_REF",
            "GROUND.INVALID_REF",
            "GROUND.WEAK_SUPPORT",
            "GROUND.UNTRACEABLE_CLAIM",
            "SCHEMA.INVALID_OUTPUT",
            "SCHEMA.MISSING_REQUIRED_FIELD",
            "SCHEMA.TYPE_MISMATCH",
            "HALLUC.UNSUPPORTED_ASSERTION",
            "HALLUC.INVENTED_DETAIL",
            "REGRESS.STRUCTURAL_DROP",
            "REGRESS.SEMANTIC_DROP",
            "REGRESS.GROUNDING_DROP",
            "REGRESS.LATENCY_SPIKE",
            "RETRIEVE.IRRELEVANT_MEMORY",
            "RETRIEVE.MISSED_RELEVANT_MEMORY",
            "HUMAN.REVIEWER_DISAGREEMENT",
            "HUMAN.NEEDS_SUPPORT",
            "HUMAN.REWRITE_REQUIRED",
        ]
        for code in required_codes:
            assert catalog.get_error(code) is not None, f"Missing subtype: {code}"

    def test_subtype_severity_is_valid(self, catalog: ErrorTaxonomyCatalog) -> None:
        valid = {"low", "medium", "high", "critical"}
        for st in catalog.list_subtypes():
            assert st.default_severity in valid, f"{st.error_code} has invalid severity: {st.default_severity}"

    def test_subtype_remediation_target_is_valid(self, catalog: ErrorTaxonomyCatalog) -> None:
        valid = {
            "prompt", "schema", "grounding", "model",
            "input_quality", "retrieval", "pipeline_control", "human_process",
        }
        for st in catalog.list_subtypes():
            assert st.remediation_target in valid, f"{st.error_code} has invalid target: {st.remediation_target}"


# ===========================================================================
# 2. Catalog API
# ===========================================================================

class TestCatalogAPI:
    def test_get_error_known_code(self, catalog: ErrorTaxonomyCatalog) -> None:
        st = catalog.get_error("GROUND.MISSING_REF")
        assert st is not None
        assert st.error_code == "GROUND.MISSING_REF"
        assert st.family_code == "GROUND"

    def test_get_error_unknown_returns_none(self, catalog: ErrorTaxonomyCatalog) -> None:
        assert catalog.get_error("FAKE.CODE") is None

    def test_list_families_returns_all(self, catalog: ErrorTaxonomyCatalog) -> None:
        families = catalog.list_families()
        assert len(families) >= 9

    def test_list_subtypes_all(self, catalog: ErrorTaxonomyCatalog) -> None:
        all_st = catalog.list_subtypes()
        assert len(all_st) >= 29  # at least the specified subtypes

    def test_list_subtypes_by_family(self, catalog: ErrorTaxonomyCatalog) -> None:
        extract = catalog.list_subtypes("EXTRACT")
        assert len(extract) >= 4
        assert all(st.family_code == "EXTRACT" for st in extract)

    def test_list_subtypes_unknown_family(self, catalog: ErrorTaxonomyCatalog) -> None:
        assert catalog.list_subtypes("NONEXISTENT") == []

    def test_is_valid_code(self, catalog: ErrorTaxonomyCatalog) -> None:
        assert catalog.is_valid_code("GROUND.MISSING_REF")
        assert not catalog.is_valid_code("FAKE.CODE")

    def test_load_catalog_from_custom_path(self, tmp_path: Path) -> None:
        """Loading catalog from an explicit path works."""
        default_path = Path(__file__).resolve().parents[1] / "config" / "error_taxonomy_catalog.json"
        import shutil
        copy_path = tmp_path / "catalog.json"
        shutil.copy(default_path, copy_path)
        cat = ErrorTaxonomyCatalog.load_catalog(str(copy_path))
        assert cat.taxonomy_id

    def test_family_to_dict(self, catalog: ErrorTaxonomyCatalog) -> None:
        fam = catalog.get_family("GROUND")
        assert fam is not None
        d = fam.to_dict()
        assert d["family_code"] == "GROUND"
        assert "subtypes" in d

    def test_subtype_to_dict(self, catalog: ErrorTaxonomyCatalog) -> None:
        st = catalog.get_error("GROUND.MISSING_REF")
        d = st.to_dict()
        assert d["error_code"] == "GROUND.MISSING_REF"
        assert "remediation_target" in d


# ===========================================================================
# 3. Normalization — Eval
# ===========================================================================

class TestNormalizeEvalError:
    def test_schema_errors_produces_schema_code(self) -> None:
        results = normalize_eval_error({"schema_errors": ["'decisions' is required"]})
        codes = [r.error_code for r in results]
        assert any(c.startswith("SCHEMA.") for c in codes)

    def test_missing_refs_produces_ground_missing_ref(self) -> None:
        results = normalize_eval_error({"missing_refs": ["ref-1"], "upstream_pass_refs": ["ref-1", "ref-2"]})
        codes = [r.error_code for r in results]
        assert "GROUND.MISSING_REF" in codes

    def test_all_refs_missing_produces_hallucination(self) -> None:
        results = normalize_eval_error({
            "missing_refs": ["ref-1", "ref-2"],
            "upstream_pass_refs": ["ref-1", "ref-2"],
        })
        codes = [r.error_code for r in results]
        assert "HALLUC.UNSUPPORTED_ASSERTION" in codes

    def test_mismatched_refs_produces_weak_support(self) -> None:
        results = normalize_eval_error({"mismatched_refs": ["ref-1"]})
        codes = [r.error_code for r in results]
        assert "GROUND.WEAK_SUPPORT" in codes

    def test_reasoning_pass_type(self) -> None:
        results = normalize_eval_error({"pass_type": "contradiction_detection"})
        codes = [r.error_code for r in results]
        assert "REASON.CONTRADICTION_MISSED" in codes

    def test_gap_detection_pass_type(self) -> None:
        results = normalize_eval_error({"pass_type": "gap_detection"})
        codes = [r.error_code for r in results]
        assert "REASON.GAP_MISSED" in codes

    def test_extraction_pass_type(self) -> None:
        results = normalize_eval_error({"pass_type": "action_item_extraction"})
        codes = [r.error_code for r in results]
        assert "EXTRACT.MISSED_ACTION_ITEM" in codes

    def test_regression_flag(self) -> None:
        results = normalize_eval_error({"regression": True})
        codes = [r.error_code for r in results]
        assert any(c.startswith("REGRESS.") for c in codes)

    def test_empty_failure_info_produces_fallback(self) -> None:
        results = normalize_eval_error({})
        assert len(results) >= 1
        assert all(isinstance(r, ClassificationResult) for r in results)

    def test_confidence_in_range(self) -> None:
        results = normalize_eval_error({"schema_errors": ["error"]})
        for r in results:
            assert 0.0 <= r.confidence <= 1.0


# ===========================================================================
# 4. Normalization — Feedback
# ===========================================================================

class TestNormalizeFeedbackError:
    def test_needs_support_action(self) -> None:
        results = normalize_feedback_error({"action": "needs_support", "failure_type": "unclear"})
        codes = [r.error_code for r in results]
        assert "HUMAN.NEEDS_SUPPORT" in codes

    def test_needs_support_also_adds_weak_support(self) -> None:
        results = normalize_feedback_error({"action": "needs_support", "failure_type": "unclear"})
        codes = [r.error_code for r in results]
        assert "GROUND.WEAK_SUPPORT" in codes

    def test_rewrite_action(self) -> None:
        results = normalize_feedback_error({"action": "rewrite", "failure_type": "unclear"})
        codes = [r.error_code for r in results]
        assert "HUMAN.REWRITE_REQUIRED" in codes

    def test_explicit_grounding_failure(self) -> None:
        results = normalize_feedback_error({"failure_type": "grounding_failure", "action": "reject"})
        codes = [r.error_code for r in results]
        assert "GROUND.MISSING_REF" in codes

    def test_explicit_hallucination(self) -> None:
        results = normalize_feedback_error({"failure_type": "hallucination", "action": "reject"})
        codes = [r.error_code for r in results]
        assert "HALLUC.UNSUPPORTED_ASSERTION" in codes

    def test_reject_action_fallback(self) -> None:
        results = normalize_feedback_error({"action": "reject", "failure_type": "unclear"})
        codes = [r.error_code for r in results]
        assert len(codes) >= 1

    def test_empty_dict_produces_fallback(self) -> None:
        results = normalize_feedback_error({})
        assert len(results) >= 1


# ===========================================================================
# 5. Normalization — Observability
# ===========================================================================

class TestNormalizeObservabilityError:
    def test_schema_valid_false(self) -> None:
        obs = {"flags": {"schema_valid": False, "grounding_passed": True, "regression_passed": True, "human_disagrees": False}}
        results = normalize_observability_error(obs)
        codes = [r.error_code for r in results]
        assert "SCHEMA.INVALID_OUTPUT" in codes

    def test_grounding_passed_false(self) -> None:
        obs = {
            "flags": {"schema_valid": True, "grounding_passed": False, "regression_passed": True, "human_disagrees": False},
            "scores": {"grounding_score": 0.5},
        }
        results = normalize_observability_error(obs)
        codes = [r.error_code for r in results]
        assert any(c.startswith("GROUND.") or c.startswith("HALLUC.") for c in codes)

    def test_grounding_score_zero_produces_hallucination(self) -> None:
        obs = {
            "flags": {"schema_valid": True, "grounding_passed": False, "regression_passed": True, "human_disagrees": False},
            "scores": {"grounding_score": 0.0},
        }
        results = normalize_observability_error(obs)
        codes = [r.error_code for r in results]
        assert "HALLUC.UNSUPPORTED_ASSERTION" in codes

    def test_regression_passed_false(self) -> None:
        obs = {"flags": {"schema_valid": True, "grounding_passed": True, "regression_passed": False, "human_disagrees": False}}
        results = normalize_observability_error(obs)
        codes = [r.error_code for r in results]
        assert any(c.startswith("REGRESS.") for c in codes)

    def test_human_disagrees_true(self) -> None:
        obs = {"flags": {"schema_valid": True, "grounding_passed": True, "regression_passed": True, "human_disagrees": True}}
        results = normalize_observability_error(obs)
        codes = [r.error_code for r in results]
        assert "HUMAN.REVIEWER_DISAGREEMENT" in codes

    def test_error_types_legacy(self) -> None:
        obs = {"error_types": ["hallucination"], "flags": {}}
        results = normalize_observability_error(obs)
        codes = [r.error_code for r in results]
        assert "HALLUC.UNSUPPORTED_ASSERTION" in codes

    def test_all_good_flags_produces_fallback(self) -> None:
        obs = {"flags": {"schema_valid": True, "grounding_passed": True, "regression_passed": True, "human_disagrees": False}}
        results = normalize_observability_error(obs)
        assert len(results) >= 1


# ===========================================================================
# 6. Normalization — Regression
# ===========================================================================

class TestNormalizeRegressionError:
    def test_grounding_score_dimension(self) -> None:
        entry = {"dimension": "grounding_score", "delta": -0.05, "severity": "hard_fail", "explanation": "Drop"}
        results = normalize_regression_error(entry)
        assert results[0].error_code == "REGRESS.GROUNDING_DROP"
        assert results[0].confidence == 0.90

    def test_structural_score_dimension(self) -> None:
        entry = {"dimension": "structural_score", "delta": -0.08, "severity": "hard_fail", "explanation": "Drop"}
        results = normalize_regression_error(entry)
        assert results[0].error_code == "REGRESS.STRUCTURAL_DROP"

    def test_semantic_score_dimension(self) -> None:
        entry = {"dimension": "semantic_score", "delta": -0.10, "severity": "warning"}
        results = normalize_regression_error(entry)
        assert results[0].error_code == "REGRESS.SEMANTIC_DROP"
        assert results[0].confidence == 0.75

    def test_latency_dimension(self) -> None:
        entry = {"dimension": "latency", "delta": 500.0, "severity": "warning"}
        results = normalize_regression_error(entry)
        assert results[0].error_code == "REGRESS.LATENCY_SPIKE"

    def test_unknown_dimension_fallback(self) -> None:
        entry = {"dimension": "unknown_metric", "delta": -0.1, "severity": "warning"}
        results = normalize_regression_error(entry)
        assert len(results) >= 1
        assert results[0].confidence < 0.5  # low confidence fallback


# ===========================================================================
# 7. ErrorClassificationRecord
# ===========================================================================

class TestErrorClassificationRecord:
    def test_round_trip_serialisation(self) -> None:
        rec = _make_record(error_codes=["GROUND.MISSING_REF", "HUMAN.NEEDS_SUPPORT"])
        data = rec.to_dict()
        restored = ErrorClassificationRecord.from_dict(data)
        assert restored.classification_id == rec.classification_id
        assert len(restored.classifications) == 2

    def test_schema_validation_valid_record(self) -> None:
        rec = _make_record(error_codes=["GROUND.MISSING_REF"])
        errors = rec.validate_against_schema()
        assert errors == [], f"Schema errors: {errors}"

    def test_schema_validation_missing_required_field(self) -> None:
        rec = _make_record(error_codes=["GROUND.MISSING_REF"])
        data = rec.to_dict()
        del data["taxonomy_version"]
        rec2 = ErrorClassificationRecord.from_dict({**data, "taxonomy_version": "1.0.0"})
        # Manually break it for validation
        bad_data = {k: v for k, v in data.items() if k != "taxonomy_version"}
        # Can't directly instantiate without taxonomy_version but can test dict
        import jsonschema
        schema_path = (
            Path(__file__).resolve().parents[1]
            / "contracts" / "schemas" / "error_classification_record.schema.json"
        )
        with open(schema_path) as f:
            schema = json.load(f)
        errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad_data))
        assert len(errors) > 0

    def test_save_and_load(self, tmp_store: Path) -> None:
        rec = _make_record(error_codes=["GROUND.MISSING_REF"])
        path = rec.save(tmp_store)
        assert path.exists()
        loaded = ErrorClassificationRecord.load(rec.classification_id, tmp_store)
        assert loaded.classification_id == rec.classification_id

    def test_save_duplicate_raises(self, tmp_store: Path) -> None:
        rec = _make_record(error_codes=["GROUND.MISSING_REF"])
        rec.save(tmp_store)
        with pytest.raises(FileExistsError):
            rec.save(tmp_store)

    def test_load_nonexistent_raises(self, tmp_store: Path) -> None:
        with pytest.raises(FileNotFoundError):
            ErrorClassificationRecord.load("nonexistent-id", tmp_store)

    def test_list_all_empty(self, tmp_store: Path) -> None:
        records = ErrorClassificationRecord.list_all(tmp_store)
        assert records == []

    def test_list_all_returns_saved_records(self, tmp_store: Path) -> None:
        r1 = _make_record(error_codes=["GROUND.MISSING_REF"])
        r2 = _make_record(error_codes=["EXTRACT.MISSED_DECISION"])
        r1.save(tmp_store)
        r2.save(tmp_store)
        loaded = ErrorClassificationRecord.list_all(tmp_store)
        assert len(loaded) == 2


# ===========================================================================
# 8. ErrorClassifier
# ===========================================================================

class TestErrorClassifier:
    def test_classify_eval_result_schema_error(self, classifier: ErrorClassifier) -> None:
        eval_result = {"schema_errors": ["'decisions' is required"], "pass_type": "extraction"}
        rec = classifier.classify_eval_result(eval_result)
        codes = [e["error_code"] for e in rec.classifications]
        assert any(c.startswith("SCHEMA.") for c in codes)
        assert rec.context["source_system"] == "evaluation"

    def test_classify_eval_result_grounding_failure(self, classifier: ErrorClassifier) -> None:
        eval_result = {"missing_refs": ["ref-1"], "upstream_pass_refs": ["ref-1", "ref-2"]}
        rec = classifier.classify_eval_result(eval_result)
        codes = [e["error_code"] for e in rec.classifications]
        assert "GROUND.MISSING_REF" in codes

    def test_classify_eval_result_hallucination(self, classifier: ErrorClassifier) -> None:
        eval_result = {
            "missing_refs": ["ref-1"],
            "upstream_pass_refs": ["ref-1"],
        }
        rec = classifier.classify_eval_result(eval_result)
        codes = [e["error_code"] for e in rec.classifications]
        assert "HALLUC.UNSUPPORTED_ASSERTION" in codes

    def test_classify_feedback_needs_support(self, classifier: ErrorClassifier) -> None:
        feedback = {
            "failure_type": "grounding_failure",
            "action": "needs_support",
            "artifact_id": "art-001",
            "artifact_type": "meeting_minutes",
        }
        rec = classifier.classify_feedback_record(feedback)
        codes = [e["error_code"] for e in rec.classifications]
        assert "HUMAN.NEEDS_SUPPORT" in codes
        assert rec.context["source_system"] == "feedback"

    def test_classify_observability_record(self, classifier: ErrorClassifier) -> None:
        obs = {
            "artifact_id": "art-001",
            "pass_type": "extraction",
            "flags": {
                "schema_valid": True,
                "grounding_passed": False,
                "regression_passed": True,
                "human_disagrees": False,
            },
            "scores": {"grounding_score": 0.3},
            "error_summary": {"error_types": [], "failure_count": 1},
        }
        rec = classifier.classify_observability_record(obs)
        codes = [e["error_code"] for e in rec.classifications]
        assert any(c.startswith("GROUND.") or c.startswith("HALLUC.") for c in codes)
        assert rec.context["source_system"] == "observability"

    def test_classify_regression_report(self, classifier: ErrorClassifier) -> None:
        report = {
            "report_id": "rep-001",
            "summary": {"overall_pass": False, "hard_failures": 1, "warnings": 0, "cases_compared": 5, "passes_compared": 10},
            "worst_regressions": [
                {"dimension": "grounding_score", "delta": -0.05, "severity": "hard_fail", "explanation": "Grounding dropped"},
                {"dimension": "semantic_score", "delta": -0.10, "severity": "warning", "explanation": "Semantic dropped"},
            ],
        }
        records = classifier.classify_regression_report(report)
        assert len(records) == 2
        codes_0 = [e["error_code"] for e in records[0].classifications]
        assert "REGRESS.GROUNDING_DROP" in codes_0

    def test_classify_regression_report_empty_worst(self, classifier: ErrorClassifier) -> None:
        report = {
            "report_id": "rep-002",
            "summary": {"overall_pass": False, "hard_failures": 1, "warnings": 0, "cases_compared": 5, "passes_compared": 10},
            "worst_regressions": [],
        }
        records = classifier.classify_regression_report(report)
        assert len(records) == 1

    def test_classify_many_evaluation(self, classifier: ErrorClassifier) -> None:
        items = [
            {"schema_errors": ["error1"]},
            {"missing_refs": ["ref-1"]},
        ]
        records = classifier.classify_many(items, "evaluation")
        assert len(records) == 2

    def test_classify_many_feedback(self, classifier: ErrorClassifier) -> None:
        items = [
            {"failure_type": "grounding_failure", "action": "needs_support"},
        ]
        records = classifier.classify_many(items, "feedback")
        assert len(records) == 1

    def test_classify_many_unknown_source_raises(self, classifier: ErrorClassifier) -> None:
        with pytest.raises(ValueError, match="Unknown source_system"):
            classifier.classify_many([], "invalid_source")

    def test_raw_inputs_preserved(self, classifier: ErrorClassifier) -> None:
        eval_result = {"schema_errors": ["err"], "my_custom_field": "preserved"}
        rec = classifier.classify_eval_result(eval_result)
        assert rec.raw_inputs.get("my_custom_field") == "preserved"

    def test_taxonomy_version_recorded(self, classifier: ErrorClassifier) -> None:
        rec = classifier.classify_eval_result({"schema_errors": ["err"]})
        assert rec.taxonomy_version  # must not be empty


# ===========================================================================
# 9. Backward Compatibility Bridge
# ===========================================================================

class TestBridge:
    def test_map_legacy_error_type_extraction(self) -> None:
        codes = map_legacy_error_type(ErrorType.extraction_error)
        assert "EXTRACT.MISSED_DECISION" in codes

    def test_map_legacy_error_type_reasoning(self) -> None:
        codes = map_legacy_error_type(ErrorType.reasoning_error)
        assert "REASON.BAD_INFERENCE" in codes

    def test_map_legacy_error_type_grounding(self) -> None:
        codes = map_legacy_error_type(ErrorType.grounding_failure)
        assert "GROUND.MISSING_REF" in codes

    def test_map_legacy_error_type_schema(self) -> None:
        codes = map_legacy_error_type(ErrorType.schema_violation)
        assert "SCHEMA.INVALID_OUTPUT" in codes

    def test_map_legacy_error_type_hallucination(self) -> None:
        codes = map_legacy_error_type(ErrorType.hallucination)
        assert "HALLUC.UNSUPPORTED_ASSERTION" in codes

    def test_map_legacy_error_type_regression(self) -> None:
        codes = map_legacy_error_type(ErrorType.regression_failure)
        assert "REGRESS.STRUCTURAL_DROP" in codes

    def test_map_legacy_error_type_all_enum_values(self) -> None:
        """All ErrorType values must map without error."""
        for et in ErrorType:
            codes = map_legacy_error_type(et)
            assert len(codes) >= 1

    def test_map_failure_type_string(self) -> None:
        assert "GROUND.MISSING_REF" in map_failure_type_string("grounding_failure")
        assert "HALLUC.UNSUPPORTED_ASSERTION" in map_failure_type_string("hallucination")
        assert "SCHEMA.INVALID_OUTPUT" in map_failure_type_string("schema_violation")

    def test_map_failure_type_string_unknown_fallback(self) -> None:
        codes = map_failure_type_string("totally_unknown")
        assert len(codes) >= 1

    def test_infer_from_grounding_failure_all_missing(self) -> None:
        codes = infer_from_grounding_failure(["ref-1"], [], declared_refs=["ref-1"])
        assert "HALLUC.UNSUPPORTED_ASSERTION" in codes

    def test_infer_from_grounding_failure_partial_missing(self) -> None:
        codes = infer_from_grounding_failure(["ref-1"], [], declared_refs=["ref-1", "ref-2"])
        assert "GROUND.MISSING_REF" in codes

    def test_infer_from_grounding_failure_mismatched(self) -> None:
        codes = infer_from_grounding_failure([], ["ref-1"])
        assert "GROUND.WEAK_SUPPORT" in codes

    def test_infer_from_regression_dimension_grounding(self) -> None:
        assert infer_from_regression_dimension("grounding_score") == "REGRESS.GROUNDING_DROP"

    def test_infer_from_regression_dimension_structural(self) -> None:
        assert infer_from_regression_dimension("structural_score") == "REGRESS.STRUCTURAL_DROP"

    def test_infer_from_regression_dimension_latency(self) -> None:
        assert infer_from_regression_dimension("latency") == "REGRESS.LATENCY_SPIKE"

    def test_infer_from_regression_dimension_unknown(self) -> None:
        code = infer_from_regression_dimension("some_unknown_dim")
        assert code  # must not be empty


# ===========================================================================
# 10. Aggregation
# ===========================================================================

@pytest.fixture()
def sample_records() -> List[ErrorClassificationRecord]:
    return [
        _make_record(error_codes=["GROUND.MISSING_REF", "HUMAN.NEEDS_SUPPORT"], source_system="evaluation", pass_type="extraction"),
        _make_record(error_codes=["GROUND.MISSING_REF"], source_system="feedback", pass_type="extraction"),
        _make_record(error_codes=["EXTRACT.MISSED_DECISION"], source_system="evaluation", pass_type="action_item_extraction"),
        _make_record(error_codes=["REGRESS.GROUNDING_DROP"], source_system="regression", pass_type=""),
        _make_record(error_codes=["SCHEMA.INVALID_OUTPUT"], source_system="observability", pass_type="extraction"),
    ]


class TestAggregation:
    def test_count_by_family(self, sample_records: List[ErrorClassificationRecord]) -> None:
        counts = count_by_family(sample_records)
        assert counts.get("GROUND", 0) == 2
        assert counts.get("EXTRACT", 0) == 1
        assert counts.get("HUMAN", 0) == 1

    def test_count_by_subtype(self, sample_records: List[ErrorClassificationRecord]) -> None:
        counts = count_by_subtype(sample_records)
        assert counts.get("GROUND.MISSING_REF", 0) == 2
        assert counts.get("EXTRACT.MISSED_DECISION", 0) == 1

    def test_count_by_source_system(self, sample_records: List[ErrorClassificationRecord]) -> None:
        counts = count_by_source_system(sample_records)
        # evaluation has 2 records × their classification counts
        assert "evaluation" in counts
        assert "feedback" in counts
        assert "regression" in counts

    def test_count_by_pass_type(self, sample_records: List[ErrorClassificationRecord]) -> None:
        counts = count_by_pass_type(sample_records)
        assert "extraction" in counts
        assert counts["extraction"] >= 3

    def test_count_by_remediation_target(
        self,
        sample_records: List[ErrorClassificationRecord],
        catalog: ErrorTaxonomyCatalog,
    ) -> None:
        counts = count_by_remediation_target(sample_records, catalog)
        assert "grounding" in counts  # GROUND.MISSING_REF → grounding

    def test_identify_highest_impact_subtypes(
        self,
        sample_records: List[ErrorClassificationRecord],
        catalog: ErrorTaxonomyCatalog,
    ) -> None:
        top = identify_highest_impact_subtypes(sample_records, catalog, top_n=5)
        assert len(top) <= 5
        assert all("impact_score" in item for item in top)
        # First entry should have highest impact score
        if len(top) > 1:
            assert top[0]["impact_score"] >= top[1]["impact_score"]

    def test_aggregation_empty_records(self, catalog: ErrorTaxonomyCatalog) -> None:
        assert count_by_family([]) == {}
        assert count_by_subtype([]) == {}
        assert count_by_source_system([]) == {}
        assert count_by_remediation_target([], catalog) == {}
        assert identify_highest_impact_subtypes([], catalog) == []


# ===========================================================================
# 11. CLI Smoke Tests
# ===========================================================================

class TestCLISmoke:
    def test_run_report_all_no_records(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI exits cleanly when no records exist."""
        import scripts.run_error_taxonomy_report as cli_module

        monkeypatch.setattr(cli_module, "_STORE_DIR", tmp_path / "empty_store")
        monkeypatch.setattr(cli_module, "_OUTPUTS_DIR", tmp_path / "outputs")

        # Patch sys.argv and run
        monkeypatch.setattr(sys, "argv", ["run_error_taxonomy_report.py", "--all"])
        # Should exit with 0 cleanly
        with pytest.raises(SystemExit) as exc_info:
            cli_module.main()
        assert exc_info.value.code == 0

    def test_run_report_all_with_records(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CLI produces a JSON report when records exist."""
        import scripts.run_error_taxonomy_report as cli_module

        store_dir = tmp_path / "classifications"
        outputs_dir = tmp_path / "outputs"
        monkeypatch.setattr(cli_module, "_STORE_DIR", store_dir)
        monkeypatch.setattr(cli_module, "_OUTPUTS_DIR", outputs_dir)

        # Plant a record
        rec = _make_record(error_codes=["GROUND.MISSING_REF"])
        rec.save(store_dir)

        monkeypatch.setattr(sys, "argv", ["run_error_taxonomy_report.py", "--all"])
        cli_module.main()

        report_path = outputs_dir / "error_taxonomy_report.json"
        assert report_path.exists()
        with open(report_path) as fh:
            report = json.load(fh)
        assert report["report_type"] == "error_taxonomy_report"
        assert report["summary"]["record_count"] == 1

    def test_run_report_filter_by_case(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CLI --case filter works correctly."""
        import scripts.run_error_taxonomy_report as cli_module

        store_dir = tmp_path / "classifications"
        outputs_dir = tmp_path / "outputs"
        monkeypatch.setattr(cli_module, "_STORE_DIR", store_dir)
        monkeypatch.setattr(cli_module, "_OUTPUTS_DIR", outputs_dir)

        # Record with case_id
        rec = ErrorClassificationRecord(
            classification_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            context={"source_system": "evaluation", "case_id": "case-001"},
            classifications=[{"error_code": "GROUND.MISSING_REF", "confidence": 0.9, "evidence_source": "test", "explanation": "test"}],
            raw_inputs={},
            taxonomy_version="1.0.0",
        )
        rec.save(store_dir)

        monkeypatch.setattr(sys, "argv", ["run_error_taxonomy_report.py", "--case", "case-001"])
        cli_module.main()

        with open(outputs_dir / "error_taxonomy_report.json") as fh:
            report = json.load(fh)
        assert report["summary"]["record_count"] == 1


# ===========================================================================
# 12. Error Classification Record Schema Validation
# ===========================================================================

class TestClassificationRecordSchema:
    def test_valid_record_passes_schema(self) -> None:
        rec = _make_record(error_codes=["GROUND.MISSING_REF"])
        errors = rec.validate_against_schema()
        assert errors == []

    def test_multiple_classifications_pass_schema(self) -> None:
        rec = _make_record(error_codes=["GROUND.MISSING_REF", "HALLUC.UNSUPPORTED_ASSERTION"])
        errors = rec.validate_against_schema()
        assert errors == []

    def test_confidence_out_of_range_fails_schema(self) -> None:
        rec = ErrorClassificationRecord(
            classification_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            context={"source_system": "evaluation"},
            classifications=[{
                "error_code": "GROUND.MISSING_REF",
                "confidence": 1.5,  # invalid — > 1.0
                "evidence_source": "test",
                "explanation": "test",
            }],
            raw_inputs={},
            taxonomy_version="1.0.0",
        )
        errors = rec.validate_against_schema()
        assert len(errors) > 0

    def test_invalid_source_system_fails_schema(self) -> None:
        rec = ErrorClassificationRecord(
            classification_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            context={"source_system": "not_a_real_system"},
            classifications=[{
                "error_code": "GROUND.MISSING_REF",
                "confidence": 0.9,
                "evidence_source": "test",
                "explanation": "test",
            }],
            raw_inputs={},
            taxonomy_version="1.0.0",
        )
        errors = rec.validate_against_schema()
        assert len(errors) > 0
