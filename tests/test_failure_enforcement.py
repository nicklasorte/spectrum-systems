from __future__ import annotations

import json
from pathlib import Path

from scripts.run_failure_enforcement import _validate_against_schema, main as run_failure_enforcement_main
from spectrum_systems.modules.observability.failure_enforcement import (
    classify_incident_severity,
    evaluate_failure_controls,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_PATH = _REPO_ROOT / "contracts" / "schemas" / "failure_enforcement_decision.schema.json"


def _report_metrics(**overrides):
    base = {
        "total_cases": 10,
        "promote_rate": 0.2,
        "dangerous_promote_count": 0,
        "high_confidence_error_rate": 0.01,
        "structural_failure_rate": 0.01,
        "repeated_failure_concentration": [{"pattern": "no_decisions_extracted", "count": 2}],
        "pass_failure_concentration": {"decision_extraction": 3},
        "passes_components_most_at_risk": [
            {"pass_type": "decision_extraction", "failure_count": 3, "affected_cases": 2}
        ],
    }
    base.update(overrides)
    return base


def _record(case_id: str, pass_type: str = "decision_extraction", **overrides):
    base = {
        "case_id": case_id,
        "promotion_recommendation": "hold",
        "high_confidence_error": False,
        "dangerous_promote": False,
        "failure_flags": {
            "structural_failure": False,
            "no_decisions_extracted": False,
            "inconsistent_grounding": False,
            "duplicate_decisions": False,
        },
        "pass_results": [{"pass_type": pass_type, "schema_validation": {"status": "passed"}}],
    }
    base.update(overrides)
    return base


def test_dangerous_promote_blocks_promotion_and_flags_incident():
    decision = evaluate_failure_controls(
        _report_metrics(dangerous_promote_count=1),
        [_record("c1", dangerous_promote=True, promotion_recommendation="promote")],
        source_report_ref="outputs/failure_first_report.json",
    )
    assert decision["promotion_allowed"] is False
    assert decision["system_response"] == "incident_flag"
    assert any("dangerous_promote_count=1" in item for item in decision["triggering_conditions"])


def test_hce_threshold_triggers_human_review():
    decision = evaluate_failure_controls(
        _report_metrics(high_confidence_error_rate=0.08),
        [_record("c1", high_confidence_error=True)],
    )
    assert decision["system_response"] == "require_human_review"
    assert "require_human_review_before_promotion" in decision["required_actions"]


def test_weak_components_get_suppressed():
    records = [
        _record(
            "c1",
            pass_type="grounding",
            high_confidence_error=True,
            failure_flags={"structural_failure": True, "no_decisions_extracted": True},
        ),
        _record(
            "c2",
            pass_type="grounding",
            high_confidence_error=True,
            failure_flags={"structural_failure": True, "no_decisions_extracted": True},
        ),
    ]
    decision = evaluate_failure_controls(
        _report_metrics(
            pass_failure_concentration={"grounding": 4},
            passes_components_most_at_risk=[{"pass_type": "grounding", "failure_count": 4}],
        ),
        records,
    )
    assert "grounding" in decision["suppressed_components"]
    grounding = [row for row in decision["component_health"] if row["component"] == "grounding"][0]
    assert 0.0 <= grounding["component_health_score"] <= 1.0


def test_repeated_failure_concentration_creates_remediation_flag():
    decision = evaluate_failure_controls(
        _report_metrics(total_cases=10, repeated_failure_concentration=[{"pattern": "duplicate_decisions", "count": 8}]),
        [_record("c1")],
    )
    assert "priority_remediation_required" in decision["required_actions"]
    assert decision["incident_severity"] in {"medium", "low", "high", "critical"}


def test_incident_severity_logic():
    metrics = _report_metrics(
        dangerous_promote_count=1,
        promote_rate=0.3,
        high_confidence_error_rate=0.07,
        structural_failure_rate=0.2,
    )
    severity = classify_incident_severity(
        metrics,
        {
            "triggering_conditions": ["dangerous_promote_count=1"],
            "pre_intervention_promotion_possible": True,
        },
    )
    assert severity == "critical"

    high = classify_incident_severity(
        _report_metrics(high_confidence_error_rate=0.2, structural_failure_rate=0.2),
        {"triggering_conditions": ["hce", "structural"], "pre_intervention_promotion_possible": False},
    )
    assert high == "high"

    none = classify_incident_severity(_report_metrics(), {"triggering_conditions": []})
    assert none == "none"


def test_decision_schema_validation():
    decision = evaluate_failure_controls(_report_metrics(), [_record("c1")])
    _validate_against_schema(decision)


def test_cli_behavior(tmp_path: Path, capsys):
    report_path = tmp_path / "failure_first_report.json"
    output_path = tmp_path / "failure_enforcement_decision.json"
    report = {
        "failure_first_metrics": _report_metrics(dangerous_promote_count=1, structural_failure_rate=0.2),
        "worst_cases": [_record("c1", dangerous_promote=True, promotion_recommendation="promote")],
        "dangerous_promotes": [_record("c1", dangerous_promote=True, promotion_recommendation="promote")],
        "false_confidence_zones": [_record("c2", high_confidence_error=True)],
        "passes_components_most_at_risk": [{"pass_type": "grounding", "failure_count": 4}],
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")

    exit_code = run_failure_enforcement_main(["--report-path", str(report_path), "--output", str(output_path)])
    assert exit_code == 0
    assert output_path.exists()

    output = capsys.readouterr().out
    assert "promotion_allowed:" in output
    assert "system_response:" in output
    assert "incident_severity:" in output
    assert "suppressed_component_count:" in output
    assert "top_triggering_conditions:" in output
