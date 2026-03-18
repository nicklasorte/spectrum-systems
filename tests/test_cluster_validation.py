"""
Tests for the AW0 Cluster Validation Layer (Prompt AW0).

Covers:
- ValidatedCluster: serialisation round-trip
- ValidatedCluster: schema validation
- ClusterValidator: SIZE CHECK (rule A)
- ClusterValidator: COHESION CHECK (rule B)
- ClusterValidator: PASS CONSISTENCY (rule C)
- ClusterValidator: STABILITY CHECK (rule D)
- ClusterValidator: ACTIONABILITY CHECK (rule E)
- ClusterValidator: CONFIDENCE CHECK (rule F)
- ClusterValidator: edge cases (mixed error codes, small clusters)
- Scoring: cohesion_score, actionability_score, stability_score
- Pipeline integration: validate_clusters()
- Schema file: validated_cluster.schema.json exists
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

from spectrum_systems.modules.error_taxonomy.catalog import ErrorTaxonomyCatalog
from spectrum_systems.modules.error_taxonomy.classify import ErrorClassificationRecord
from spectrum_systems.modules.error_taxonomy.clustering import ErrorCluster, ErrorClusterer
from spectrum_systems.modules.error_taxonomy.cluster_validation import (
    ClusterValidator,
    ValidatedCluster,
)
from spectrum_systems.modules.error_taxonomy.cluster_pipeline import (
    build_clusters_from_classifications,
    validate_clusters,
)
from spectrum_systems.modules.error_taxonomy.validated_cluster_store import (
    save_validated_cluster,
    load_validated_clusters,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parents[1]


def _make_record(
    *,
    error_codes: List[str],
    source_system: str = "evaluation",
    pass_type: str = "extraction",
    artifact_id: str = "artifact-001",
    artifact_type: str = "working_paper",
    taxonomy_version: str = "1.0.0",
    confidence: float = 0.85,
) -> ErrorClassificationRecord:
    return ErrorClassificationRecord(
        classification_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        context={
            "source_system": source_system,
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "pass_type": pass_type,
        },
        classifications=[
            {
                "error_code": code,
                "confidence": confidence,
                "evidence_source": "test",
                "explanation": f"Test entry for {code}",
            }
            for code in error_codes
        ],
        raw_inputs={"test": True},
        taxonomy_version=taxonomy_version,
    )


def _make_cluster(
    *,
    primary_error_code: str = "GROUND.MISSING_REF",
    secondary_error_codes: List[str] | None = None,
    record_count: int = 5,
    weighted_severity_score: float = 10.0,
    avg_confidence: float = 0.85,
    remediation_targets: List[str] | None = None,
    pass_types: Dict[str, int] | None = None,
    record_ids: List[str] | None = None,
) -> ErrorCluster:
    dominant_family = (
        primary_error_code.split(".")[0] if "." in primary_error_code else primary_error_code
    )
    return ErrorCluster(
        cluster_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        taxonomy_version="1.0.0",
        cluster_signature={
            "primary_error_code": primary_error_code,
            "secondary_error_codes": secondary_error_codes or [],
            "dominant_family": dominant_family,
        },
        metrics={
            "record_count": record_count,
            "weighted_severity_score": weighted_severity_score,
            "avg_confidence": avg_confidence,
        },
        context_distribution={
            "artifact_types": {"working_paper": record_count},
            "pass_types": pass_types or {"extraction": record_count},
            "source_systems": {"evaluation": record_count},
        },
        remediation_targets=remediation_targets if remediation_targets is not None else ["grounding"],
        representative_examples=[],
        record_ids=record_ids,
    )


def _make_validated(
    *,
    validation_status: str = "valid",
    cluster_id: str | None = None,
) -> ValidatedCluster:
    return ValidatedCluster(
        cluster_id=cluster_id or str(uuid.uuid4()),
        cluster_signature="GROUND.MISSING_REF",
        record_count=5,
        error_codes=["GROUND.MISSING_REF"],
        pass_types=["extraction"],
        remediation_targets=["grounding"],
        validation_status=validation_status,
        validation_reasons=["size_ok: record_count=5 >= min=3"],
        stability_score=1.0,
        cohesion_score=1.0,
        actionability_score=1.0,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture
def catalog() -> ErrorTaxonomyCatalog:
    return ErrorTaxonomyCatalog.load_catalog()


@pytest.fixture
def validator() -> ClusterValidator:
    return ClusterValidator()


# ===========================================================================
# 1. Schema file presence
# ===========================================================================


class TestSchemaFileExists:
    def test_validated_cluster_schema_exists(self) -> None:
        schema_path = _ROOT / "contracts" / "schemas" / "validated_cluster.schema.json"
        assert schema_path.exists(), f"Schema not found at {schema_path}"

    def test_validated_cluster_schema_is_valid_json(self) -> None:
        schema_path = _ROOT / "contracts" / "schemas" / "validated_cluster.schema.json"
        with open(schema_path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["type"] == "object"
        assert "cluster_id" in data["properties"]
        assert "validation_status" in data["properties"]
        assert data["additionalProperties"] is False


# ===========================================================================
# 2. ValidatedCluster serialisation
# ===========================================================================


class TestValidatedClusterSerialisation:
    def test_round_trip(self) -> None:
        vc = _make_validated()
        d = vc.to_dict()
        restored = ValidatedCluster.from_dict(d)
        assert restored.cluster_id == vc.cluster_id
        assert restored.validation_status == vc.validation_status
        assert restored.cohesion_score == vc.cohesion_score

    def test_to_dict_has_all_required_fields(self) -> None:
        vc = _make_validated()
        d = vc.to_dict()
        required = {
            "cluster_id", "cluster_signature", "record_count", "error_codes",
            "pass_types", "remediation_targets", "validation_status",
            "validation_reasons", "stability_score", "cohesion_score",
            "actionability_score", "created_at",
        }
        assert required.issubset(d.keys())

    def test_schema_validation_passes_for_valid_object(self) -> None:
        vc = _make_validated(validation_status="valid")
        errors = vc.validate_against_schema()
        assert errors == [], f"Schema errors: {errors}"

    def test_schema_validation_passes_for_invalid_object(self) -> None:
        vc = _make_validated(validation_status="invalid")
        errors = vc.validate_against_schema()
        assert errors == [], f"Schema errors: {errors}"


# ===========================================================================
# 3. Rule A — SIZE CHECK
# ===========================================================================


class TestSizeCheck:
    def test_cluster_too_small_is_invalid(self, validator: ClusterValidator) -> None:
        cluster = _make_cluster(record_count=2)
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 2
        for r in records:
            r.classification_id = str(uuid.uuid4())
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert result.validation_status == "invalid"
        assert any("too_small" in r for r in result.validation_reasons)

    def test_cluster_at_minimum_size_is_valid_for_size_check(
        self, validator: ClusterValidator
    ) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 3
        cluster = _make_cluster(record_count=3)
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert any("size_ok" in r for r in result.validation_reasons)

    def test_cluster_exactly_one_record_is_invalid(
        self, validator: ClusterValidator
    ) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])]
        cluster = _make_cluster(record_count=1)
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert result.validation_status == "invalid"
        assert any("too_small" in r for r in result.validation_reasons)


# ===========================================================================
# 4. Rule B — COHESION CHECK
# ===========================================================================


class TestCohesionCheck:
    def test_low_cohesion_is_invalid(self, validator: ClusterValidator) -> None:
        # Mix of many different codes → dominant code frequency < 0.6
        records = (
            [_make_record(error_codes=["GROUND.MISSING_REF"])] * 2
            + [_make_record(error_codes=["REASON.UNSOUND_INFERENCE"])] * 2
            + [_make_record(error_codes=["EXTRACT.MISSED_DECISION"])] * 2
        )
        cluster = _make_cluster(
            primary_error_code="GROUND.MISSING_REF",
            record_count=6,
        )
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert result.validation_status == "invalid"
        assert any("low_cohesion" in r for r in result.validation_reasons)

    def test_high_cohesion_cluster_passes(self, validator: ClusterValidator) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 4 + [
            _make_record(error_codes=["REASON.UNSOUND_INFERENCE"])
        ]
        cluster = _make_cluster(
            primary_error_code="GROUND.MISSING_REF",
            record_count=5,
        )
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert any("cohesion_ok" in r for r in result.validation_reasons)
        # cohesion = 4/5 = 0.8 ≥ 0.6
        assert result.cohesion_score >= 0.6


# ===========================================================================
# 5. Rule C — PASS CONSISTENCY
# ===========================================================================


class TestPassConsistency:
    def test_too_many_pass_types_flagged(self, validator: ClusterValidator) -> None:
        pass_types_list = ["extraction", "grounding", "reasoning", "validation"]
        records = [
            _make_record(error_codes=["GROUND.MISSING_REF"], pass_type=pt)
            for pt in pass_types_list
        ] + [_make_record(error_codes=["GROUND.MISSING_REF"], pass_type="extraction")]
        cluster = _make_cluster(
            primary_error_code="GROUND.MISSING_REF",
            record_count=len(records),
        )
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        # too_broad is a flag, not an invalidating check by itself
        assert any("too_broad" in r for r in result.validation_reasons)

    def test_three_pass_types_passes(self, validator: ClusterValidator) -> None:
        pass_types_list = ["extraction", "grounding", "reasoning"]
        records = [
            _make_record(error_codes=["GROUND.MISSING_REF"], pass_type=pt)
            for pt in pass_types_list
        ] + [_make_record(error_codes=["GROUND.MISSING_REF"])] * 2
        cluster = _make_cluster(
            primary_error_code="GROUND.MISSING_REF",
            record_count=len(records),
        )
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert any("pass_consistency_ok" in r for r in result.validation_reasons)


# ===========================================================================
# 6. Rule D — STABILITY CHECK
# ===========================================================================


class TestStabilityCheck:
    def test_mismatched_signature_is_invalid(
        self, validator: ClusterValidator
    ) -> None:
        # Records all have REASON.UNSOUND_INFERENCE but cluster says GROUND.MISSING_REF
        records = [
            _make_record(error_codes=["REASON.UNSOUND_INFERENCE"])
        ] * 5
        cluster = _make_cluster(
            primary_error_code="GROUND.MISSING_REF",
            record_count=5,
        )
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert result.validation_status == "invalid"
        assert any("unstable_signature" in r for r in result.validation_reasons)

    def test_matching_signature_passes(self, validator: ClusterValidator) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
        cluster = _make_cluster(
            primary_error_code="GROUND.MISSING_REF",
            record_count=5,
        )
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert any("signature_stable" in r for r in result.validation_reasons)


# ===========================================================================
# 7. Rule E — ACTIONABILITY CHECK
# ===========================================================================


class TestActionabilityCheck:
    def test_too_many_remediation_targets_is_invalid(
        self, validator: ClusterValidator
    ) -> None:
        cluster = _make_cluster(
            remediation_targets=["grounding", "prompt", "retrieval"],
            record_count=5,
        )
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert result.validation_status == "invalid"
        assert any("unclear_remediation" in r for r in result.validation_reasons)

    def test_one_remediation_target_passes(
        self, validator: ClusterValidator
    ) -> None:
        cluster = _make_cluster(
            remediation_targets=["grounding"],
            record_count=5,
        )
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert any("actionability_ok" in r for r in result.validation_reasons)

    def test_two_remediation_targets_passes(
        self, validator: ClusterValidator
    ) -> None:
        cluster = _make_cluster(
            remediation_targets=["grounding", "prompt"],
            record_count=5,
        )
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert any("actionability_ok" in r for r in result.validation_reasons)


# ===========================================================================
# 8. Rule F — CONFIDENCE CHECK
# ===========================================================================


class TestConfidenceCheck:
    def test_low_confidence_is_invalid(self, validator: ClusterValidator) -> None:
        records = [
            _make_record(error_codes=["GROUND.MISSING_REF"], confidence=0.3)
        ] * 5
        cluster = _make_cluster(record_count=5)
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert result.validation_status == "invalid"
        assert any("low_confidence" in r for r in result.validation_reasons)

    def test_adequate_confidence_passes(self, validator: ClusterValidator) -> None:
        records = [
            _make_record(error_codes=["GROUND.MISSING_REF"], confidence=0.75)
        ] * 5
        cluster = _make_cluster(record_count=5)
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert any("confidence_ok" in r for r in result.validation_reasons)

    def test_exactly_min_confidence_passes(
        self, validator: ClusterValidator
    ) -> None:
        records = [
            _make_record(error_codes=["GROUND.MISSING_REF"], confidence=0.6)
        ] * 5
        cluster = _make_cluster(record_count=5)
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert any("confidence_ok" in r for r in result.validation_reasons)


# ===========================================================================
# 9. Scoring correctness
# ===========================================================================


class TestScoring:
    def test_cohesion_score_one_when_single_code(
        self, validator: ClusterValidator
    ) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
        cluster = _make_cluster(
            primary_error_code="GROUND.MISSING_REF",
            record_count=5,
        )
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert result.cohesion_score == 1.0

    def test_cohesion_score_partial_when_mixed(
        self, validator: ClusterValidator
    ) -> None:
        records = (
            [_make_record(error_codes=["GROUND.MISSING_REF"])] * 4
            + [_make_record(error_codes=["REASON.UNSOUND_INFERENCE"])]
        )
        cluster = _make_cluster(
            primary_error_code="GROUND.MISSING_REF",
            record_count=5,
        )
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert 0.7 < result.cohesion_score < 1.0

    def test_actionability_score_one_when_single_target(
        self, validator: ClusterValidator
    ) -> None:
        cluster = _make_cluster(remediation_targets=["grounding"], record_count=5)
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert result.actionability_score == 1.0

    def test_actionability_score_half_when_two_targets(
        self, validator: ClusterValidator
    ) -> None:
        cluster = _make_cluster(
            remediation_targets=["grounding", "prompt"], record_count=5
        )
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert result.actionability_score == pytest.approx(0.5, rel=1e-3)

    def test_stability_score_one_when_signature_matches(
        self, validator: ClusterValidator
    ) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
        cluster = _make_cluster(
            primary_error_code="GROUND.MISSING_REF",
            record_count=5,
        )
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert result.stability_score == pytest.approx(1.0, rel=1e-3)

    def test_stability_score_zero_when_signature_mismatches(
        self, validator: ClusterValidator
    ) -> None:
        records = [_make_record(error_codes=["REASON.UNSOUND_INFERENCE"])] * 5
        cluster = _make_cluster(
            primary_error_code="GROUND.MISSING_REF",
            record_count=5,
        )
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert result.stability_score == pytest.approx(0.0, abs=1e-3)

    def test_scores_in_range_0_1(self, validator: ClusterValidator) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
        cluster = _make_cluster(record_count=5)
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert 0.0 <= result.cohesion_score <= 1.0
        assert 0.0 <= result.actionability_score <= 1.0
        assert 0.0 <= result.stability_score <= 1.0


# ===========================================================================
# 10. Edge cases
# ===========================================================================


class TestEdgeCases:
    def test_empty_records_list(self, validator: ClusterValidator) -> None:
        cluster = _make_cluster(record_count=5)
        result = validator.validate_cluster(cluster, [])
        # With no live records, signature recomputation returns "" → mismatch
        assert result.validation_status == "invalid"

    def test_cluster_with_zero_remediation_targets(
        self, validator: ClusterValidator
    ) -> None:
        cluster = _make_cluster(
            remediation_targets=[],
            record_count=5,
        )
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert any("actionability_ok" in r for r in result.validation_reasons)
        assert result.actionability_score == 1.0

    def test_multiple_failures_listed_in_reasons(
        self, validator: ClusterValidator
    ) -> None:
        # Trigger size + confidence failures simultaneously
        records = [
            _make_record(error_codes=["GROUND.MISSING_REF"], confidence=0.2)
        ] * 2
        cluster = _make_cluster(record_count=2)
        cluster.record_ids = [r.classification_id for r in records]

        result = validator.validate_cluster(cluster, records)
        assert result.validation_status == "invalid"
        reason_tags = {r.split(":")[0] for r in result.validation_reasons}
        assert "too_small" in reason_tags
        assert "low_confidence" in reason_tags

    def test_determinism(self, validator: ClusterValidator) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
        cluster = _make_cluster(record_count=5)
        cluster.record_ids = [r.classification_id for r in records]

        r1 = validator.validate_cluster(cluster, records)
        r2 = validator.validate_cluster(cluster, records)
        assert r1.validation_status == r2.validation_status
        assert r1.cohesion_score == r2.cohesion_score
        assert r1.actionability_score == r2.actionability_score


# ===========================================================================
# 11. Pipeline integration: validate_clusters()
# ===========================================================================


class TestValidateClustersIntegration:
    def test_validate_clusters_empty(self, catalog: ErrorTaxonomyCatalog) -> None:
        result = validate_clusters([], [])
        assert result == []

    def test_validate_clusters_returns_one_per_cluster(
        self, catalog: ErrorTaxonomyCatalog
    ) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
        clusters = build_clusters_from_classifications(records, catalog)
        validated = validate_clusters(clusters, records)
        assert len(validated) == len(clusters)

    def test_validate_clusters_valid_only_filter(
        self, catalog: ErrorTaxonomyCatalog
    ) -> None:
        records = (
            [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
            + [_make_record(error_codes=["REASON.UNSOUND_INFERENCE"])] * 5
        )
        clusters = build_clusters_from_classifications(records, catalog)
        valid = validate_clusters(clusters, records, valid_only=True)
        assert all(v.validation_status == "valid" for v in valid)

    def test_validate_clusters_high_confidence_records_tend_to_pass(
        self, catalog: ErrorTaxonomyCatalog
    ) -> None:
        records = [
            _make_record(error_codes=["GROUND.MISSING_REF"], confidence=0.95)
        ] * 10
        clusters = build_clusters_from_classifications(records, catalog)
        validated = validate_clusters(clusters, records)
        # All records have identical error code and high confidence — expect valid
        assert any(v.validation_status == "valid" for v in validated)

    def test_pipeline_flow_build_validate_filter(
        self, catalog: ErrorTaxonomyCatalog
    ) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 8
        # Step 1: build
        clusters = build_clusters_from_classifications(records, catalog)
        # Step 2: validate
        validated = validate_clusters(clusters, records)
        # Step 3: filter valid only
        valid_only = [v for v in validated if v.validation_status == "valid"]
        assert isinstance(valid_only, list)
        for v in valid_only:
            assert v.validation_status == "valid"


# ===========================================================================
# 12. Validated cluster store
# ===========================================================================


class TestValidatedClusterStore:
    def test_save_and_load(self, tmp_path: Path) -> None:
        vc = _make_validated(validation_status="valid")
        path = save_validated_cluster(vc, tmp_path)
        assert path.exists()

        loaded = load_validated_clusters(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].cluster_id == vc.cluster_id
        assert loaded[0].validation_status == "valid"

    def test_load_empty_directory(self, tmp_path: Path) -> None:
        results = load_validated_clusters(tmp_path)
        assert results == []

    def test_load_nonexistent_directory(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist"
        results = load_validated_clusters(missing)
        assert results == []

    def test_save_duplicate_raises(self, tmp_path: Path) -> None:
        vc = _make_validated()
        save_validated_cluster(vc, tmp_path)
        with pytest.raises(FileExistsError):
            save_validated_cluster(vc, tmp_path)

    def test_save_multiple_and_load_all(self, tmp_path: Path) -> None:
        vc1 = _make_validated(validation_status="valid")
        vc2 = _make_validated(validation_status="invalid")
        save_validated_cluster(vc1, tmp_path)
        save_validated_cluster(vc2, tmp_path)

        loaded = load_validated_clusters(tmp_path)
        assert len(loaded) == 2
        statuses = {v.validation_status for v in loaded}
        assert statuses == {"valid", "invalid"}
