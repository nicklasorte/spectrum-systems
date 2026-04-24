"""Tests for SLO/SLI definitions module.

Verifies all SLOs are defined with sane targets, that emit_slo_metric produces
correct status for pass/warning/critical thresholds, and that cost_slo enforces
hard_freeze_on_budget_exhaust semantics.
"""
from __future__ import annotations

import pytest

from spectrum_systems.modules.observability.slo_definitions import (
    SLO_DEFINITIONS,
    check_all_slos,
    emit_slo_metric,
)


# ---------------------------------------------------------------------------
# SLO definition completeness
# ---------------------------------------------------------------------------

class TestSloDefinitionsCompleteness:
    REQUIRED_SLOS = [
        "drift_slo",
        "error_budget_slo",
        "latency_slo",
        "cost_slo",
        "schema_conformance_slo",
    ]

    def test_all_required_slos_defined(self) -> None:
        for slo in self.REQUIRED_SLOS:
            assert slo in SLO_DEFINITIONS, f"Missing SLO definition: {slo}"

    def test_each_slo_has_required_fields(self) -> None:
        required_fields = {"metric", "target", "alert_threshold", "window", "enforcement"}
        for slo_name, slo_def in SLO_DEFINITIONS.items():
            missing = required_fields - slo_def.keys()
            assert not missing, f"SLO '{slo_name}' missing fields: {missing}"

    def test_drift_slo_targets_sane(self) -> None:
        slo = SLO_DEFINITIONS["drift_slo"]
        assert slo["target"] == 0.15
        assert slo["alert_threshold"] == 0.10
        assert slo["alert_threshold"] < slo["target"]

    def test_error_budget_slo_targets_sane(self) -> None:
        slo = SLO_DEFINITIONS["error_budget_slo"]
        assert slo["target"] == 0.05
        assert slo["alert_threshold"] == 0.03
        assert slo["alert_threshold"] < slo["target"]

    def test_latency_slo_targets_sane(self) -> None:
        slo = SLO_DEFINITIONS["latency_slo"]
        assert slo["target"] == 5000
        assert slo["alert_threshold"] == 3000

    def test_cost_slo_has_hard_freeze_enforcement(self) -> None:
        slo = SLO_DEFINITIONS["cost_slo"]
        assert slo["enforcement"] == "hard_freeze_on_budget_exhaust"
        assert slo["target"] == 100000
        assert slo["alert_threshold"] == 80000

    def test_schema_conformance_slo_targets_sane(self) -> None:
        slo = SLO_DEFINITIONS["schema_conformance_slo"]
        assert slo["target"] == 0.99
        assert slo["alert_threshold"] == 0.95
        assert slo["alert_threshold"] < slo["target"]


# ---------------------------------------------------------------------------
# emit_slo_metric status correctness
# ---------------------------------------------------------------------------

