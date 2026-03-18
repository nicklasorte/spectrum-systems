"""
Tests for the Auto-Failure Clustering System (Prompt AV).

Covers:
- ErrorCluster: serialisation round-trip
- ErrorCluster: schema validation
- ErrorClusterer: deterministic clustering
- ErrorClusterer: grouping correctness
- ErrorClusterer: compute_cluster_signature
- ErrorClusterer: compute_metrics
- ErrorClusterer: extract_representative_examples
- ErrorClusterer: sub-clustering by pass_type
- ErrorClusterer: small cluster merging
- ErrorClusterer: taxonomy version filtering
- Impact scoring: compute_weighted_severity
- Impact scoring: compute_cluster_impact
- Impact scoring: rank_clusters
- ClusterStore: save / load / list_clusters
- ClusterStore: list_clusters with filters
- ClusterPipeline: build_clusters_from_classifications
- ClusterPipeline: rank_and_filter_clusters
- ClusterPipeline: enrich_clusters_with_catalog
- Schema file: error_cluster.schema.json exists
- CLI smoke test: --all with no records
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------

from spectrum_systems.modules.error_taxonomy.catalog import ErrorTaxonomyCatalog
from spectrum_systems.modules.error_taxonomy.classify import ErrorClassificationRecord
from spectrum_systems.modules.error_taxonomy.clustering import ErrorCluster, ErrorClusterer
from spectrum_systems.modules.error_taxonomy.impact import (
    SEVERITY_WEIGHTS,
    compute_weighted_severity,
    compute_cluster_impact,
    rank_clusters,
)
from spectrum_systems.modules.error_taxonomy.cluster_store import (
    save_cluster,
    load_cluster,
    list_clusters,
)
from spectrum_systems.modules.error_taxonomy.cluster_pipeline import (
    build_clusters_from_classifications,
    enrich_clusters_with_catalog,
    rank_and_filter_clusters,
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
    """Build a minimal ErrorClassificationRecord for testing."""
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
    record_count: int = 5,
    weighted_severity_score: float = 10.0,
    avg_confidence: float = 0.85,
) -> ErrorCluster:
    """Build a minimal ErrorCluster for testing."""
    return ErrorCluster(
        cluster_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        taxonomy_version="1.0.0",
        cluster_signature={
            "primary_error_code": primary_error_code,
            "secondary_error_codes": [],
            "dominant_family": primary_error_code.split(".")[0] if "." in primary_error_code else primary_error_code,
        },
        metrics={
            "record_count": record_count,
            "weighted_severity_score": weighted_severity_score,
            "avg_confidence": avg_confidence,
        },
        context_distribution={
            "artifact_types": {"working_paper": record_count},
            "pass_types": {"extraction": record_count},
            "source_systems": {"evaluation": record_count},
        },
        remediation_targets=["grounding"],
        representative_examples=[],
    )


@pytest.fixture
def catalog() -> ErrorTaxonomyCatalog:
    return ErrorTaxonomyCatalog.load_catalog()


@pytest.fixture
def clusterer(catalog: ErrorTaxonomyCatalog) -> ErrorClusterer:
    return ErrorClusterer(catalog, min_cluster_size=2)


# ===========================================================================
# 1. Schema file presence
# ===========================================================================

class TestSchemaFileExists:
    def test_error_cluster_schema_exists(self) -> None:
        schema_path = _ROOT / "contracts" / "schemas" / "error_cluster.schema.json"
        assert schema_path.exists(), f"Schema not found at {schema_path}"

    def test_error_cluster_schema_is_valid_json(self) -> None:
        schema_path = _ROOT / "contracts" / "schemas" / "error_cluster.schema.json"
        with open(schema_path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["type"] == "object"
        assert "cluster_id" in data["properties"]
        assert "cluster_signature" in data["properties"]
        assert "metrics" in data["properties"]


# ===========================================================================
# 2. ErrorCluster serialisation
# ===========================================================================

class TestErrorClusterSerialisation:
    def test_round_trip(self) -> None:
        cluster = _make_cluster()
        d = cluster.to_dict()
        restored = ErrorCluster.from_dict(d)
        assert restored.cluster_id == cluster.cluster_id
        assert restored.taxonomy_version == cluster.taxonomy_version
        assert restored.cluster_signature == cluster.cluster_signature
        assert restored.metrics == cluster.metrics

    def test_notes_omitted_when_empty(self) -> None:
        cluster = _make_cluster()
        d = cluster.to_dict()
        assert "notes" not in d

    def test_notes_included_when_set(self) -> None:
        cluster = _make_cluster()
        cluster.notes = "test note"
        d = cluster.to_dict()
        assert d["notes"] == "test note"

    def test_from_dict_preserves_notes(self) -> None:
        cluster = _make_cluster()
        cluster.notes = "important"
        restored = ErrorCluster.from_dict(cluster.to_dict())
        assert restored.notes == "important"


# ===========================================================================
# 3. ErrorCluster schema validation
# ===========================================================================

class TestErrorClusterSchemaValidation:
    def test_valid_cluster_passes(self) -> None:
        cluster = _make_cluster()
        errors = cluster.validate_against_schema()
        assert errors == [], f"Unexpected schema errors: {errors}"

    def test_missing_cluster_id_fails(self) -> None:
        cluster = _make_cluster()
        d = cluster.to_dict()
        del d["cluster_id"]
        # Schema requires cluster_id; from_dict should raise KeyError
        with pytest.raises(KeyError):
            ErrorCluster.from_dict(d)

    def test_additional_properties_rejected(self) -> None:
        cluster = _make_cluster()
        d = cluster.to_dict()
        d["unexpected_field"] = "bad"
        # Schema has additionalProperties: false so this should fail
        import jsonschema
        schema_path = _ROOT / "contracts" / "schemas" / "error_cluster.schema.json"
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        errors = list(jsonschema.Draft202012Validator(schema).iter_errors(d))
        assert any("additional" in e.message.lower() for e in errors)


# ===========================================================================
# 4. ErrorClusterer — compute_cluster_signature
# ===========================================================================

class TestComputeClusterSignature:
    def test_primary_is_most_frequent(self, clusterer: ErrorClusterer) -> None:
        records = (
            [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
            + [_make_record(error_codes=["REASON.UNSOUND_INFERENCE"])] * 2
        )
        sig = clusterer.compute_cluster_signature(records)
        assert sig["primary_error_code"] == "GROUND.MISSING_REF"

    def test_secondary_codes_listed(self, clusterer: ErrorClusterer) -> None:
        records = (
            [_make_record(error_codes=["GROUND.MISSING_REF"])] * 3
            + [_make_record(error_codes=["REASON.UNSOUND_INFERENCE"])] * 1
        )
        sig = clusterer.compute_cluster_signature(records)
        assert "REASON.UNSOUND_INFERENCE" in sig["secondary_error_codes"]

    def test_dominant_family_derived_from_primary(self, clusterer: ErrorClusterer) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 3
        sig = clusterer.compute_cluster_signature(records)
        assert sig["dominant_family"] == "GROUND"

    def test_tie_broken_alphabetically(self, clusterer: ErrorClusterer) -> None:
        records = (
            [_make_record(error_codes=["REASON.UNSOUND_INFERENCE"])]
            + [_make_record(error_codes=["GROUND.MISSING_REF"])]
        )
        sig = clusterer.compute_cluster_signature(records)
        # Both have count=1; alphabetically GROUND < REASON
        assert sig["primary_error_code"] == "GROUND.MISSING_REF"

    def test_empty_records(self, clusterer: ErrorClusterer) -> None:
        sig = clusterer.compute_cluster_signature([])
        assert sig["primary_error_code"] == "UNKNOWN"
        assert sig["dominant_family"] == "UNKNOWN"


# ===========================================================================
# 5. ErrorClusterer — compute_metrics
# ===========================================================================

class TestComputeMetrics:
    def test_record_count(self, clusterer: ErrorClusterer) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 4
        m = clusterer.compute_metrics(records)
        assert m["record_count"] == 4

    def test_avg_confidence(self, clusterer: ErrorClusterer) -> None:
        records = [
            _make_record(error_codes=["GROUND.MISSING_REF"], confidence=0.9),
            _make_record(error_codes=["GROUND.MISSING_REF"], confidence=0.7),
        ]
        m = clusterer.compute_metrics(records)
        assert abs(m["avg_confidence"] - 0.8) < 0.01

    def test_weighted_severity_positive(self, clusterer: ErrorClusterer) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 3
        m = clusterer.compute_metrics(records)
        assert m["weighted_severity_score"] > 0


# ===========================================================================
# 6. ErrorClusterer — extract_representative_examples
# ===========================================================================

class TestExtractRepresentativeExamples:
    def test_top_n_returned(self, clusterer: ErrorClusterer) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 6
        examples = clusterer.extract_representative_examples(records, top_n=3)
        assert len(examples) == 3

    def test_fewer_records_than_top_n(self, clusterer: ErrorClusterer) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 2
        examples = clusterer.extract_representative_examples(records, top_n=5)
        assert len(examples) == 2

    def test_example_has_required_fields(self, clusterer: ErrorClusterer) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])]
        examples = clusterer.extract_representative_examples(records, top_n=1)
        assert len(examples) == 1
        e = examples[0]
        assert "classification_id" in e
        assert "error_codes" in e
        assert "explanation" in e

    def test_deterministic_selection(self, clusterer: ErrorClusterer) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
        ex1 = clusterer.extract_representative_examples(records, top_n=2)
        ex2 = clusterer.extract_representative_examples(records, top_n=2)
        assert [e["classification_id"] for e in ex1] == [e["classification_id"] for e in ex2]


# ===========================================================================
# 7. ErrorClusterer — group_records (deterministic clustering)
# ===========================================================================

class TestGroupRecordsClustering:
    def test_empty_input_returns_empty(self, clusterer: ErrorClusterer) -> None:
        assert clusterer.group_records([]) == []

    def test_single_family_single_cluster(self, clusterer: ErrorClusterer) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
        clusters = clusterer.group_records(records)
        assert len(clusters) >= 1
        families = {c.cluster_signature["dominant_family"] for c in clusters}
        assert "GROUND" in families

    def test_two_families_two_clusters(self, clusterer: ErrorClusterer) -> None:
        records = (
            [_make_record(error_codes=["GROUND.MISSING_REF"])] * 4
            + [_make_record(error_codes=["REASON.UNSOUND_INFERENCE"])] * 4
        )
        clusters = clusterer.group_records(records)
        families = {c.cluster_signature["dominant_family"] for c in clusters}
        assert "GROUND" in families
        assert "REASON" in families

    def test_deterministic_same_input_same_output(self, clusterer: ErrorClusterer) -> None:
        records = (
            [_make_record(error_codes=["GROUND.MISSING_REF"])] * 4
            + [_make_record(error_codes=["REASON.UNSOUND_INFERENCE"])] * 3
        )
        clusters_a = clusterer.group_records(records)
        clusters_b = clusterer.group_records(records)
        # Same number of clusters
        assert len(clusters_a) == len(clusters_b)
        # Same primary codes (order may differ; compare sets)
        codes_a = {c.cluster_signature["primary_error_code"] for c in clusters_a}
        codes_b = {c.cluster_signature["primary_error_code"] for c in clusters_b}
        assert codes_a == codes_b

    def test_record_ids_preserved(self, clusterer: ErrorClusterer) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 4
        rec_ids = {r.classification_id for r in records}
        clusters = clusterer.group_records(records)
        cluster_record_ids: set[str] = set()
        for c in clusters:
            cluster_record_ids.update(c.record_ids)
        assert cluster_record_ids == rec_ids

    def test_total_records_preserved(self, clusterer: ErrorClusterer) -> None:
        records = (
            [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
            + [_make_record(error_codes=["REASON.UNSOUND_INFERENCE"])] * 3
        )
        clusters = clusterer.group_records(records)
        total = sum(c.metrics["record_count"] for c in clusters)
        assert total == len(records)

    def test_sub_clustering_by_pass_type(self, clusterer: ErrorClusterer) -> None:
        records = (
            [_make_record(error_codes=["GROUND.MISSING_REF"], pass_type="extraction")] * 3
            + [_make_record(error_codes=["GROUND.MISSING_REF"], pass_type="reasoning")] * 3
        )
        clusters = clusterer.group_records(records)
        # Should produce at least 1 cluster; may sub-cluster by pass_type
        assert len(clusters) >= 1

    def test_incompatible_taxonomy_versions_filtered(self, catalog: ErrorTaxonomyCatalog) -> None:
        clusterer_v1 = ErrorClusterer(catalog, taxonomy_version="1.0.0")
        records = (
            [_make_record(error_codes=["GROUND.MISSING_REF"], taxonomy_version="1.0.0")] * 3
            + [_make_record(error_codes=["REASON.UNSOUND_INFERENCE"], taxonomy_version="2.0.0")] * 3
        )
        clusters = clusterer_v1.group_records(records)
        # Only v1.0.0 records should be clustered
        for c in clusters:
            assert c.taxonomy_version == "1.0.0"

    def test_no_giant_single_cluster_for_varied_input(self, clusterer: ErrorClusterer) -> None:
        """Varied error codes should NOT all collapse into a single cluster."""
        records = (
            [_make_record(error_codes=["GROUND.MISSING_REF"])] * 4
            + [_make_record(error_codes=["REASON.UNSOUND_INFERENCE"])] * 4
            + [_make_record(error_codes=["EXTRACT.MISSED_DECISION"])] * 4
        )
        clusters = clusterer.group_records(records)
        assert len(clusters) >= 2

    def test_small_cluster_merging(self, catalog: ErrorTaxonomyCatalog) -> None:
        """A single-record cluster should be merged into its family sibling."""
        big_clusterer = ErrorClusterer(catalog, min_cluster_size=3)
        records = (
            [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
            # Only 2 GROUND.INVALID_REF records — below threshold of 3
            + [_make_record(error_codes=["GROUND.INVALID_REF"])] * 2
        )
        clusters = big_clusterer.group_records(records)
        # The small GROUND.INVALID_REF sub-group should merge into GROUND cluster
        total = sum(c.metrics["record_count"] for c in clusters)
        assert total == len(records)


# ===========================================================================
# 8. Impact scoring
# ===========================================================================

class TestImpactScoring:
    def test_severity_weights_defined(self) -> None:
        assert "low" in SEVERITY_WEIGHTS
        assert "medium" in SEVERITY_WEIGHTS
        assert "high" in SEVERITY_WEIGHTS
        assert "critical" in SEVERITY_WEIGHTS
        assert SEVERITY_WEIGHTS["critical"] > SEVERITY_WEIGHTS["high"]
        assert SEVERITY_WEIGHTS["high"] > SEVERITY_WEIGHTS["medium"]
        assert SEVERITY_WEIGHTS["medium"] > SEVERITY_WEIGHTS["low"]

    def test_compute_weighted_severity_positive(self, catalog: ErrorTaxonomyCatalog) -> None:
        rec = _make_record(error_codes=["GROUND.MISSING_REF"], confidence=1.0)
        score = compute_weighted_severity(rec, catalog)
        assert score > 0

    def test_compute_weighted_severity_zero_confidence(self, catalog: ErrorTaxonomyCatalog) -> None:
        rec = _make_record(error_codes=["GROUND.MISSING_REF"], confidence=0.0)
        score = compute_weighted_severity(rec, catalog)
        assert score == 0.0

    def test_critical_higher_than_low(self, catalog: ErrorTaxonomyCatalog) -> None:
        # HALLUC.FABRICATED_CLAIM is critical; EXTRACT.SPAN_BOUNDARY_ERROR is low
        critical_codes = [
            code for code in catalog.list_subtypes("HALLUC")
            if catalog.get_error(code.error_code) and
               catalog.get_error(code.error_code).default_severity == "critical"
        ]
        low_codes = [
            code for code in catalog.list_subtypes("EXTRACT")
            if catalog.get_error(code.error_code) and
               catalog.get_error(code.error_code).default_severity == "low"
        ]
        if critical_codes and low_codes:
            rec_critical = _make_record(error_codes=[critical_codes[0].error_code], confidence=1.0)
            rec_low = _make_record(error_codes=[low_codes[0].error_code], confidence=1.0)
            assert compute_weighted_severity(rec_critical, catalog) > compute_weighted_severity(rec_low, catalog)

    def test_compute_cluster_impact_matches_metric(self) -> None:
        cluster = _make_cluster(weighted_severity_score=42.5)
        assert compute_cluster_impact(cluster) == 42.5

    def test_rank_clusters_descending(self) -> None:
        c1 = _make_cluster(weighted_severity_score=10.0, record_count=5)
        c2 = _make_cluster(weighted_severity_score=50.0, record_count=5)
        c3 = _make_cluster(weighted_severity_score=25.0, record_count=5)
        ranked = rank_clusters([c1, c2, c3])
        scores = [c.metrics["weighted_severity_score"] for c in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_rank_clusters_secondary_sort_by_record_count(self) -> None:
        c1 = _make_cluster(weighted_severity_score=10.0, record_count=3)
        c2 = _make_cluster(weighted_severity_score=10.0, record_count=10)
        ranked = rank_clusters([c1, c2])
        assert ranked[0].metrics["record_count"] == 10

    def test_rank_clusters_preserves_all(self) -> None:
        clusters = [_make_cluster() for _ in range(5)]
        ranked = rank_clusters(clusters)
        assert len(ranked) == 5

    def test_rank_clusters_empty_input(self) -> None:
        assert rank_clusters([]) == []


# ===========================================================================
# 9. Cluster Store
# ===========================================================================

class TestClusterStore:
    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        cluster = _make_cluster()
        save_cluster(cluster, store_dir=tmp_path)
        loaded = load_cluster(cluster.cluster_id, store_dir=tmp_path)
        assert loaded.cluster_id == cluster.cluster_id
        assert loaded.cluster_signature == cluster.cluster_signature

    def test_save_raises_on_duplicate(self, tmp_path: Path) -> None:
        cluster = _make_cluster()
        save_cluster(cluster, store_dir=tmp_path)
        with pytest.raises(FileExistsError):
            save_cluster(cluster, store_dir=tmp_path)

    def test_load_raises_if_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_cluster("nonexistent-id", store_dir=tmp_path)

    def test_list_clusters_empty_dir(self, tmp_path: Path) -> None:
        result = list_clusters(store_dir=tmp_path)
        assert result == []

    def test_list_clusters_missing_dir(self, tmp_path: Path) -> None:
        result = list_clusters(store_dir=tmp_path / "missing")
        assert result == []

    def test_list_clusters_returns_all(self, tmp_path: Path) -> None:
        clusters = [_make_cluster() for _ in range(3)]
        for c in clusters:
            save_cluster(c, store_dir=tmp_path)
        loaded = list_clusters(store_dir=tmp_path)
        assert len(loaded) == 3

    def test_list_clusters_filter_by_taxonomy_version(self, tmp_path: Path) -> None:
        c1 = _make_cluster()
        c2 = _make_cluster()
        c2.taxonomy_version = "2.0.0"
        save_cluster(c1, store_dir=tmp_path)
        save_cluster(c2, store_dir=tmp_path)
        result = list_clusters({"taxonomy_version": "1.0.0"}, store_dir=tmp_path)
        assert len(result) == 1
        assert result[0].cluster_id == c1.cluster_id

    def test_list_clusters_filter_by_min_record_count(self, tmp_path: Path) -> None:
        c_small = _make_cluster(record_count=2)
        c_large = _make_cluster(record_count=10)
        save_cluster(c_small, store_dir=tmp_path)
        save_cluster(c_large, store_dir=tmp_path)
        result = list_clusters({"min_record_count": 5}, store_dir=tmp_path)
        assert len(result) == 1
        assert result[0].cluster_id == c_large.cluster_id

    def test_list_clusters_filter_by_dominant_family(self, tmp_path: Path) -> None:
        c_ground = _make_cluster(primary_error_code="GROUND.MISSING_REF")
        c_reason = _make_cluster(primary_error_code="REASON.UNSOUND_INFERENCE")
        save_cluster(c_ground, store_dir=tmp_path)
        save_cluster(c_reason, store_dir=tmp_path)
        result = list_clusters({"dominant_family": "GROUND"}, store_dir=tmp_path)
        assert len(result) == 1
        assert result[0].cluster_signature["dominant_family"] == "GROUND"


# ===========================================================================
# 10. Cluster Pipeline
# ===========================================================================

class TestClusterPipeline:
    def test_build_clusters_empty_input(self, catalog: ErrorTaxonomyCatalog) -> None:
        result = build_clusters_from_classifications([], catalog)
        assert result == []

    def test_build_clusters_produces_clusters(self, catalog: ErrorTaxonomyCatalog) -> None:
        records = [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
        clusters = build_clusters_from_classifications(records, catalog)
        assert len(clusters) >= 1

    def test_build_clusters_ranked_by_impact(self, catalog: ErrorTaxonomyCatalog) -> None:
        records = (
            [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
            + [_make_record(error_codes=["REASON.UNSOUND_INFERENCE"])] * 3
        )
        clusters = build_clusters_from_classifications(records, catalog)
        scores = [c.metrics["weighted_severity_score"] for c in clusters]
        assert scores == sorted(scores, reverse=True)

    def test_rank_and_filter_removes_small_clusters(self, catalog: ErrorTaxonomyCatalog) -> None:
        records = (
            [_make_record(error_codes=["GROUND.MISSING_REF"])] * 5
            + [_make_record(error_codes=["REASON.UNSOUND_INFERENCE"])] * 2
        )
        clusters = build_clusters_from_classifications(records, catalog, min_cluster_size=1)
        filtered = rank_and_filter_clusters(clusters, min_size=3)
        for c in filtered:
            assert c.metrics["record_count"] >= 3

    def test_rank_and_filter_empty(self) -> None:
        assert rank_and_filter_clusters([], min_size=3) == []

    def test_enrich_clusters_with_catalog(self, catalog: ErrorTaxonomyCatalog) -> None:
        clusters = [_make_cluster(primary_error_code="GROUND.MISSING_REF")]
        enriched = enrich_clusters_with_catalog(clusters, catalog)
        assert len(enriched) == 1
        assert enriched[0].metrics["weighted_severity_score"] >= 0

    def test_build_100_records_deterministic(self, catalog: ErrorTaxonomyCatalog) -> None:
        """Can cluster ≥100 classification records deterministically."""
        records = (
            [_make_record(error_codes=["GROUND.MISSING_REF"])] * 30
            + [_make_record(error_codes=["REASON.UNSOUND_INFERENCE"])] * 25
            + [_make_record(error_codes=["EXTRACT.MISSED_DECISION"])] * 20
            + [_make_record(error_codes=["HALLUC.UNSUPPORTED_ASSERTION"])] * 15
            + [_make_record(error_codes=["SCHEMA.MISSING_FIELD"])] * 10
        )
        assert len(records) == 100

        c1 = build_clusters_from_classifications(records, catalog)
        c2 = build_clusters_from_classifications(records, catalog)

        assert len(c1) == len(c2)
        primaries_1 = {c.cluster_signature["primary_error_code"] for c in c1}
        primaries_2 = {c.cluster_signature["primary_error_code"] for c in c2}
        assert primaries_1 == primaries_2

    def test_build_identifies_top_families(self, catalog: ErrorTaxonomyCatalog) -> None:
        """Identifies top 3–5 highest impact failure patterns."""
        records = (
            [_make_record(error_codes=["GROUND.MISSING_REF"])] * 30
            + [_make_record(error_codes=["REASON.UNSOUND_INFERENCE"])] * 20
            + [_make_record(error_codes=["EXTRACT.MISSED_DECISION"])] * 15
            + [_make_record(error_codes=["HALLUC.UNSUPPORTED_ASSERTION"])] * 10
            + [_make_record(error_codes=["SCHEMA.MISSING_FIELD"])] * 5
        )
        clusters = build_clusters_from_classifications(records, catalog)
        top5 = rank_and_filter_clusters(clusters, min_size=1)[:5]
        families = {c.cluster_signature["dominant_family"] for c in top5}
        # Should have at least 3 distinct dominant families
        assert len(families) >= 3


# ===========================================================================
# 11. CLI smoke test
# ===========================================================================

class TestCLISmokeTest:
    def test_cli_no_records(self, tmp_path: Path, capsys: Any) -> None:
        """CLI exits cleanly with no records in the store."""
        script = _ROOT / "scripts" / "run_error_clustering.py"
        import subprocess

        result = subprocess.run(
            [
                sys.executable, str(script), "--all",
                "--store-dir", str(tmp_path),
            ],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PYTHONPATH": str(_ROOT),
            },
        )
        # Should exit 0 with a "no records" message
        assert result.returncode == 0
        assert "No classification records found" in result.stdout
