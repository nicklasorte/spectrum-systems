"""Tests for the full PRL pre-PR gate: integration across all PRL subsystems."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from spectrum_systems.modules.prl.failure_classifier import aggregate_gate_signal
from spectrum_systems.modules.prl.failure_parser import ParsedFailure, parse_log


class TestAggregateDecisionLogic:
    """Unit tests for the gate's signal aggregation."""

    def test_zero_failures_produces_passed_gate(self):
        assert aggregate_gate_signal([]) == "passed_gate"

    def test_failed_gate_failure_produces_failed_gate(self):
        signals = ["failed_gate"]
        assert aggregate_gate_signal(signals) == "failed_gate"

    def test_gate_hold_only_produces_gate_hold(self):
        assert aggregate_gate_signal(["gate_hold"]) == "gate_hold"

    def test_gate_warn_only_produces_gate_warn(self):
        assert aggregate_gate_signal(["gate_warn"]) == "gate_warn"

    def test_mixed_failed_gate_and_warn_produces_failed_gate(self):
        assert aggregate_gate_signal(["gate_warn", "failed_gate"]) == "failed_gate"

    def test_mixed_gate_hold_and_warn_produces_gate_hold(self):
        assert aggregate_gate_signal(["gate_hold", "gate_warn"]) == "gate_hold"


class TestGateRunFunction:
    """Integration tests for run_gate() with mocked subprocess calls."""

    def _import_run_gate(self):
        from scripts.run_pre_pr_reliability_gate import run_gate
        return run_gate

    def test_clean_run_produces_passed_gate(self):
        run_gate = self._import_run_gate()
        with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
            mock_check.return_value = (0, "")
            result = run_gate(
                run_id="run-test-clean",
                trace_id="trace-test-clean",
                skip_pytest=True,
            )
        assert result["artifact_type"] == "prl_gate_result"
        assert result["gate_recommendation"] == "passed_gate"
        assert result["gate_passed"] is True
        assert result["failure_count"] == 0

    def test_authority_violation_produces_failed_gate(self):
        run_gate = self._import_run_gate()
        with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
            mock_check.return_value = (1, "authority_shape_violation detected in foo.py")
            result = run_gate(
                run_id="run-test-block",
                trace_id="trace-test-block",
                skip_pytest=True,
            )
        assert result["gate_recommendation"] == "failed_gate"
        assert result["gate_passed"] is False
        assert result["failure_count"] > 0
        assert "authority_shape_violation" in result["failure_classes"]

    def test_unknown_failure_produces_gate_hold(self):
        run_gate = self._import_run_gate()
        with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
            mock_check.return_value = (1, "something completely unrecognized happened")
            result = run_gate(
                run_id="run-test-freeze",
                trace_id="trace-test-freeze",
                skip_pytest=True,
            )
        assert result["gate_recommendation"] == "gate_hold"
        assert result["gate_passed"] is False

    def test_pytest_selection_missing_produces_gate_warn(self):
        run_gate = self._import_run_gate()
        with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
            def side_effect(label, cmd, **kwargs):
                if "pytest" in " ".join(cmd):
                    return (1, "collected 0 items / no tests ran")
                return (0, "")
            mock_check.side_effect = side_effect
            result = run_gate(
                run_id="run-test-warn",
                trace_id="trace-test-warn",
                skip_pytest=False,
            )
        assert result["gate_recommendation"] == "gate_warn"
        assert result["gate_passed"] is False

    def test_real_assertion_failure_produces_gate_hold(self):
        # A real test failure must NOT be downgraded to gate_warn.
        run_gate = self._import_run_gate()
        with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
            def side_effect(label, cmd, **kwargs):
                if "pytest" in " ".join(cmd):
                    return (1, "FAILED tests/prl/test_foo.py::test_bar - AssertionError")
                return (0, "")
            mock_check.side_effect = side_effect
            result = run_gate(
                run_id="run-test-assert-fail",
                trace_id="trace-test-assert-fail",
                skip_pytest=False,
            )
        assert result["gate_recommendation"] != "gate_warn"
        assert result["gate_passed"] is False

    def test_gate_result_has_all_required_fields(self):
        run_gate = self._import_run_gate()
        with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
            mock_check.return_value = (0, "")
            result = run_gate(
                run_id="run-fields-test",
                trace_id="trace-fields-test",
                skip_pytest=True,
            )
        required_fields = {
            "artifact_type",
            "schema_version",
            "id",
            "timestamp",
            "run_id",
            "trace_id",
            "trace_refs",
            "gate_recommendation",
            "failure_count",
            "failure_classes",
            "failure_packet_refs",
            "repair_candidate_refs",
            "eval_candidate_refs",
            "blocking_reasons",
            "gate_passed",
        }
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_gate_result_id_pattern(self):
        run_gate = self._import_run_gate()
        with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
            mock_check.return_value = (0, "")
            result = run_gate(
                run_id="run-id-test",
                trace_id="trace-id-test",
                skip_pytest=True,
            )
        assert result["id"].startswith("prl-gate-")

    def test_blocking_reasons_populated_on_failed_gate(self):
        run_gate = self._import_run_gate()
        with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
            mock_check.return_value = (1, "system_registry_mismatch: canonical owner missing")
            result = run_gate(
                run_id="run-reasons-test",
                trace_id="trace-reasons-test",
                skip_pytest=True,
            )
        assert len(result["blocking_reasons"]) > 0

    def test_repair_and_eval_refs_populated_on_failure(self):
        run_gate = self._import_run_gate()
        with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
            mock_check.return_value = (1, "contract_schema_violation in artifact")
            result = run_gate(
                run_id="run-refs-test",
                trace_id="trace-refs-test",
                skip_pytest=True,
            )
        assert len(result["repair_candidate_refs"]) > 0
        assert len(result["eval_candidate_refs"]) > 0

    def test_trace_refs_present_in_gate_result(self):
        run_gate = self._import_run_gate()
        with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
            mock_check.return_value = (0, "")
            result = run_gate(
                run_id="run-trace-test",
                trace_id="trace-trace-test",
                skip_pytest=True,
            )
        assert "trace_refs" in result
        assert result["trace_refs"]["primary"] == "trace-trace-test"

    def test_deterministic_gate_id_same_inputs(self):
        run_gate = self._import_run_gate()
        with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
            mock_check.return_value = (0, "")
            r1 = run_gate(
                run_id="run-det-test",
                trace_id="trace-det-test",
                skip_pytest=True,
            )
            r2 = run_gate(
                run_id="run-det-test",
                trace_id="trace-det-test",
                skip_pytest=True,
            )
        assert r1["id"] == r2["id"]


