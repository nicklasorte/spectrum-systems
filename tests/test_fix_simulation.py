"""
Tests for the AW2 Fix Simulation Sandbox (Prompt AW2).

Covers:
- Schema file: simulation_result.schema.json exists
- SimulationResult: serialisation round-trip
- SimulationResult: schema validation
- FixSimulator: ambiguous/rejected plan handling (gate rejection)
- FixSimulator: mapped plan simulation
- Strategy routing: prompt_change
- Strategy routing: grounding_rule_change
- Strategy routing: schema_change
- Strategy routing: input_quality_rule_change
- Strategy routing: retrieval_change
- Strategy routing: observability_change
- Strategy routing: no_action (inconclusive)
- Strategy routing: unknown action_type (inconclusive)
- Baseline/candidate delta calculation
- compare_baseline_candidate
- summarize_targeted_effect
- check_regression: hard failure detection
- check_regression: warning detection
- check_regression: all pass
- determine_promotion_recommendation: promote
- determine_promotion_recommendation: hold (warnings)
- determine_promotion_recommendation: hold (low fidelity)
- determine_promotion_recommendation: reject (hard failure)
- determine_promotion_recommendation: reject (target metric worsened)
- determine_promotion_recommendation: reject (fidelity=none)
- case_selection: targeted case selection by error_codes
- case_selection: fallback when no linked cases
- case_selection: weak linkage fallback to all golden cases
- case_selection: empty dataset
- simulation_store: save and load round-trip
- simulation_store: list with filters
- simulation_store: FileExistsError on duplicate save
- simulation_store: FileNotFoundError on missing load
- simulation_pipeline: run_simulation_for_plan
- simulation_pipeline: run_simulation_batch
- simulation_pipeline: summarize_simulation_outcomes
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

from spectrum_systems.modules.error_taxonomy.classify import ErrorClassificationRecord
from spectrum_systems.modules.error_taxonomy.cluster_validation import ValidatedCluster
from spectrum_systems.modules.improvement.remediation_mapping import (
    RemediationMapper,
    RemediationPlan,
)
from spectrum_systems.modules.improvement.simulation import FixSimulator, SimulationResult
from spectrum_systems.modules.improvement.simulation_compare import (
    check_regression,
    compare_baseline_candidate,
    determine_promotion_recommendation,
    summarize_targeted_effect,
)
from spectrum_systems.modules.improvement.simulation_pipeline import (
    run_simulation_batch,
    run_simulation_for_plan,
    summarize_simulation_outcomes,
)
from spectrum_systems.modules.improvement.simulation_store import (
    list_simulation_results,
    load_simulation_result,
    save_simulation_result,
)
from spectrum_systems.modules.improvement.case_selection import select_cases_for_plan
from spectrum_systems.modules.improvement.simulation_strategies import route_strategy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parents[1]

_BASELINE = {
    "cases_run": 3,
    "structural_score": 0.70,
    "semantic_score": 0.70,
    "grounding_score": 0.65,
    "latency_ms": 250.0,
}


def _make_validated(
    *,
    validation_status: str = "valid",
    cluster_id: str | None = None,
    cluster_signature: str = "GROUND.MISSING_REF",
    error_codes: List[str] | None = None,
    cohesion_score: float = 0.85,
    actionability_score: float = 0.85,
    record_count: int = 5,
) -> ValidatedCluster:
    return ValidatedCluster(
        cluster_id=cluster_id or str(uuid.uuid4()),
        cluster_signature=cluster_signature,
        record_count=record_count,
        error_codes=error_codes if error_codes is not None else [cluster_signature],
        pass_types=["extraction"],
        remediation_targets=["grounding"],
        validation_status=validation_status,
        validation_reasons=["size_ok: record_count=5 >= min=3"],
        stability_score=0.9,
        cohesion_score=cohesion_score,
        actionability_score=actionability_score,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _make_plan(
    *,
    mapping_status: str = "mapped",
    action_type: str = "grounding_rule_change",
    target_component: str = "grounding_verifier",
    cluster_id: str | None = None,
    dominant_error_codes: List[str] | None = None,
) -> RemediationPlan:
    rid = str(uuid.uuid4())
    cid = cluster_id or str(uuid.uuid4())
    return RemediationPlan(
        remediation_id=rid,
        cluster_id=cid,
        cluster_signature="GROUND.MISSING_REF",
        taxonomy_version="1.0",
        created_at=datetime.now(timezone.utc).isoformat(),
        mapping_status=mapping_status,
        mapping_reasons=["rule_A: dominant GROUND family"],
        dominant_error_codes=dominant_error_codes or ["GROUND.MISSING_REF"],
        remediation_targets=[target_component],
        proposed_actions=[
            {
                "action_id": str(uuid.uuid4()),
                "action_type": action_type,
                "target_component": target_component,
                "rationale": "Test rationale.",
                "expected_benefit": "Improve grounding.",
                "risk_level": "medium",
                "confidence_score": 0.8,
            }
        ],
        primary_proposal_index=0,
        evidence_summary={
            "record_count": 5,
            "avg_cluster_confidence": 0.8,
            "weighted_severity_score": 0.0,
            "pass_types": ["extraction"],
        },
    )


def _make_golden_cases(n: int = 3) -> List[Dict[str, Any]]:
    return [
        {
            "case_id": f"case-{i:03d}",
            "error_codes": ["GROUND.MISSING_REF"] if i == 0 else [],
            "tags": ["golden"],
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# 1. Schema file exists
# ---------------------------------------------------------------------------


def test_simulation_result_schema_file_exists():
    schema_path = _ROOT / "contracts" / "schemas" / "simulation_result.schema.json"
    assert schema_path.exists(), f"Schema file missing: {schema_path}"


def test_simulation_result_schema_is_valid_json():
    schema_path = _ROOT / "contracts" / "schemas" / "simulation_result.schema.json"
    with open(schema_path, encoding="utf-8") as fh:
        schema = json.load(fh)
    assert schema.get("$schema") is not None
    assert schema.get("type") == "object"
    assert schema.get("additionalProperties") is False


# ---------------------------------------------------------------------------
# 2. SimulationResult serialisation round-trip
# ---------------------------------------------------------------------------


def test_simulation_result_round_trip():
    plan = _make_plan()
    simulator = FixSimulator(golden_dataset=_make_golden_cases(), baseline_summary=_BASELINE)
    result = simulator.simulate_plan(plan)

    data = result.to_dict()
    restored = SimulationResult.from_dict(data)

    assert restored.simulation_id == result.simulation_id
    assert restored.remediation_id == result.remediation_id
    assert restored.cluster_id == result.cluster_id
    assert restored.simulation_status == result.simulation_status
    assert restored.promotion_recommendation == result.promotion_recommendation
    assert restored.baseline_summary == result.baseline_summary
    assert restored.candidate_summary == result.candidate_summary
    assert restored.deltas == result.deltas
    assert restored.targeted_effect == result.targeted_effect
    assert restored.regression_check == result.regression_check
    assert restored.evidence == result.evidence


# ---------------------------------------------------------------------------
# 3. SimulationResult schema validation
# ---------------------------------------------------------------------------


def test_simulation_result_schema_validation_valid():
    plan = _make_plan()
    simulator = FixSimulator(golden_dataset=_make_golden_cases(), baseline_summary=_BASELINE)
    result = simulator.simulate_plan(plan)
    errors = result.validate_against_schema()
    assert errors == [], f"Schema validation errors: {errors}"


def test_simulation_result_schema_validation_invalid():
    plan = _make_plan()
    simulator = FixSimulator(golden_dataset=_make_golden_cases(), baseline_summary=_BASELINE)
    result = simulator.simulate_plan(plan)
    # Corrupt the status field
    data = result.to_dict()
    data["simulation_status"] = "INVALID_VALUE"
    bad = SimulationResult.from_dict(data)
    errors = bad.validate_against_schema()
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# 4. FixSimulator: gate — ambiguous/rejected plans are rejected
# ---------------------------------------------------------------------------


def test_simulator_rejects_ambiguous_plan():
    plan = _make_plan(mapping_status="ambiguous")
    simulator = FixSimulator(baseline_summary=_BASELINE)
    result = simulator.simulate_plan(plan)
    assert result.simulation_status == "rejected"
    assert result.promotion_recommendation == "reject"
    assert any("mapping_status" in r for r in result.simulation_reasons)


def test_simulator_rejects_rejected_plan():
    plan = _make_plan(mapping_status="rejected")
    simulator = FixSimulator(baseline_summary=_BASELINE)
    result = simulator.simulate_plan(plan)
    assert result.simulation_status == "rejected"
    assert result.promotion_recommendation == "reject"


# ---------------------------------------------------------------------------
# 5. FixSimulator: mapped plan simulation
# ---------------------------------------------------------------------------


def test_simulator_simulates_mapped_plan():
    plan = _make_plan(mapping_status="mapped", action_type="grounding_rule_change")
    simulator = FixSimulator(golden_dataset=_make_golden_cases(), baseline_summary=_BASELINE)
    result = simulator.simulate_plan(plan)
    assert result.simulation_status in ("passed", "failed", "inconclusive")
    assert result.promotion_recommendation in ("promote", "hold", "reject")
    # Candidate summary should have same structure as baseline
    assert "structural_score" in result.candidate_summary
    assert "grounding_score" in result.candidate_summary
    assert result.baseline_summary["cases_run"] >= 0


def test_simulator_simulate_many():
    plans = [
        _make_plan(action_type="grounding_rule_change"),
        _make_plan(action_type="prompt_change", target_component="decision_extraction_prompt"),
        _make_plan(mapping_status="ambiguous"),
    ]
    simulator = FixSimulator(golden_dataset=_make_golden_cases(), baseline_summary=_BASELINE)
    results = simulator.simulate_many(plans)
    assert len(results) == 3
    assert results[2].simulation_status == "rejected"


# ---------------------------------------------------------------------------
# 6. Strategy routing by action_type
# ---------------------------------------------------------------------------


def test_strategy_prompt_change_boosts_scores():
    action = {"action_type": "prompt_change", "confidence_score": 0.8}
    result = route_strategy("prompt_change", action, _BASELINE, ["case-001", "case-002"])
    c = result["candidate_summary"]
    assert c["structural_score"] > _BASELINE["structural_score"]
    assert c["semantic_score"] > _BASELINE["semantic_score"]
    assert result["simulation_fidelity"] in ("high", "medium")


def test_strategy_grounding_rule_change_boosts_grounding():
    action = {"action_type": "grounding_rule_change", "confidence_score": 0.85}
    result = route_strategy("grounding_rule_change", action, _BASELINE, ["case-001"])
    c = result["candidate_summary"]
    assert c["grounding_score"] > _BASELINE["grounding_score"]
    assert result["simulation_fidelity"] in ("high", "medium")


def test_strategy_schema_change_boosts_structural():
    action = {"action_type": "schema_change", "confidence_score": 0.75}
    result = route_strategy("schema_change", action, _BASELINE, ["case-001"])
    c = result["candidate_summary"]
    assert c["structural_score"] > _BASELINE["structural_score"]
    assert result["simulation_fidelity"] == "medium"


def test_strategy_input_quality_rule_change_boosts_structural_and_reduces_latency():
    action = {"action_type": "input_quality_rule_change", "confidence_score": 0.9}
    result = route_strategy("input_quality_rule_change", action, _BASELINE, ["case-001"])
    c = result["candidate_summary"]
    assert c["structural_score"] > _BASELINE["structural_score"]
    assert c["latency_ms"] < _BASELINE["latency_ms"]


def test_strategy_retrieval_change_boosts_semantic_and_grounding():
    action = {"action_type": "retrieval_change", "confidence_score": 0.8}
    result = route_strategy("retrieval_change", action, _BASELINE, ["case-001"])
    c = result["candidate_summary"]
    assert c["semantic_score"] > _BASELINE["semantic_score"]
    assert c["grounding_score"] > _BASELINE["grounding_score"]


def test_strategy_observability_change_reduces_latency_only():
    action = {"action_type": "observability_change", "confidence_score": 0.9}
    result = route_strategy("observability_change", action, _BASELINE, ["case-001"])
    c = result["candidate_summary"]
    assert c["latency_ms"] < _BASELINE["latency_ms"]
    assert c["structural_score"] == _BASELINE["structural_score"]
    assert result["simulation_fidelity"] == "low"


def test_strategy_no_action_returns_inconclusive():
    action = {"action_type": "no_action", "confidence_score": 0.5}
    result = route_strategy("no_action", action, _BASELINE, [])
    assert result["simulation_fidelity"] == "none"
    assert "no_action" in result["strategy_notes"][0]


def test_strategy_unknown_action_type_returns_inconclusive():
    action = {"action_type": "unknown_xyz", "confidence_score": 0.5}
    result = route_strategy("unknown_xyz", action, _BASELINE, [])
    assert result["simulation_fidelity"] == "none"
    assert "unknown_action_type" in result["strategy_notes"][0]


# ---------------------------------------------------------------------------
# 7. Baseline/candidate delta calculation
# ---------------------------------------------------------------------------


def test_compare_baseline_candidate_zero_delta():
    deltas = compare_baseline_candidate(_BASELINE, _BASELINE)
    assert deltas["structural_score_delta"] == 0.0
    assert deltas["semantic_score_delta"] == 0.0
    assert deltas["grounding_score_delta"] == 0.0
    assert deltas["latency_ms_delta"] == 0.0


def test_compare_baseline_candidate_positive_delta():
    candidate = dict(_BASELINE)
    candidate["structural_score"] = 0.80
    candidate["grounding_score"] = 0.72
    deltas = compare_baseline_candidate(_BASELINE, candidate)
    assert abs(deltas["structural_score_delta"] - 0.10) < 1e-4
    assert abs(deltas["grounding_score_delta"] - 0.07) < 1e-4


def test_compare_baseline_candidate_negative_delta():
    candidate = dict(_BASELINE)
    candidate["structural_score"] = 0.55  # regression
    deltas = compare_baseline_candidate(_BASELINE, candidate)
    assert deltas["structural_score_delta"] < 0.0


# ---------------------------------------------------------------------------
# 8. summarize_targeted_effect
# ---------------------------------------------------------------------------


def test_targeted_effect_observed_increase():
    action = {"target_component": "grounding_verifier", "confidence_score": 0.8}
    deltas = {"grounding_score_delta": 0.05}
    effect = summarize_targeted_effect(action, deltas, "grounding_rule_change")
    assert effect["target_metric"] == "grounding_score"
    assert effect["expected_direction"] == "increase"
    assert effect["observed_direction"] == "increase"


def test_targeted_effect_observed_none():
    action = {"target_component": "grounding_verifier", "confidence_score": 0.8}
    deltas = {"grounding_score_delta": 0.0}
    effect = summarize_targeted_effect(action, deltas, "grounding_rule_change")
    assert effect["observed_direction"] == "none"


def test_targeted_effect_observed_decrease():
    action = {"target_component": "grounding_verifier", "confidence_score": 0.8}
    deltas = {"grounding_score_delta": -0.05}
    effect = summarize_targeted_effect(action, deltas, "grounding_rule_change")
    assert effect["observed_direction"] == "decrease"


def test_targeted_effect_latency_decrease():
    action = {"target_component": "observability_output", "confidence_score": 0.8}
    deltas = {"latency_ms_delta": -5.0}
    effect = summarize_targeted_effect(action, deltas, "observability_change")
    assert effect["expected_direction"] == "decrease"
    assert effect["observed_direction"] == "decrease"


# ---------------------------------------------------------------------------
# 9. check_regression
# ---------------------------------------------------------------------------


def test_check_regression_all_pass():
    candidate = dict(_BASELINE)
    candidate["structural_score"] = 0.72  # small improvement
    rc = check_regression(_BASELINE, candidate)
    assert rc["overall_pass"] is True
    assert rc["hard_failures"] == 0
    assert rc["warnings"] == 0


def test_check_regression_warning():
    candidate = dict(_BASELINE)
    candidate["structural_score"] = 0.66  # -0.04, within warn threshold (-0.03 to -0.10)
    rc = check_regression(_BASELINE, candidate)
    assert rc["hard_failures"] == 0
    assert rc["warnings"] >= 1


def test_check_regression_hard_failure():
    candidate = dict(_BASELINE)
    candidate["structural_score"] = 0.55  # -0.15, hard failure
    rc = check_regression(_BASELINE, candidate)
    assert rc["overall_pass"] is False
    assert rc["hard_failures"] >= 1


def test_check_regression_multiple_failures():
    candidate = dict(_BASELINE)
    candidate["structural_score"] = 0.55
    candidate["semantic_score"] = 0.55
    candidate["grounding_score"] = 0.50
    rc = check_regression(_BASELINE, candidate)
    assert rc["hard_failures"] >= 2


# ---------------------------------------------------------------------------
# 10. determine_promotion_recommendation
# ---------------------------------------------------------------------------


def _make_targeted_effect(expected: str = "increase", observed: str = "increase") -> Dict:
    return {
        "target_component": "grounding_verifier",
        "target_metric": "grounding_score",
        "expected_direction": expected,
        "observed_direction": observed,
    }


def _make_regression_check(hard: int = 0, warnings: int = 0) -> Dict:
    return {"overall_pass": hard == 0, "hard_failures": hard, "warnings": warnings}


def test_promote_high_fidelity_no_regressions():
    rec = determine_promotion_recommendation(
        simulation_fidelity="high",
        targeted_effect=_make_targeted_effect("increase", "increase"),
        regression_check=_make_regression_check(0, 0),
        deltas={"grounding_score_delta": 0.05},
    )
    assert rec == "promote"


def test_promote_medium_fidelity_no_regressions():
    rec = determine_promotion_recommendation(
        simulation_fidelity="medium",
        targeted_effect=_make_targeted_effect("increase", "increase"),
        regression_check=_make_regression_check(0, 0),
        deltas={"grounding_score_delta": 0.03},
    )
    assert rec == "promote"


def test_hold_with_warnings():
    rec = determine_promotion_recommendation(
        simulation_fidelity="high",
        targeted_effect=_make_targeted_effect("increase", "increase"),
        regression_check=_make_regression_check(0, 1),
        deltas={"grounding_score_delta": 0.03},
    )
    assert rec == "hold"


def test_hold_low_fidelity():
    rec = determine_promotion_recommendation(
        simulation_fidelity="low",
        targeted_effect=_make_targeted_effect("increase", "increase"),
        regression_check=_make_regression_check(0, 0),
        deltas={"grounding_score_delta": 0.02},
    )
    assert rec == "hold"


def test_reject_hard_failure():
    rec = determine_promotion_recommendation(
        simulation_fidelity="high",
        targeted_effect=_make_targeted_effect("increase", "increase"),
        regression_check=_make_regression_check(1, 0),
        deltas={"grounding_score_delta": 0.05},
    )
    assert rec == "reject"


def test_reject_target_metric_worsened():
    rec = determine_promotion_recommendation(
        simulation_fidelity="high",
        targeted_effect=_make_targeted_effect("increase", "decrease"),
        regression_check=_make_regression_check(0, 0),
        deltas={"grounding_score_delta": -0.05},
    )
    assert rec == "reject"


def test_reject_fidelity_none():
    rec = determine_promotion_recommendation(
        simulation_fidelity="none",
        targeted_effect=_make_targeted_effect("increase", "none"),
        regression_check=_make_regression_check(0, 0),
        deltas={"grounding_score_delta": 0.0},
    )
    assert rec == "reject"


# ---------------------------------------------------------------------------
# 11. Case selection
# ---------------------------------------------------------------------------


def test_case_selection_targeted_by_error_codes():
    plan = _make_plan(dominant_error_codes=["GROUND.MISSING_REF"])
    dataset = _make_golden_cases(3)
    # dataset[0] has error_codes=["GROUND.MISSING_REF"] — should be targeted
    result = select_cases_for_plan(plan, dataset)
    assert "case-000" in result["selected_case_ids"]
    assert len(result["selection_reasons"]) > 0


def test_case_selection_fallback_when_no_linked_cases():
    plan = _make_plan(dominant_error_codes=["SOME.UNKNOWN.CODE"])
    dataset = _make_golden_cases(3)
    result = select_cases_for_plan(plan, dataset)
    # Should fall back gracefully
    assert len(result["selected_case_ids"]) > 0 or "no_cases" in str(result["selection_reasons"])


def test_case_selection_weak_linkage_fallback():
    plan = _make_plan(dominant_error_codes=["SOME.UNKNOWN.CODE"])
    # Only one case available → weak linkage fallback should include all
    dataset = [{"case_id": "case-single", "error_codes": []}]
    result = select_cases_for_plan(plan, dataset)
    # With one case, returns that one case
    assert result["selected_case_ids"] == ["case-single"]


def test_case_selection_empty_dataset():
    plan = _make_plan()
    result = select_cases_for_plan(plan, [])
    assert result["selected_case_ids"] == []
    assert any("no_cases" in r for r in result["selection_reasons"])


def test_case_selection_control_and_targeted_present():
    plan = _make_plan(dominant_error_codes=["GROUND.MISSING_REF"])
    dataset = [
        {"case_id": "targeted-1", "error_codes": ["GROUND.MISSING_REF"]},
        {"case_id": "control-1", "error_codes": []},
        {"case_id": "control-2", "error_codes": []},
    ]
    result = select_cases_for_plan(plan, dataset)
    assert "targeted-1" in result["selected_case_ids"]
    assert "control-1" in result["selected_case_ids"]


# ---------------------------------------------------------------------------
# 12. Storage round-trip
# ---------------------------------------------------------------------------


def test_simulation_store_round_trip(tmp_path):
    plan = _make_plan()
    simulator = FixSimulator(golden_dataset=_make_golden_cases(), baseline_summary=_BASELINE)
    result = simulator.simulate_plan(plan)

    saved_path = save_simulation_result(result, tmp_path)
    assert saved_path.exists()

    loaded = load_simulation_result(result.simulation_id, tmp_path)
    assert loaded.simulation_id == result.simulation_id
    assert loaded.simulation_status == result.simulation_status
    assert loaded.promotion_recommendation == result.promotion_recommendation


def test_simulation_store_file_exists_error(tmp_path):
    plan = _make_plan()
    simulator = FixSimulator(golden_dataset=_make_golden_cases(), baseline_summary=_BASELINE)
    result = simulator.simulate_plan(plan)
    save_simulation_result(result, tmp_path)
    with pytest.raises(FileExistsError):
        save_simulation_result(result, tmp_path)


def test_simulation_store_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_simulation_result("nonexistent-id", tmp_path)


def test_simulation_store_list_with_filters(tmp_path):
    plans = [
        _make_plan(action_type="grounding_rule_change"),
        _make_plan(action_type="prompt_change", target_component="decision_extraction_prompt"),
        _make_plan(mapping_status="ambiguous"),
    ]
    simulator = FixSimulator(golden_dataset=_make_golden_cases(), baseline_summary=_BASELINE)
    results = simulator.simulate_many(plans)

    for r in results:
        try:
            save_simulation_result(r, tmp_path)
        except FileExistsError:
            pass

    # List all
    all_results = list_simulation_results(tmp_path)
    assert len(all_results) == 3

    # Filter by simulation_status=rejected
    rejected = list_simulation_results(tmp_path, {"simulation_status": "rejected"})
    assert all(r.simulation_status == "rejected" for r in rejected)
    assert len(rejected) == 1


def test_simulation_store_empty_dir(tmp_path):
    results = list_simulation_results(tmp_path)
    assert results == []


def test_simulation_store_nonexistent_dir():
    results = list_simulation_results(Path("/tmp/nonexistent-aw2-store-xyz"))
    assert results == []


# ---------------------------------------------------------------------------
# 13. Pipeline
# ---------------------------------------------------------------------------


def test_run_simulation_for_plan():
    plan = _make_plan()
    result = run_simulation_for_plan(plan, golden_dataset=_make_golden_cases(), baseline_summary=_BASELINE)
    assert result is not None
    assert result.remediation_id == plan.remediation_id


def test_run_simulation_batch():
    plans = [
        _make_plan(action_type="grounding_rule_change"),
        _make_plan(action_type="schema_change", target_component="output_schema_contract"),
        _make_plan(mapping_status="ambiguous"),
    ]
    results = run_simulation_batch(plans, golden_dataset=_make_golden_cases(), baseline_summary=_BASELINE)
    assert len(results) == 3


def test_summarize_simulation_outcomes_structure():
    plans = [
        _make_plan(action_type="grounding_rule_change"),
        _make_plan(action_type="prompt_change", target_component="decision_extraction_prompt"),
        _make_plan(mapping_status="ambiguous"),
    ]
    simulator = FixSimulator(golden_dataset=_make_golden_cases(), baseline_summary=_BASELINE)
    results = simulator.simulate_many(plans)

    summary = summarize_simulation_outcomes(results)
    assert "total_results" in summary
    assert summary["total_results"] == 3
    assert "by_status" in summary
    assert "by_recommendation" in summary
    assert "promotable_plans" in summary
    assert "held_plans" in summary
    assert "rejected_plans" in summary
    assert "top_targeted_improvements" in summary
    assert "top_regressions_detected" in summary


def test_summarize_simulation_outcomes_rejected_plans_counted():
    plans = [_make_plan(mapping_status="ambiguous")]
    simulator = FixSimulator(golden_dataset=[], baseline_summary=_BASELINE)
    results = simulator.simulate_many(plans)
    summary = summarize_simulation_outcomes(results)
    assert len(summary["rejected_plans"]) == 1
    assert summary["by_recommendation"].get("reject", 0) == 1


def test_summarize_simulation_outcomes_empty():
    summary = summarize_simulation_outcomes([])
    assert summary["total_results"] == 0
    assert summary["promotable_plans"] == []


# ---------------------------------------------------------------------------
# 14. End-to-end: real AW1 mapper → AW2 simulator
# ---------------------------------------------------------------------------


def test_end_to_end_aw1_to_aw2():
    """Verify that plans produced by the AW1 mapper can be simulated by AW2."""
    vc = _make_validated(cluster_signature="GROUND.MISSING_REF", validation_status="valid")
    mapper = RemediationMapper(taxonomy_version="1.0")
    plan = mapper.map_validated_cluster(vc, [])

    assert plan.mapping_status == "mapped"

    simulator = FixSimulator(golden_dataset=_make_golden_cases(), baseline_summary=_BASELINE)
    result = simulator.simulate_plan(plan)

    assert result.remediation_id == plan.remediation_id
    assert result.cluster_id == plan.cluster_id
    assert result.simulation_status in ("passed", "failed", "inconclusive", "rejected")
    errors = result.validate_against_schema()
    assert errors == [], f"Schema validation errors: {errors}"


def test_end_to_end_invalid_cluster_rejected():
    """Invalid clusters from AW0 produce rejected AW1 plans that AW2 also rejects."""
    vc = _make_validated(validation_status="invalid")
    mapper = RemediationMapper(taxonomy_version="1.0")
    plan = mapper.map_validated_cluster(vc, [])

    assert plan.mapping_status == "rejected"

    simulator = FixSimulator(golden_dataset=_make_golden_cases(), baseline_summary=_BASELINE)
    result = simulator.simulate_plan(plan)

    assert result.simulation_status == "rejected"
    assert result.promotion_recommendation == "reject"


# ---------------------------------------------------------------------------
# 15. Safety invariant: minimum improvement threshold
# ---------------------------------------------------------------------------


def test_hold_below_minimum_improvement_high_fidelity():
    """Sub-threshold delta must not produce 'promote' even at high fidelity."""
    rec = determine_promotion_recommendation(
        simulation_fidelity="high",
        targeted_effect=_make_targeted_effect("increase", "increase"),
        regression_check=_make_regression_check(0, 0),
        deltas={"grounding_score_delta": 0.005},  # below _MIN_IMPROVEMENT_FOR_PROMOTE=0.01
    )
    assert rec == "hold"


def test_hold_below_minimum_improvement_medium_fidelity():
    """Sub-threshold delta must not produce 'promote' even at medium fidelity."""
    rec = determine_promotion_recommendation(
        simulation_fidelity="medium",
        targeted_effect=_make_targeted_effect("increase", "increase"),
        regression_check=_make_regression_check(0, 0),
        deltas={"grounding_score_delta": 0.009},  # just below threshold
    )
    assert rec == "hold"


def test_promote_at_exactly_minimum_improvement():
    """Delta exactly at the minimum threshold should be allowed to promote."""
    rec = determine_promotion_recommendation(
        simulation_fidelity="high",
        targeted_effect=_make_targeted_effect("increase", "increase"),
        regression_check=_make_regression_check(0, 0),
        deltas={"grounding_score_delta": 0.01},  # exactly at threshold
    )
    assert rec == "promote"


# ---------------------------------------------------------------------------
# 16. Safety invariant: latency regression detection
# ---------------------------------------------------------------------------


def test_check_regression_latency_hard_failure():
    """A large latency increase must produce a hard failure."""
    candidate = dict(_BASELINE)
    candidate["latency_ms"] = 350.0  # +100 ms — hard failure
    rc = check_regression(_BASELINE, candidate)
    assert rc["overall_pass"] is False
    assert rc["hard_failures"] >= 1


def test_check_regression_latency_warning():
    """A moderate latency increase must produce a warning."""
    candidate = dict(_BASELINE)
    candidate["latency_ms"] = 275.0  # +25 ms — within warning band
    rc = check_regression(_BASELINE, candidate)
    assert rc["hard_failures"] == 0
    assert rc["warnings"] >= 1


def test_check_regression_latency_no_regression():
    """A latency improvement (decrease) must not trigger any regression signal."""
    candidate = dict(_BASELINE)
    candidate["latency_ms"] = 245.0  # -5 ms — improvement
    rc = check_regression(_BASELINE, candidate)
    assert rc["hard_failures"] == 0
    assert rc["warnings"] == 0


def test_check_regression_latency_small_increase_no_warning():
    """A latency increase below the warning threshold must not trigger a warning."""
    candidate = dict(_BASELINE)
    candidate["latency_ms"] = 260.0  # +10 ms — below warning threshold
    rc = check_regression(_BASELINE, candidate)
    assert rc["hard_failures"] == 0
    assert rc["warnings"] == 0


# ---------------------------------------------------------------------------
# 17. Safety invariant: simulation_status = "rejected" for unsimulable actions
# ---------------------------------------------------------------------------


def test_simulation_status_no_action_is_rejected():
    """A mapped plan with no_action must produce simulation_status='rejected'."""
    plan = _make_plan(action_type="no_action")
    simulator = FixSimulator(golden_dataset=_make_golden_cases(), baseline_summary=_BASELINE)
    result = simulator.simulate_plan(plan)
    assert result.simulation_status == "rejected"
    assert result.promotion_recommendation == "reject"


def test_simulation_status_unknown_action_is_rejected():
    """A mapped plan with an unknown action_type must produce simulation_status='rejected'."""
    plan = _make_plan(action_type="totally_unknown_action")
    simulator = FixSimulator(golden_dataset=_make_golden_cases(), baseline_summary=_BASELINE)
    result = simulator.simulate_plan(plan)
    assert result.simulation_status == "rejected"
    assert result.promotion_recommendation == "reject"


def test_schema_validates_rejected_status_for_no_action():
    """Schema validation must pass for a no_action result with simulation_status='rejected'."""
    plan = _make_plan(action_type="no_action")
    simulator = FixSimulator(golden_dataset=_make_golden_cases(), baseline_summary=_BASELINE)
    result = simulator.simulate_plan(plan)
    errors = result.validate_against_schema()
    assert errors == [], f"Schema validation errors: {errors}"
