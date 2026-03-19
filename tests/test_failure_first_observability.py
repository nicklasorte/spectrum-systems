from __future__ import annotations

import json
from pathlib import Path

from scripts.run_failure_first_report import (
    _collect_case_records,
    build_failure_first_report,
)
from spectrum_systems.modules.observability.aggregation import (
    compute_failure_first_metrics,
    enrich_failure_first_flags,
)
from spectrum_systems.modules.observability.failure_ranking import (
    rank_failure_modes,
    rank_worst_cases,
)


def _case(**overrides):
    base = {
        "case_id": "case-1",
        "promotion_recommendation": "reject",
        "gating_decision_reason": "baseline",
        "failure_flags": {
            "no_decisions_extracted": False,
            "duplicate_decisions": False,
            "inconsistent_grounding": False,
            "structural_failure": False,
        },
        "gating_flags": [],
        "confidence": "low",
        "downstream_failure": False,
        "pass_results": [{"pass_type": "decision_extraction", "schema_validation": {"status": "passed"}}],
        "structural_score": 0.9,
        "adversarial_type": None,
        "expected_difficulty": None,
    }
    base.update(overrides)
    return base


def test_high_confidence_error_detection():
    record = enrich_failure_first_flags(
        _case(confidence="high", promotion_recommendation="reject")
    )
    assert record["high_confidence_error"] is True


def test_dangerous_promote_detection():
    record = enrich_failure_first_flags(
        _case(
            promotion_recommendation="promote",
            adversarial_type="contradictory_decisions",
            failure_flags={
                "no_decisions_extracted": False,
                "duplicate_decisions": True,
                "inconsistent_grounding": False,
                "structural_failure": False,
            },
        )
    )
    assert record["dangerous_promote"] is True
    assert "promoted_adversarial_case" in record["dangerous_promote_reason"]


def test_worst_case_ranking_prioritizes_dangerous_promotes_then_high_confidence_errors():
    cases = [
        _case(case_id="ordinary-reject", promotion_recommendation="reject", confidence="low"),
        _case(
            case_id="high-confidence-reject",
            promotion_recommendation="reject",
            confidence="high",
            failure_flags={
                "no_decisions_extracted": True,
                "duplicate_decisions": False,
                "inconsistent_grounding": False,
                "structural_failure": False,
            },
        ),
        _case(
            case_id="dangerous-promote",
            promotion_recommendation="promote",
            confidence="high",
            adversarial_type="overconfident_reference_minutes",
            failure_flags={
                "no_decisions_extracted": False,
                "duplicate_decisions": False,
                "inconsistent_grounding": True,
                "structural_failure": False,
            },
        ),
    ]

    ranked = rank_worst_cases(cases, limit=3)
    assert ranked[0]["case_id"] == "dangerous-promote"
    assert ranked[1]["case_id"] == "high-confidence-reject"


def test_failure_mode_ranking_counts_repeated_flags():
    cases = [
        _case(case_id="a", failure_flags={"structural_failure": True}),
        _case(case_id="b", failure_flags={"structural_failure": True}),
        _case(case_id="c", failure_flags={"duplicate_decisions": True}),
    ]
    ranked = rank_failure_modes(cases, limit=2)
    assert ranked[0]["failure_mode"] == "structural_failure"
    assert ranked[0]["count"] == 2


def test_report_generation_contains_required_sections():
    cases = [
        enrich_failure_first_flags(
            _case(
                case_id="adv-1",
                promotion_recommendation="reject",
                confidence="high",
                failure_flags={"no_decisions_extracted": True},
                adversarial_type="missing_decisions",
                expected_difficulty="hard",
            )
        ),
        enrich_failure_first_flags(
            _case(
                case_id="op-1",
                promotion_recommendation="promote",
                confidence="high",
                failure_flags={"inconsistent_grounding": True},
            )
        ),
    ]
    report = build_failure_first_report(cases)

    assert "executive_failure_summary" in report
    assert "worst_cases" in report
    assert "top_failure_modes" in report
    assert "passes_components_most_at_risk" in report
    assert "false_confidence_zones" in report
    assert "structural_health" in report
    assert report["executive_failure_summary"]["dangerous_promotes"] >= 1


def test_compute_failure_first_metrics_exposes_concentrations():
    cases = [
        _case(case_id="c1", failure_flags={"no_decisions_extracted": True}),
        _case(case_id="c2", failure_flags={"no_decisions_extracted": True}),
        _case(case_id="c3", failure_flags={"duplicate_decisions": True}),
    ]
    metrics = compute_failure_first_metrics(cases)
    assert metrics["repeated_failure_concentration"][0]["pattern"] == "no_decisions_extracted"
    assert "decision_extraction" in metrics["pass_failure_concentration"]


def test_adversarial_integration_from_observability_dir(tmp_path: Path):
    obs_dir = tmp_path / "data" / "observability"
    obs_dir.mkdir(parents=True)

    # Adversarial aggregate list payload
    (obs_dir / "adversarial_run.json").write_text(
        json.dumps(
            [
                {
                    "case_id": "adv_777",
                    "adversarial_type": "contradictory_decisions",
                    "expected_difficulty": "hard",
                    "promotion_recommendation": "reject",
                    "gating_decision_reason": "flagged",
                    "gating_flags": ["no_decisions_extracted"],
                    "failure_flags": {"no_decisions_extracted": True},
                    "pass_results": [{"pass_type": "decision_extraction", "schema_validation": {"status": "passed"}}],
                }
            ]
        ),
        encoding="utf-8",
    )

    # Standard AP observability dict payload
    (obs_dir / "record.json").write_text(
        json.dumps(
            {
                "record_id": "r1",
                "context": {"artifact_id": "art-1", "case_id": "case-std"},
                "pass_info": {"pass_type": "grounding"},
                "metrics": {"structural_score": 0.5, "semantic_score": 0.8},
                "flags": {"schema_valid": True, "grounding_passed": False},
                "error_summary": {"failure_count": 1},
            }
        ),
        encoding="utf-8",
    )

    cases = _collect_case_records(
        observability_dir=obs_dir,
        include_adversarial=True,
        include_operationalization=False,
    )
    adv = [c for c in cases if c.get("case_id") == "adv_777"][0]
    assert adv["adversarial_type"] == "contradictory_decisions"
    assert adv["expected_difficulty"] == "hard"