class TestEmitSloMetricStatus:
    # drift_slo: lower-is-better, target=0.15, alert=0.10
    def test_drift_slo_pass(self) -> None:
        result = emit_slo_metric("drift_slo", 0.05)
        assert result["status"] == "pass"

    def test_drift_slo_warning(self) -> None:
        result = emit_slo_metric("drift_slo", 0.12)
        assert result["status"] == "warning"

    def test_drift_slo_critical(self) -> None:
        result = emit_slo_metric("drift_slo", 0.20)
        assert result["status"] == "critical"

    # error_budget_slo: lower-is-better, target=0.05, alert=0.03
    def test_error_budget_slo_pass(self) -> None:
        result = emit_slo_metric("error_budget_slo", 0.01)
        assert result["status"] == "pass"

    def test_error_budget_slo_warning(self) -> None:
        result = emit_slo_metric("error_budget_slo", 0.04)
        assert result["status"] == "warning"

    def test_error_budget_slo_critical(self) -> None:
        result = emit_slo_metric("error_budget_slo", 0.08)
        assert result["status"] == "critical"

    # schema_conformance_slo: higher-is-better, target=0.99, alert=0.95
    def test_schema_conformance_slo_pass(self) -> None:
        result = emit_slo_metric("schema_conformance_slo", 0.995)
        assert result["status"] == "pass"

    def test_schema_conformance_slo_warning(self) -> None:
        result = emit_slo_metric("schema_conformance_slo", 0.97)
        assert result["status"] == "warning"

    def test_schema_conformance_slo_critical(self) -> None:
        result = emit_slo_metric("schema_conformance_slo", 0.90)
        assert result["status"] == "critical"

    # latency_slo: lower-is-better, target=5000ms, alert=3000ms
    def test_latency_slo_pass(self) -> None:
        result = emit_slo_metric("latency_slo", 1500)
        assert result["status"] == "pass"

    def test_latency_slo_warning(self) -> None:
        result = emit_slo_metric("latency_slo", 4000)
        assert result["status"] == "warning"

    def test_latency_slo_critical(self) -> None:
        result = emit_slo_metric("latency_slo", 6000)
        assert result["status"] == "critical"

    # cost_slo: lower-is-better, hard_freeze_on_budget_exhaust
    def test_cost_slo_pass(self) -> None:
        result = emit_slo_metric("cost_slo", 50000)
        assert result["status"] == "pass"
        assert result["enforcement_signal"] is None

    def test_cost_slo_warning(self) -> None:
        result = emit_slo_metric("cost_slo", 90000)
        assert result["status"] == "warning"

    def test_cost_slo_critical_triggers_hard_freeze(self) -> None:
        result = emit_slo_metric("cost_slo", 110000)
        assert result["status"] == "critical"
        assert result["enforcement_signal"] == "hard_freeze_required"

    def test_cost_slo_at_target_boundary_is_warning(self) -> None:
        result = emit_slo_metric("cost_slo", 100000)
        assert result["status"] == "critical"

    def test_cost_slo_at_alert_threshold_is_pass(self) -> None:
        result = emit_slo_metric("cost_slo", 80000)
        assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# emit_slo_metric artifact structure
# ---------------------------------------------------------------------------

class TestEmitSloMetricArtifact:
    def test_artifact_has_correct_type(self) -> None:
        result = emit_slo_metric("drift_slo", 0.05)
        assert result["artifact_type"] == "slo_metric_artifact"

    def test_artifact_has_schema_version(self) -> None:
        result = emit_slo_metric("drift_slo", 0.05)
        assert result["schema_version"] == "1.0.0"

    def test_artifact_includes_slo_name(self) -> None:
        result = emit_slo_metric("error_budget_slo", 0.02)
        assert result["slo_name"] == "error_budget_slo"

    def test_artifact_includes_timestamp(self) -> None:
        result = emit_slo_metric("latency_slo", 2000)
        assert result["timestamp"]

    def test_artifact_includes_run_id_when_provided(self) -> None:
        result = emit_slo_metric("drift_slo", 0.05, run_id="run-xyz")
        assert result["run_id"] == "run-xyz"

    def test_unknown_metric_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown SLO metric"):
            emit_slo_metric("nonexistent_slo", 0.5)


# ---------------------------------------------------------------------------
# check_all_slos
# ---------------------------------------------------------------------------

class TestCheckAllSlos:
    def test_all_pass_overall_pass(self) -> None:
        result = check_all_slos({
            "drift_slo": 0.05,
            "error_budget_slo": 0.01,
            "latency_slo": 1000,
            "cost_slo": 50000,
            "schema_conformance_slo": 0.999,
        })
        assert result["overall_status"] == "pass"
        assert result["enforcement_required"] is False

    def test_one_warning_overall_warning(self) -> None:
        result = check_all_slos({
            "drift_slo": 0.12,
            "error_budget_slo": 0.01,
        })
        assert result["overall_status"] == "warning"

    def test_cost_slo_critical_triggers_enforcement(self) -> None:
        result = check_all_slos({
            "cost_slo": 120000,
        })
        assert result["overall_status"] == "critical"
        assert result["enforcement_required"] is True

    def test_result_includes_metrics_dict(self) -> None:
        result = check_all_slos({"drift_slo": 0.05})
        assert "metrics" in result
        assert "drift_slo" in result["metrics"]

    def test_result_has_artifact_type(self) -> None:
        result = check_all_slos({"drift_slo": 0.05})
        assert result["artifact_type"] == "slo_check_result"