class TestFullPipelineArtifactChain:
    """Verify that capture → packet → repair → eval → generation chain is coherent."""

    def test_pipeline_produces_linked_artifacts(self):
        from spectrum_systems.modules.prl.artifact_builder import (
            build_capture_record,
            build_failure_packet,
        )
        from spectrum_systems.modules.prl.eval_generator import (
            build_generation_record,
            generate_eval_case_candidate,
            advance_to_eval_case,
        )
        from spectrum_systems.modules.prl.failure_classifier import classify
        from spectrum_systems.modules.prl.repair_generator import generate_repair_candidate

        run_id = "run-chain-001"
        trace_id = "trace-chain-001"
        failure_class = "contract_schema_violation"

        parsed = ParsedFailure(
            failure_class=failure_class,
            raw_excerpt="ValidationError: additionalProperties violated",
            normalized_message="Contract schema validation failure",
            file_refs=("spectrum_systems/modules/foo.py",),
            line_number=10,
            exit_code=1,
        )
        classification = classify(parsed)

        capture = build_capture_record(
            parsed=parsed,
            classification=classification,
            source="pre_pr_gate",
            run_id=run_id,
            trace_id=trace_id,
        )
        assert capture["artifact_type"] == "pr_failure_capture_record"

        packet = build_failure_packet(
            capture_record=capture,
            classification=classification,
            run_id=run_id,
            trace_id=trace_id,
        )
        assert packet["capture_record_ref"] == f"pr_failure_capture_record:{capture['id']}"

        repair = generate_repair_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=run_id,
            trace_id=trace_id,
        )
        assert repair["failure_packet_ref"] == f"pre_pr_failure_packet:{packet['id']}"
        assert repair["auto_apply"] is False

        candidate = generate_eval_case_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=run_id,
            trace_id=trace_id,
        )
        assert candidate["failure_packet_ref"] == f"pre_pr_failure_packet:{packet['id']}"
        assert candidate["gate_eligible"] is True

        gated = advance_to_eval_case(
            candidate=candidate,
            classification=classification,
            run_id=run_id,
            trace_id=trace_id,
        )
        assert gated is not None
        assert gated["candidate_ref"] == f"eval_case_candidate:{candidate['id']}"

        gen_record = build_generation_record(
            failure_packet=packet,
            candidate=candidate,
            gated_eval=gated,
            run_id=run_id,
            trace_id=trace_id,
        )
        assert gen_record["candidate_id"] == candidate["id"]
        assert gen_record["gated_eval_id"] == gated["id"]
        assert gen_record["gate_status"] == "advanced"
