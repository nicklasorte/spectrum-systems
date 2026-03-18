"""
Tests for the AW1 Remediation Mapping Engine (Prompt AW1).

Covers:
- Schema file: remediation_plan.schema.json exists
- RemediationPlan: serialisation round-trip
- RemediationPlan: schema validation
- RemediationMapper: invalid cluster rejection
- RemediationMapper: valid cluster mapping (GROUND.*)
- RemediationMapper: valid cluster mapping (EXTRACT.MISSED_DECISION)
- RemediationMapper: valid cluster mapping (EXTRACT.MISSED_ACTION_ITEM)
- RemediationMapper: valid cluster mapping (SCHEMA.INVALID_OUTPUT)
- RemediationMapper: valid cluster mapping (INPUT.BAD_TRANSCRIPT_QUALITY)
- RemediationMapper: valid cluster mapping (RETRIEVE.*)
- RemediationMapper: valid cluster mapping (HUMAN.NEEDS_SUPPORT + GROUND.WEAK_SUPPORT)
- RemediationMapper: ambiguous cluster handling (mixed / no dominant signal)
- RemediationMapper: max 2 proposed actions per cluster
- TargetRegistry: validate_target_component accepts known names
- TargetRegistry: validate_target_component rejects unknown names
- Confidence scoring: compute_mapping_confidence
- Risk scoring: compute_risk_level
- Pipeline: build_remediation_plans_from_validated_clusters
- Pipeline: filter_mapped_plans
- Pipeline: summarize_remediation_targets
- Store: save and load round-trip
- Store: list_remediation_plans with filters
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

from spectrum_systems.modules.error_taxonomy.cluster_validation import ValidatedCluster
from spectrum_systems.modules.improvement.remediation_mapping import (
    RemediationMapper,
    RemediationPlan,
    compute_mapping_confidence,
    compute_risk_level,
)
from spectrum_systems.modules.improvement.remediation_pipeline import (
    build_remediation_plans_from_validated_clusters,
    filter_mapped_plans,
    summarize_remediation_targets,
)
from spectrum_systems.modules.improvement.remediation_store import (
    list_remediation_plans,
    load_remediation_plan,
    save_remediation_plan,
)
from spectrum_systems.modules.improvement.target_registry import (
    KNOWN_TARGET_COMPONENTS,
    validate_target_component,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parents[1]


def _make_validated(
    *,
    validation_status: str = "valid",
    cluster_id: str | None = None,
    cluster_signature: str = "GROUND.MISSING_REF",
    error_codes: List[str] | None = None,
    cohesion_score: float = 0.85,
    actionability_score: float = 0.85,
    stability_score: float = 0.9,
    record_count: int = 5,
    pass_types: List[str] | None = None,
    remediation_targets: List[str] | None = None,
) -> ValidatedCluster:
    return ValidatedCluster(
        cluster_id=cluster_id or str(uuid.uuid4()),
        cluster_signature=cluster_signature,
        record_count=record_count,
        error_codes=error_codes if error_codes is not None else [cluster_signature],
        pass_types=pass_types if pass_types is not None else ["extraction"],
        remediation_targets=remediation_targets if remediation_targets is not None else ["grounding"],
        validation_status=validation_status,
        validation_reasons=["size_ok: record_count=5 >= min=3"],
        stability_score=stability_score,
        cohesion_score=cohesion_score,
        actionability_score=actionability_score,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _make_plan(
    *,
    mapping_status: str = "mapped",
    cluster_id: str | None = None,
    cluster_signature: str = "GROUND.MISSING_REF",
) -> RemediationPlan:
    return RemediationPlan(
        remediation_id=str(uuid.uuid4()),
        cluster_id=cluster_id or str(uuid.uuid4()),
        cluster_signature=cluster_signature,
        taxonomy_version="1.0.0",
        created_at=datetime.now(timezone.utc).isoformat(),
        mapping_status=mapping_status,
        mapping_reasons=["test_reason"],
        dominant_error_codes=[cluster_signature],
        remediation_targets=["grounding_verifier"],
        proposed_actions=[
            {
                "action_id": str(uuid.uuid4()),
                "action_type": "grounding_rule_change",
                "target_component": "grounding_verifier",
                "rationale": "Test rationale.",
                "expected_benefit": "Test benefit.",
                "risk_level": "medium",
                "confidence_score": 0.8,
            }
        ],
        primary_proposal_index=0,
        evidence_summary={
            "record_count": 5,
            "avg_cluster_confidence": 0.85,
            "weighted_severity_score": 10.0,
            "pass_types": ["extraction"],
        },
    )


@pytest.fixture
def mapper() -> RemediationMapper:
    return RemediationMapper(taxonomy_version="1.0.0")


# ===========================================================================
# 1. Schema file presence
# ===========================================================================


class TestSchemaFileExists:
    def test_remediation_plan_schema_exists(self) -> None:
        schema_path = _ROOT / "contracts" / "schemas" / "remediation_plan.schema.json"
        assert schema_path.exists(), f"Schema file not found at {schema_path}"

    def test_remediation_plan_schema_is_valid_json(self) -> None:
        schema_path = _ROOT / "contracts" / "schemas" / "remediation_plan.schema.json"
        with open(schema_path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["title"] == "Remediation Plan"
        assert data.get("additionalProperties") is False


# ===========================================================================
# 2. RemediationPlan serialisation
# ===========================================================================


class TestRemediationPlanSerialisation:
    def test_to_dict_contains_all_required_fields(self) -> None:
        plan = _make_plan()
        d = plan.to_dict()
        required = [
            "remediation_id",
            "cluster_id",
            "cluster_signature",
            "taxonomy_version",
            "created_at",
            "mapping_status",
            "mapping_reasons",
            "dominant_error_codes",
            "remediation_targets",
            "proposed_actions",
            "primary_proposal_index",
            "evidence_summary",
        ]
        for field in required:
            assert field in d, f"Missing field: {field}"

    def test_round_trip(self) -> None:
        original = _make_plan()
        restored = RemediationPlan.from_dict(original.to_dict())
        assert restored.remediation_id == original.remediation_id
        assert restored.cluster_id == original.cluster_id
        assert restored.mapping_status == original.mapping_status
        assert restored.proposed_actions == original.proposed_actions

    def test_schema_validation_passes_for_valid_plan(self) -> None:
        plan = _make_plan()
        errors = plan.validate_against_schema()
        assert errors == [], f"Schema validation errors: {errors}"

    def test_schema_validation_rejects_missing_field(self) -> None:
        plan = _make_plan()
        d = plan.to_dict()
        del d["remediation_id"]
        errors: List[str] = []
        import jsonschema
        schema_path = _ROOT / "contracts" / "schemas" / "remediation_plan.schema.json"
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        for err in jsonschema.Draft202012Validator(schema).iter_errors(d):
            errors.append(err.message)
        assert errors, "Expected schema validation errors for missing field"


# ===========================================================================
# 3. RemediationMapper: rejected plans
# ===========================================================================


class TestRemediationMapperRejection:
    def test_invalid_cluster_is_rejected(self, mapper: RemediationMapper) -> None:
        vc = _make_validated(validation_status="invalid")
        plan = mapper.map_validated_cluster(vc, [])
        assert plan.mapping_status == "rejected"

    def test_rejected_plan_has_no_action(self, mapper: RemediationMapper) -> None:
        vc = _make_validated(validation_status="invalid")
        plan = mapper.map_validated_cluster(vc, [])
        assert len(plan.proposed_actions) == 1
        assert plan.proposed_actions[0]["action_type"] == "no_action"

    def test_rejected_plan_reasons_mention_validation_status(
        self, mapper: RemediationMapper
    ) -> None:
        vc = _make_validated(validation_status="invalid")
        plan = mapper.map_validated_cluster(vc, [])
        assert any("invalid" in r for r in plan.mapping_reasons)


# ===========================================================================
# 4. RemediationMapper: GROUND.* mapping (Rule A)
# ===========================================================================


class TestRemediationMapperGrounding:
    def test_ground_dominant_maps_to_grounding_rule_change(
        self, mapper: RemediationMapper
    ) -> None:
        vc = _make_validated(
            cluster_signature="GROUND.MISSING_REF",
            error_codes=["GROUND.MISSING_REF"],
        )
        plan = mapper.map_validated_cluster(vc, [])
        assert plan.mapping_status == "mapped"
        assert plan.proposed_actions[0]["action_type"] == "grounding_rule_change"

    def test_ground_dominant_targets_grounding_verifier(
        self, mapper: RemediationMapper
    ) -> None:
        vc = _make_validated(
            cluster_signature="GROUND.MISSING_REF",
            error_codes=["GROUND.MISSING_REF"],
        )
        plan = mapper.map_validated_cluster(vc, [])
        assert plan.proposed_actions[0]["target_component"] == "grounding_verifier"

    def test_ground_weak_support_with_human_targets_synthesis_grounding(
        self, mapper: RemediationMapper
    ) -> None:
        vc = _make_validated(
            cluster_signature="GROUND.WEAK_SUPPORT",
            error_codes=["GROUND.WEAK_SUPPORT", "HUMAN.NEEDS_SUPPORT"],
        )
        plan = mapper.map_validated_cluster(vc, [])
        assert plan.mapping_status == "mapped"
        assert plan.proposed_actions[0]["target_component"] == "synthesis_grounding_rules"


# ===========================================================================
# 5. RemediationMapper: EXTRACT.* mapping (Rule B)
# ===========================================================================


class TestRemediationMapperExtract:
    def test_missed_decision_maps_to_decision_extraction_prompt(
        self, mapper: RemediationMapper
    ) -> None:
        vc = _make_validated(
            cluster_signature="EXTRACT.MISSED_DECISION",
            error_codes=["EXTRACT.MISSED_DECISION"],
            cohesion_score=0.9,
        )
        plan = mapper.map_validated_cluster(vc, [])
        assert plan.mapping_status == "mapped"
        assert plan.proposed_actions[0]["action_type"] == "prompt_change"
        assert plan.proposed_actions[0]["target_component"] == "decision_extraction_prompt"

    def test_missed_action_item_maps_to_action_item_extraction_prompt(
        self, mapper: RemediationMapper
    ) -> None:
        vc = _make_validated(
            cluster_signature="EXTRACT.MISSED_ACTION_ITEM",
            error_codes=["EXTRACT.MISSED_ACTION_ITEM"],
            cohesion_score=0.9,
        )
        plan = mapper.map_validated_cluster(vc, [])
        assert plan.mapping_status == "mapped"
        assert plan.proposed_actions[0]["target_component"] == "action_item_extraction_prompt"


# ===========================================================================
# 6. RemediationMapper: SCHEMA.INVALID_OUTPUT mapping (Rule C)
# ===========================================================================


class TestRemediationMapperSchema:
    def test_schema_invalid_output_maps_to_schema_change(
        self, mapper: RemediationMapper
    ) -> None:
        vc = _make_validated(
            cluster_signature="SCHEMA.INVALID_OUTPUT",
            error_codes=["SCHEMA.INVALID_OUTPUT"],
            cohesion_score=0.9,
        )
        plan = mapper.map_validated_cluster(vc, [])
        assert plan.mapping_status == "mapped"
        assert plan.proposed_actions[0]["action_type"] == "schema_change"
        assert plan.proposed_actions[0]["target_component"] == "output_schema_contract"


# ===========================================================================
# 7. RemediationMapper: INPUT.BAD_TRANSCRIPT_QUALITY mapping (Rule D)
# ===========================================================================


class TestRemediationMapperInputQuality:
    def test_bad_transcript_quality_maps_to_input_quality_rule_change(
        self, mapper: RemediationMapper
    ) -> None:
        vc = _make_validated(
            cluster_signature="INPUT.BAD_TRANSCRIPT_QUALITY",
            error_codes=["INPUT.BAD_TRANSCRIPT_QUALITY"],
            cohesion_score=0.9,
        )
        plan = mapper.map_validated_cluster(vc, [])
        assert plan.mapping_status == "mapped"
        assert plan.proposed_actions[0]["action_type"] == "input_quality_rule_change"
        assert plan.proposed_actions[0]["target_component"] == "transcript_preprocessing_rules"


# ===========================================================================
# 8. RemediationMapper: RETRIEVE.* mapping (Rule E)
# ===========================================================================


class TestRemediationMapperRetrieval:
    def test_retrieve_dominant_maps_to_retrieval_change(
        self, mapper: RemediationMapper
    ) -> None:
        vc = _make_validated(
            cluster_signature="RETRIEVE.MISSING_CONTEXT",
            error_codes=["RETRIEVE.MISSING_CONTEXT"],
            cohesion_score=0.9,
        )
        plan = mapper.map_validated_cluster(vc, [])
        assert plan.mapping_status == "mapped"
        assert plan.proposed_actions[0]["action_type"] == "retrieval_change"
        assert plan.proposed_actions[0]["target_component"] == "retrieval_selection_rules"


# ===========================================================================
# 9. RemediationMapper: ambiguous cluster (Rule G)
# ===========================================================================


class TestRemediationMapperAmbiguous:
    def test_mixed_cluster_with_no_dominant_signal_is_ambiguous(
        self, mapper: RemediationMapper
    ) -> None:
        # Low cohesion so no single dominant code passes the threshold
        vc = _make_validated(
            cluster_signature="MISC.UNKNOWN",
            error_codes=["MISC.UNKNOWN"],
            cohesion_score=0.3,
            actionability_score=0.3,
        )
        plan = mapper.map_validated_cluster(vc, [])
        assert plan.mapping_status == "ambiguous"

    def test_ambiguous_plan_has_no_action(self, mapper: RemediationMapper) -> None:
        vc = _make_validated(
            cluster_signature="MISC.UNKNOWN",
            error_codes=["MISC.UNKNOWN"],
            cohesion_score=0.3,
            actionability_score=0.3,
        )
        plan = mapper.map_validated_cluster(vc, [])
        assert plan.proposed_actions[0]["action_type"] == "no_action"

    def test_ambiguous_reasons_mention_rule_g(self, mapper: RemediationMapper) -> None:
        vc = _make_validated(
            cluster_signature="MISC.UNKNOWN",
            error_codes=["MISC.UNKNOWN"],
            cohesion_score=0.3,
        )
        plan = mapper.map_validated_cluster(vc, [])
        assert any("rule_G" in r for r in plan.mapping_reasons)


# ===========================================================================
# 10. Max 2 proposed actions
# ===========================================================================


class TestMaxProposedActions:
    def test_proposed_actions_never_exceed_two(self, mapper: RemediationMapper) -> None:
        for sig in [
            "GROUND.MISSING_REF",
            "EXTRACT.MISSED_DECISION",
            "SCHEMA.INVALID_OUTPUT",
            "INPUT.BAD_TRANSCRIPT_QUALITY",
            "RETRIEVE.MISSING_CONTEXT",
        ]:
            vc = _make_validated(
                cluster_signature=sig,
                error_codes=[sig],
                cohesion_score=0.9,
            )
            plan = mapper.map_validated_cluster(vc, [])
            assert len(plan.proposed_actions) <= 2, (
                f"Too many proposed actions for {sig}: {len(plan.proposed_actions)}"
            )


# ===========================================================================
# 11. Target registry
# ===========================================================================


class TestTargetRegistry:
    def test_known_components_are_accepted(self) -> None:
        for name in KNOWN_TARGET_COMPONENTS:
            result = validate_target_component(name)
            assert result == name

    def test_unknown_component_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown target_component"):
            validate_target_component("totally_made_up_component")

    def test_registry_contains_required_names(self) -> None:
        required = [
            "decision_extraction_prompt",
            "action_item_extraction_prompt",
            "contradiction_detection_prompt",
            "gap_detection_prompt",
            "adversarial_review_prompt",
            "grounding_verifier",
            "synthesis_grounding_rules",
            "output_schema_contract",
            "transcript_preprocessing_rules",
            "slide_preprocessing_rules",
            "retrieval_selection_rules",
            "observability_emission_rules",
        ]
        for name in required:
            assert name in KNOWN_TARGET_COMPONENTS, f"Missing from registry: {name}"


# ===========================================================================
# 12. Confidence scoring
# ===========================================================================


class TestConfidenceScoring:
    def test_high_confidence_when_all_inputs_strong(self) -> None:
        score = compute_mapping_confidence(
            cohesion_score=0.9,
            actionability_score=0.9,
            avg_confidence=0.9,
            dominant_share=0.9,
        )
        assert score >= 0.75

    def test_low_confidence_when_all_inputs_weak(self) -> None:
        score = compute_mapping_confidence(
            cohesion_score=0.2,
            actionability_score=0.2,
            avg_confidence=0.2,
            dominant_share=0.2,
        )
        assert score < 0.5

    def test_confidence_is_clamped_between_zero_and_one(self) -> None:
        score = compute_mapping_confidence(
            cohesion_score=1.0,
            actionability_score=1.0,
            avg_confidence=1.0,
            dominant_share=1.0,
        )
        assert 0.0 <= score <= 1.0

        score_low = compute_mapping_confidence(
            cohesion_score=0.0,
            actionability_score=0.0,
            avg_confidence=0.0,
            dominant_share=0.0,
        )
        assert 0.0 <= score_low <= 1.0


# ===========================================================================
# 13. Risk scoring
# ===========================================================================


class TestRiskScoring:
    def test_schema_change_is_at_least_medium_risk(self) -> None:
        assert compute_risk_level("schema_change", 0.9) in ("medium", "high")

    def test_no_action_is_low_risk_when_confidence_high(self) -> None:
        assert compute_risk_level("no_action", 0.9) == "low"

    def test_input_quality_rule_change_is_low_or_medium(self) -> None:
        assert compute_risk_level("input_quality_rule_change", 0.9) in ("low", "medium")

    def test_low_confidence_increases_risk_level(self) -> None:
        risk_high_conf = compute_risk_level("input_quality_rule_change", 0.9)
        risk_low_conf = compute_risk_level("input_quality_rule_change", 0.1)
        risk_order = {"low": 0, "medium": 1, "high": 2}
        assert risk_order[risk_low_conf] >= risk_order[risk_high_conf]


# ===========================================================================
# 14. Pipeline integration
# ===========================================================================


class TestRemediationPipeline:
    def test_pipeline_returns_one_plan_per_cluster(self) -> None:
        clusters = [
            _make_validated(cluster_signature="GROUND.MISSING_REF"),
            _make_validated(cluster_signature="EXTRACT.MISSED_DECISION"),
            _make_validated(validation_status="invalid"),
        ]
        plans = build_remediation_plans_from_validated_clusters(
            validated_clusters=clusters,
            classification_records=[],
        )
        assert len(plans) == 3

    def test_pipeline_rejected_invalid_clusters(self) -> None:
        clusters = [_make_validated(validation_status="invalid")]
        plans = build_remediation_plans_from_validated_clusters(
            validated_clusters=clusters,
            classification_records=[],
        )
        assert plans[0].mapping_status == "rejected"

    def test_filter_mapped_returns_only_mapped(self) -> None:
        plans = [
            _make_plan(mapping_status="mapped"),
            _make_plan(mapping_status="ambiguous"),
            _make_plan(mapping_status="rejected"),
        ]
        mapped = filter_mapped_plans(plans, status="mapped")
        assert all(p.mapping_status == "mapped" for p in mapped)
        assert len(mapped) == 1

    def test_filter_none_returns_all(self) -> None:
        plans = [
            _make_plan(mapping_status="mapped"),
            _make_plan(mapping_status="ambiguous"),
        ]
        result = filter_mapped_plans(plans)
        assert len(result) == 2

    def test_summarize_remediation_targets(self) -> None:
        plans = [
            _make_plan(mapping_status="mapped"),
            _make_plan(mapping_status="ambiguous"),
            _make_plan(mapping_status="rejected"),
        ]
        summary = summarize_remediation_targets(plans)
        assert summary["total_plans"] == 3
        assert summary["mapped"] == 1
        assert summary["ambiguous"] == 1
        assert summary["rejected"] == 1
        assert "top_remediation_targets" in summary
        assert "top_proposed_actions" in summary


# ===========================================================================
# 15. Store round-trip
# ===========================================================================


class TestRemediationStore:
    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        plan = _make_plan()
        save_remediation_plan(plan, store_dir=tmp_path)
        loaded = load_remediation_plan(plan.remediation_id, store_dir=tmp_path)
        assert loaded.remediation_id == plan.remediation_id
        assert loaded.mapping_status == plan.mapping_status

    def test_save_raises_on_duplicate(self, tmp_path: Path) -> None:
        plan = _make_plan()
        save_remediation_plan(plan, store_dir=tmp_path)
        with pytest.raises(FileExistsError):
            save_remediation_plan(plan, store_dir=tmp_path)

    def test_load_raises_for_missing_id(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_remediation_plan("does-not-exist", store_dir=tmp_path)

    def test_list_returns_all_plans(self, tmp_path: Path) -> None:
        plan_a = _make_plan(mapping_status="mapped")
        plan_b = _make_plan(mapping_status="ambiguous")
        save_remediation_plan(plan_a, store_dir=tmp_path)
        save_remediation_plan(plan_b, store_dir=tmp_path)
        results = list_remediation_plans(store_dir=tmp_path)
        assert len(results) == 2

    def test_list_with_status_filter(self, tmp_path: Path) -> None:
        plan_a = _make_plan(mapping_status="mapped")
        plan_b = _make_plan(mapping_status="ambiguous")
        save_remediation_plan(plan_a, store_dir=tmp_path)
        save_remediation_plan(plan_b, store_dir=tmp_path)
        mapped = list_remediation_plans(store_dir=tmp_path, filters={"mapping_status": "mapped"})
        assert len(mapped) == 1
        assert mapped[0].mapping_status == "mapped"

    def test_list_empty_dir_returns_empty(self, tmp_path: Path) -> None:
        results = list_remediation_plans(store_dir=tmp_path)
        assert results == []

    def test_list_nonexistent_dir_returns_empty(self, tmp_path: Path) -> None:
        results = list_remediation_plans(store_dir=tmp_path / "does_not_exist")
        assert results == []
