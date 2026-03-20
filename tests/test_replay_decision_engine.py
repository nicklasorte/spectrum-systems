"""Tests for BQ — Replay Decision Integrity Engine (replay_decision_engine.py).

Covers:
 1.  consistent replay — same decision reproduced → score=1.0, no drift
 2.  logic drift — decision_status changes between original and replay
 3.  input drift — TI SLI values differ between original and replay
 4.  missing decision — trace has no enforcement span → ReplayDecisionError
 5.  schema violations — build_analysis_artifact with invalid fields
 6.  compare_decisions returns drifted when status differs
 7.  compare_decisions returns consistent when decisions match
 8.  classify_drift returns None when consistent
 9.  classify_drift returns LOGIC_DRIFT when status changes
10.  classify_drift returns INPUT_DRIFT when TI SLI differs
11.  classify_drift returns ENVIRONMENT_DRIFT when only policy differs
12.  compute_reproducibility_score: 1.0 for consistent
13.  compute_reproducibility_score: 0.5 for indeterminate
14.  compute_reproducibility_score: 0.0 for logic drift
15.  validate_analysis returns empty list for valid artifact
16.  validate_analysis returns errors for missing required fields
17.  run_replay_decision_analysis raises on missing trace
18.  run_replay_decision_analysis raises on blocked replay
19.  execute_replay with run_decision_analysis=True attaches analysis key
20.  run_replay_decision_analysis produces schema-valid artifact for
    a trace with an enforcement span
"""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.replay_decision_engine import (  # noqa: E402
    CONSISTENCY_CONSISTENT,
    CONSISTENCY_DRIFTED,
    CONSISTENCY_INDETERMINATE,
    DRIFT_ENVIRONMENT,
    DRIFT_INPUT,
    DRIFT_LOGIC,
    DRIFT_NON_DETERMINISTIC,
    ReplayDecisionError,
    build_analysis_artifact,
    classify_drift,
    compare_decisions,
    compute_reproducibility_score,
    load_original_decision,
    recompute_decision_from_replay,
    run_replay_decision_analysis,
    validate_analysis,
)
from spectrum_systems.modules.runtime.replay_engine import (  # noqa: E402
    execute_replay,
)
from spectrum_systems.modules.runtime.trace_store import (  # noqa: E402
    persist_trace,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_store(tmp_path):
    return tmp_path / "traces"


def _make_trace(trace_id: str, *, n_spans: int = 1, with_enforcement_span: bool = False) -> Dict[str, Any]:
    """Build a minimal valid trace dict.

    Parameters
    ----------
    trace_id:
        Unique identifier for the trace.
    n_spans:
        Number of regular (non-enforcement) spans to include.
    with_enforcement_span:
        If True, append one additional slo_enforcement_decision span with a
        recorded enforcement_decision event (action=allow).
    """
    spans = []
    for i in range(n_spans):
        span_id = f"span-{i:03d}"
        span: Dict[str, Any] = {
            "span_id": span_id,
            "trace_id": trace_id,
            "parent_span_id": None if i == 0 else "span-000",
            "name": f"op_{i}",
            "status": "ok",
            "start_time": "2025-01-01T00:00:00+00:00",
            "end_time": "2025-01-01T00:00:01+00:00",
            "events": [],
        }
        spans.append(span)

    if with_enforcement_span:
        enf_span: Dict[str, Any] = {
            "span_id": "enf-span-001",
            "trace_id": trace_id,
            "parent_span_id": spans[0]["span_id"] if spans else None,
            "name": "slo_enforcement_decision",
            "status": "ok",
            "start_time": "2025-01-01T00:00:01+00:00",
            "end_time": "2025-01-01T00:00:02+00:00",
            "events": [
                {
                    "name": "enforcement_decision",
                    "data": {
                        "action": "allow",
                        "reason": "strict_valid_lineage",
                        "enforcement_policy": "permissive",
                        "recommended_action": "proceed",
                        "traceability_integrity_sli": 1.0,
                    },
                }
            ],
        }
        spans.append(enf_span)
        # If there were no regular spans, the enforcement span is the only one
        if len(spans) == 1:
            spans = [enf_span]

    return {
        "trace_id": trace_id,
        "root_span_id": spans[0]["span_id"] if spans else None,
        "spans": spans,
        "artifacts": [],
        "start_time": "2025-01-01T00:00:00+00:00",
        "end_time": "2025-01-01T00:00:02+00:00",
        "context": {"run_id": "run-001"},
        "schema_version": "1.0.0",
    }


def _make_decision_summary(
    status: str = "allow",
    reason: str = "strict_valid_lineage",
    policy: str = "permissive",
    action: str = "proceed",
    ti: float = 1.0,
) -> Dict[str, Any]:
    return {
        "decision_status": status,
        "decision_reason_code": reason,
        "enforcement_policy": policy,
        "recommended_action": action,
        "traceability_integrity_sli": ti,
    }


def _make_valid_analysis(
    trace_id: str = "trace-001",
    replay_id: str = "replay-001",
    consistency_status: str = "consistent",
) -> Dict[str, Any]:
    original = _make_decision_summary()
    replay = _make_decision_summary()
    consistency = {"status": consistency_status, "differences": []}
    return build_analysis_artifact(
        trace_id=trace_id,
        replay_result_id=replay_id,
        original_decision=original,
        replay_decision=replay,
        decision_consistency=consistency,
        drift_type=None,
        reproducibility_score=1.0,
        explanation="Decisions are consistent.",
    )


def _make_valid_replay_result(
    replay_id: str = "replay-001",
    trace_id: str = "trace-001",
    status: str = "success",
) -> Dict[str, Any]:
    return {
        "artifact_type": "replay_result",
        "schema_version": "1.0.0",
        "replay_id": replay_id,
        "source_trace_id": trace_id,
        "replayed_at": "2025-01-01T00:00:00+00:00",
        "status": status,
        "prerequisites_valid": True,
        "prerequisite_errors": [],
        "steps_executed": [],
        "output_comparison": {"compared": False, "matched": None, "differences": []},
        "determinism_notes": [],
        "context": {},
    }


# ---------------------------------------------------------------------------
# Test 1: consistent replay
# ---------------------------------------------------------------------------


class TestConsistentReplay:
    def test_consistent_produces_score_1(self, tmp_store):
        trace = _make_trace("trace-consistent", n_spans=1, with_enforcement_span=True)
        persist_trace(trace, base_dir=tmp_store)
        analysis = run_replay_decision_analysis("trace-consistent", base_dir=tmp_store)
        assert analysis["reproducibility_score"] == 1.0

    def test_consistent_no_drift_type(self, tmp_store):
        trace = _make_trace("trace-consistent-2", n_spans=1, with_enforcement_span=True)
        persist_trace(trace, base_dir=tmp_store)
        analysis = run_replay_decision_analysis("trace-consistent-2", base_dir=tmp_store)
        assert analysis["drift_type"] is None

    def test_consistent_status_value(self, tmp_store):
        trace = _make_trace("trace-consistent-3", n_spans=1, with_enforcement_span=True)
        persist_trace(trace, base_dir=tmp_store)
        analysis = run_replay_decision_analysis("trace-consistent-3", base_dir=tmp_store)
        assert analysis["decision_consistency"]["status"] == CONSISTENCY_CONSISTENT

    def test_consistent_empty_differences(self, tmp_store):
        trace = _make_trace("trace-consistent-4", n_spans=1, with_enforcement_span=True)
        persist_trace(trace, base_dir=tmp_store)
        analysis = run_replay_decision_analysis("trace-consistent-4", base_dir=tmp_store)
        assert analysis["decision_consistency"]["differences"] == []


# ---------------------------------------------------------------------------
# Test 2: logic drift
# ---------------------------------------------------------------------------


class TestLogicDrift:
    def test_logic_drift_detected(self):
        orig = _make_decision_summary(status="allow")
        replay = _make_decision_summary(status="fail")
        consistency = compare_decisions(orig, replay)
        assert consistency["status"] == CONSISTENCY_DRIFTED

    def test_logic_drift_classified(self):
        orig = _make_decision_summary(status="allow")
        replay = _make_decision_summary(status="fail")
        drift = classify_drift(orig, replay, None)
        assert drift == DRIFT_LOGIC

    def test_logic_drift_score_zero(self):
        consistency = {"status": CONSISTENCY_DRIFTED, "differences": []}
        score = compute_reproducibility_score(consistency, DRIFT_LOGIC)
        assert score == 0.0

    def test_logic_drift_differences_include_status(self):
        orig = _make_decision_summary(status="allow")
        replay = _make_decision_summary(status="fail")
        consistency = compare_decisions(orig, replay)
        fields = [d["field"] for d in consistency["differences"]]
        assert "decision_status" in fields


# ---------------------------------------------------------------------------
# Test 3: input drift
# ---------------------------------------------------------------------------


class TestInputDrift:
    def test_input_drift_classified_when_ti_differs(self):
        orig = _make_decision_summary(ti=1.0)
        replay = _make_decision_summary(ti=0.0)
        # Force TI into the summaries
        orig["traceability_integrity_sli"] = 1.0
        replay["traceability_integrity_sli"] = 0.0
        drift = classify_drift(orig, replay, None)
        assert drift == DRIFT_INPUT

    def test_input_drift_score(self):
        consistency = {"status": CONSISTENCY_DRIFTED, "differences": []}
        score = compute_reproducibility_score(consistency, DRIFT_INPUT)
        assert score == 0.2


# ---------------------------------------------------------------------------
# Test 4: missing decision
# ---------------------------------------------------------------------------


class TestMissingDecision:
    def test_load_original_decision_raises_when_no_trace(self, tmp_store):
        with pytest.raises(ReplayDecisionError, match="no persisted trace"):
            load_original_decision("nonexistent-trace", base_dir=tmp_store)

    def test_load_original_decision_raises_when_no_enforcement_span(self, tmp_store):
        trace = _make_trace("trace-no-enf", n_spans=2, with_enforcement_span=False)
        persist_trace(trace, base_dir=tmp_store)
        with pytest.raises(ReplayDecisionError, match="no SLO enforcement decision"):
            load_original_decision("trace-no-enf", base_dir=tmp_store)

    def test_run_analysis_raises_when_trace_not_found(self, tmp_store):
        with pytest.raises(ReplayDecisionError):
            run_replay_decision_analysis("does-not-exist", base_dir=tmp_store)

    def test_load_original_decision_raises_for_empty_trace_id(self, tmp_store):
        with pytest.raises(ReplayDecisionError):
            load_original_decision("", base_dir=tmp_store)


# ---------------------------------------------------------------------------
# Test 5: schema violations
# ---------------------------------------------------------------------------


class TestSchemaViolations:
    def test_validate_analysis_empty_for_valid_artifact(self):
        artifact = _make_valid_analysis()
        errors = validate_analysis(artifact)
        assert errors == []

    def test_validate_analysis_errors_for_missing_analysis_id(self):
        artifact = _make_valid_analysis()
        del artifact["analysis_id"]
        errors = validate_analysis(artifact)
        assert len(errors) > 0

    def test_validate_analysis_errors_for_missing_trace_id(self):
        artifact = _make_valid_analysis()
        del artifact["trace_id"]
        errors = validate_analysis(artifact)
        assert len(errors) > 0

    def test_validate_analysis_errors_for_invalid_score(self):
        artifact = _make_valid_analysis()
        artifact["reproducibility_score"] = 1.5  # out of [0, 1]
        errors = validate_analysis(artifact)
        assert len(errors) > 0

    def test_validate_analysis_errors_for_invalid_consistency_status(self):
        artifact = _make_valid_analysis()
        artifact["decision_consistency"]["status"] = "invalid_status"
        errors = validate_analysis(artifact)
        assert len(errors) > 0

    def test_validate_analysis_errors_for_invalid_drift_type(self):
        artifact = _make_valid_analysis()
        artifact["drift_type"] = "UNKNOWN_DRIFT"
        errors = validate_analysis(artifact)
        assert len(errors) > 0

    def test_validate_analysis_rejects_extra_property(self):
        artifact = _make_valid_analysis()
        artifact["extra_field"] = "not_allowed"
        errors = validate_analysis(artifact)
        assert len(errors) > 0

    def test_validate_analysis_non_dict_input(self):
        errors = validate_analysis("not a dict")  # type: ignore[arg-type]
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# Test 6: compare_decisions returns drifted when status differs
# ---------------------------------------------------------------------------


class TestCompareDecisionsDrifted:
    def test_different_status_is_drifted(self):
        orig = _make_decision_summary(status="allow")
        replay = _make_decision_summary(status="fail")
        result = compare_decisions(orig, replay)
        assert result["status"] == CONSISTENCY_DRIFTED

    def test_different_reason_code_is_drifted(self):
        orig = _make_decision_summary(reason="strict_valid_lineage")
        replay = _make_decision_summary(reason="strict_invalid_lineage")
        result = compare_decisions(orig, replay)
        assert result["status"] == CONSISTENCY_DRIFTED

    def test_differences_list_populated(self):
        orig = _make_decision_summary(status="allow")
        replay = _make_decision_summary(status="fail")
        result = compare_decisions(orig, replay)
        assert len(result["differences"]) > 0

    def test_difference_records_correct_values(self):
        orig = _make_decision_summary(status="allow")
        replay = _make_decision_summary(status="fail")
        result = compare_decisions(orig, replay)
        diff = next(d for d in result["differences"] if d["field"] == "decision_status")
        assert diff["original_value"] == "allow"
        assert diff["replay_value"] == "fail"


# ---------------------------------------------------------------------------
# Test 7: compare_decisions returns consistent when decisions match
# ---------------------------------------------------------------------------


class TestCompareDecisionsConsistent:
    def test_identical_decisions_are_consistent(self):
        orig = _make_decision_summary()
        replay = _make_decision_summary()
        result = compare_decisions(orig, replay)
        assert result["status"] == CONSISTENCY_CONSISTENT

    def test_consistent_has_empty_differences(self):
        orig = _make_decision_summary()
        replay = _make_decision_summary()
        result = compare_decisions(orig, replay)
        assert result["differences"] == []

    def test_both_none_optional_fields_are_consistent(self):
        orig = {"decision_status": "allow", "decision_reason_code": "reason_a", "enforcement_policy": None}
        replay = {"decision_status": "allow", "decision_reason_code": "reason_a", "enforcement_policy": None}
        result = compare_decisions(orig, replay)
        assert result["status"] == CONSISTENCY_CONSISTENT

    def test_non_dict_inputs_are_indeterminate(self):
        result = compare_decisions("not a dict", None)  # type: ignore[arg-type]
        assert result["status"] == CONSISTENCY_INDETERMINATE


# ---------------------------------------------------------------------------
# Test 8: classify_drift returns None when consistent
# ---------------------------------------------------------------------------


class TestClassifyDriftConsistent:
    def test_no_drift_when_consistent(self):
        orig = _make_decision_summary()
        replay = _make_decision_summary()
        drift = classify_drift(orig, replay, None)
        assert drift is None

    def test_no_drift_with_context(self):
        orig = _make_decision_summary()
        replay = _make_decision_summary()
        drift = classify_drift(orig, replay, {"triggered_by": "test"})
        assert drift is None


# ---------------------------------------------------------------------------
# Test 9: classify_drift returns LOGIC_DRIFT when status changes
# ---------------------------------------------------------------------------


class TestClassifyDriftLogic:
    def test_logic_drift_when_status_changes(self):
        orig = _make_decision_summary(status="allow")
        replay = _make_decision_summary(status="fail")
        drift = classify_drift(orig, replay, None)
        assert drift == DRIFT_LOGIC


# ---------------------------------------------------------------------------
# Test 10: classify_drift returns INPUT_DRIFT when TI SLI differs
# ---------------------------------------------------------------------------


class TestClassifyDriftInput:
    def test_input_drift_when_ti_differs(self):
        orig = _make_decision_summary(status="allow", ti=1.0)
        replay = _make_decision_summary(status="fail", ti=0.0)
        orig["traceability_integrity_sli"] = 1.0
        replay["traceability_integrity_sli"] = 0.0
        drift = classify_drift(orig, replay, None)
        assert drift == DRIFT_INPUT


# ---------------------------------------------------------------------------
# Test 11: classify_drift returns ENVIRONMENT_DRIFT when only policy differs
# ---------------------------------------------------------------------------


class TestClassifyDriftEnvironment:
    def test_environment_drift_when_only_policy_differs(self):
        orig = _make_decision_summary(policy="permissive")
        replay = _make_decision_summary(policy="decision_grade")
        drift = classify_drift(orig, replay, None)
        assert drift == DRIFT_ENVIRONMENT


# ---------------------------------------------------------------------------
# Test 12–14: compute_reproducibility_score
# ---------------------------------------------------------------------------


class TestComputeReproducibilityScore:
    def test_consistent_yields_1_0(self):
        consistency = {"status": CONSISTENCY_CONSISTENT, "differences": []}
        score = compute_reproducibility_score(consistency, None)
        assert score == 1.0

    def test_indeterminate_yields_0_5(self):
        consistency = {"status": CONSISTENCY_INDETERMINATE, "differences": []}
        score = compute_reproducibility_score(consistency, None)
        assert score == 0.5

    def test_logic_drift_yields_0_0(self):
        consistency = {"status": CONSISTENCY_DRIFTED, "differences": []}
        score = compute_reproducibility_score(consistency, DRIFT_LOGIC)
        assert score == 0.0

    def test_non_deterministic_drift_yields_0_5(self):
        consistency = {"status": CONSISTENCY_DRIFTED, "differences": []}
        score = compute_reproducibility_score(consistency, DRIFT_NON_DETERMINISTIC)
        assert score == 0.5

    def test_environment_drift_yields_0_3(self):
        consistency = {"status": CONSISTENCY_DRIFTED, "differences": []}
        score = compute_reproducibility_score(consistency, DRIFT_ENVIRONMENT)
        assert score == 0.3

    def test_input_drift_yields_0_2(self):
        consistency = {"status": CONSISTENCY_DRIFTED, "differences": []}
        score = compute_reproducibility_score(consistency, DRIFT_INPUT)
        assert score == 0.2

    def test_unknown_drift_type_yields_0_1(self):
        consistency = {"status": CONSISTENCY_DRIFTED, "differences": []}
        score = compute_reproducibility_score(consistency, "UNKNOWN_DRIFT")
        assert score == 0.1


# ---------------------------------------------------------------------------
# Test 15: validate_analysis returns empty list for valid artifact
# ---------------------------------------------------------------------------


class TestValidateAnalysisValid:
    def test_valid_consistent_artifact(self):
        artifact = _make_valid_analysis(consistency_status="consistent")
        errors = validate_analysis(artifact)
        assert errors == []

    def test_valid_drifted_artifact(self):
        original = _make_decision_summary()
        replay = _make_decision_summary(status="fail")
        consistency = {
            "status": "drifted",
            "differences": [
                {
                    "field": "decision_status",
                    "original_value": "allow",
                    "replay_value": "fail",
                }
            ],
        }
        artifact = build_analysis_artifact(
            trace_id="trace-001",
            replay_result_id="replay-001",
            original_decision=original,
            replay_decision=replay,
            decision_consistency=consistency,
            drift_type=DRIFT_LOGIC,
            reproducibility_score=0.0,
            explanation="Logic drift detected.",
        )
        errors = validate_analysis(artifact)
        assert errors == []

    def test_valid_artifact_with_all_drift_types(self):
        for drift_type in [DRIFT_INPUT, DRIFT_LOGIC, DRIFT_ENVIRONMENT, DRIFT_NON_DETERMINISTIC]:
            original = _make_decision_summary()
            replay = _make_decision_summary(status="fail")
            consistency = {
                "status": "drifted",
                "differences": [{"field": "decision_status", "original_value": "allow", "replay_value": "fail"}],
            }
            artifact = build_analysis_artifact(
                trace_id="trace-001",
                replay_result_id="replay-001",
                original_decision=original,
                replay_decision=replay,
                decision_consistency=consistency,
                drift_type=drift_type,
                reproducibility_score=0.1,
                explanation="Drift.",
            )
            errors = validate_analysis(artifact)
            assert errors == [], f"Unexpected errors for drift_type={drift_type}: {errors}"


# ---------------------------------------------------------------------------
# Test 16: validate_analysis returns errors for missing required fields
# ---------------------------------------------------------------------------


class TestValidateAnalysisInvalid:
    @pytest.mark.parametrize("missing_field", [
        "analysis_id",
        "trace_id",
        "replay_result_id",
        "original_decision",
        "replay_decision",
        "decision_consistency",
        "reproducibility_score",
        "explanation",
        "created_at",
    ])
    def test_missing_required_field_produces_error(self, missing_field):
        artifact = _make_valid_analysis()
        del artifact[missing_field]
        errors = validate_analysis(artifact)
        assert len(errors) > 0, f"Expected errors when '{missing_field}' is missing"


# ---------------------------------------------------------------------------
# Test 17: run_replay_decision_analysis raises on missing trace
# ---------------------------------------------------------------------------


class TestRunAnalysisMissingTrace:
    def test_raises_replay_decision_error_for_missing_trace(self, tmp_store):
        with pytest.raises(ReplayDecisionError):
            run_replay_decision_analysis("missing-trace-xyz", base_dir=tmp_store)


# ---------------------------------------------------------------------------
# Test 18: run_replay_decision_analysis raises on blocked replay
# ---------------------------------------------------------------------------


class TestRunAnalysisBlockedReplay:
    def test_recompute_raises_for_blocked_result(self):
        blocked = _make_valid_replay_result(status="blocked")
        blocked["prerequisites_valid"] = False
        with pytest.raises(ReplayDecisionError, match="blocked"):
            recompute_decision_from_replay(blocked)

    def test_recompute_raises_for_failed_result(self):
        failed = _make_valid_replay_result(status="failed")
        with pytest.raises(ReplayDecisionError, match="failed"):
            recompute_decision_from_replay(failed)

    def test_recompute_raises_for_non_dict(self):
        with pytest.raises(ReplayDecisionError):
            recompute_decision_from_replay("not a dict")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test 19: execute_replay with run_decision_analysis=True
# ---------------------------------------------------------------------------


class TestExecuteReplayWithDecisionAnalysis:
    def test_decision_analysis_key_present_when_enabled(self, tmp_store):
        trace = _make_trace("trace-da-enabled", n_spans=1, with_enforcement_span=True)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay(
            "trace-da-enabled",
            base_dir=tmp_store,
            run_decision_analysis=True,
        )
        assert "decision_analysis" in result

    def test_decision_analysis_key_absent_by_default(self, tmp_store):
        trace = _make_trace("trace-da-absent", n_spans=1)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay("trace-da-absent", base_dir=tmp_store)
        assert "decision_analysis" not in result

    def test_decision_analysis_none_when_no_enforcement_span(self, tmp_store):
        # Trace has no enforcement span → decision analysis should set None (not raise)
        trace = _make_trace("trace-da-no-enf", n_spans=1, with_enforcement_span=False)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay(
            "trace-da-no-enf",
            base_dir=tmp_store,
            run_decision_analysis=True,
        )
        assert "decision_analysis" in result
        assert result["decision_analysis"] is None

    def test_decision_analysis_is_schema_valid_when_enforcement_present(self, tmp_store):
        trace = _make_trace("trace-da-valid", n_spans=1, with_enforcement_span=True)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay(
            "trace-da-valid",
            base_dir=tmp_store,
            run_decision_analysis=True,
        )
        analysis = result["decision_analysis"]
        assert analysis is not None
        errors = validate_analysis(analysis)
        assert errors == []


# ---------------------------------------------------------------------------
# Test 20: run_replay_decision_analysis produces schema-valid artifact
# ---------------------------------------------------------------------------


class TestRunAnalysisSchemaValid:
    def test_schema_valid_artifact_for_enforcement_trace(self, tmp_store):
        trace = _make_trace("trace-full-valid", n_spans=2, with_enforcement_span=True)
        persist_trace(trace, base_dir=tmp_store)
        analysis = run_replay_decision_analysis("trace-full-valid", base_dir=tmp_store)
        errors = validate_analysis(analysis)
        assert errors == [], f"Schema errors: {errors}"

    def test_artifact_has_trace_id(self, tmp_store):
        trace = _make_trace("trace-has-id", n_spans=1, with_enforcement_span=True)
        persist_trace(trace, base_dir=tmp_store)
        analysis = run_replay_decision_analysis("trace-has-id", base_dir=tmp_store)
        assert analysis["trace_id"] == "trace-has-id"

    def test_artifact_has_analysis_id(self, tmp_store):
        trace = _make_trace("trace-analysis-id", n_spans=1, with_enforcement_span=True)
        persist_trace(trace, base_dir=tmp_store)
        analysis = run_replay_decision_analysis("trace-analysis-id", base_dir=tmp_store)
        assert isinstance(analysis["analysis_id"], str)
        assert len(analysis["analysis_id"]) > 0

    def test_artifact_has_valid_score_range(self, tmp_store):
        trace = _make_trace("trace-score-range", n_spans=1, with_enforcement_span=True)
        persist_trace(trace, base_dir=tmp_store)
        analysis = run_replay_decision_analysis("trace-score-range", base_dir=tmp_store)
        score = analysis["reproducibility_score"]
        assert 0.0 <= score <= 1.0

    def test_artifact_explanation_is_non_empty(self, tmp_store):
        trace = _make_trace("trace-explanation", n_spans=1, with_enforcement_span=True)
        persist_trace(trace, base_dir=tmp_store)
        analysis = run_replay_decision_analysis("trace-explanation", base_dir=tmp_store)
        assert isinstance(analysis["explanation"], str)
        assert len(analysis["explanation"]) > 0

    def test_artifact_original_decision_matches_trace(self, tmp_store):
        trace = _make_trace("trace-orig-match", n_spans=1, with_enforcement_span=True)
        persist_trace(trace, base_dir=tmp_store)
        analysis = run_replay_decision_analysis("trace-orig-match", base_dir=tmp_store)
        # The original decision should reflect the enforcement span event (action=allow)
        assert analysis["original_decision"]["decision_status"] == "allow"


# ---------------------------------------------------------------------------
# Test 21: unknown replay status fails closed (never allows)
# ---------------------------------------------------------------------------


class TestUnknownReplayStatus:
    """Unknown or missing statuses must never silently map to 'allow'."""

    def test_unknown_overall_status_raises(self):
        result = _make_valid_replay_result(status="unknown_status_xyz")
        with pytest.raises(ReplayDecisionError, match="unknown replay status"):
            recompute_decision_from_replay(result)

    def test_empty_overall_status_raises(self):
        result = _make_valid_replay_result(status="")
        with pytest.raises(ReplayDecisionError, match="unknown replay status"):
            recompute_decision_from_replay(result)

    def test_whitespace_only_status_raises(self):
        result = _make_valid_replay_result(status="   ")
        with pytest.raises(ReplayDecisionError, match="unknown replay status"):
            recompute_decision_from_replay(result)

    def test_none_overall_status_raises(self):
        result = _make_valid_replay_result(status="success")
        result["status"] = None
        with pytest.raises(ReplayDecisionError, match="unknown replay status"):
            recompute_decision_from_replay(result)

    def test_unknown_step_status_raises(self):
        result = _make_valid_replay_result(status="success")
        result["steps_executed"] = [
            {
                "span_name": "slo_enforcement_decision",
                "status": "UNKNOWN_STEP_STATUS_XYZ",
            }
        ]
        with pytest.raises(ReplayDecisionError, match="unknown enforcement step status"):
            recompute_decision_from_replay(result)

    def test_missing_step_status_field_raises(self):
        result = _make_valid_replay_result(status="success")
        result["steps_executed"] = [
            {
                "span_name": "slo_enforcement_decision",
                # no 'status' key
            }
        ]
        with pytest.raises(ReplayDecisionError, match="no status field"):
            recompute_decision_from_replay(result)

    def test_unknown_status_does_not_produce_allow(self):
        """Verify fail-closed: unknown status must never silently become 'allow'."""
        result = _make_valid_replay_result(status="mystery_status")
        raised = False
        try:
            decision = recompute_decision_from_replay(result)
            # If it somehow doesn't raise, the decision_status must not be "allow"
            assert decision.get("decision_status") != "allow", (
                "Unknown replay status was silently mapped to 'allow' — fail-open bug."
            )
        except ReplayDecisionError:
            raised = True
        assert raised, "Expected ReplayDecisionError for unknown replay status"


# ---------------------------------------------------------------------------
# Test 22: replay execution failure → indeterminate analysis artifact
# ---------------------------------------------------------------------------


class TestReplayExecutionFailureIndeterminate:
    """A failed replay execution must produce an indeterminate artifact,
    not raise an unhandled exception from the analysis pipeline."""

    def test_failed_replay_result_produces_indeterminate(self, tmp_store):
        from unittest.mock import patch

        trace = _make_trace("trace-failed-replay", n_spans=1, with_enforcement_span=True)
        persist_trace(trace, base_dir=tmp_store)
        failed_result = _make_valid_replay_result(
            replay_id="replay-failed-001",
            trace_id="trace-failed-replay",
            status="failed",
        )
        with patch(
            "spectrum_systems.modules.runtime.replay_decision_engine.execute_replay",
            return_value=failed_result,
        ):
            analysis = run_replay_decision_analysis(
                "trace-failed-replay", base_dir=tmp_store
            )
        assert analysis["decision_consistency"]["status"] == CONSISTENCY_INDETERMINATE

    def test_failed_replay_result_score_bounded(self, tmp_store):
        from unittest.mock import patch

        trace = _make_trace("trace-failed-score", n_spans=1, with_enforcement_span=True)
        persist_trace(trace, base_dir=tmp_store)
        failed_result = _make_valid_replay_result(
            replay_id="replay-failed-002",
            trace_id="trace-failed-score",
            status="failed",
        )
        with patch(
            "spectrum_systems.modules.runtime.replay_decision_engine.execute_replay",
            return_value=failed_result,
        ):
            analysis = run_replay_decision_analysis(
                "trace-failed-score", base_dir=tmp_store
            )
        score = analysis["reproducibility_score"]
        # Indeterminate score must not imply success (must be < 1.0)
        assert score < 1.0
        assert 0.0 <= score <= 0.5

    def test_failed_replay_artifact_is_schema_valid(self, tmp_store):
        from unittest.mock import patch

        trace = _make_trace("trace-failed-schema", n_spans=1, with_enforcement_span=True)
        persist_trace(trace, base_dir=tmp_store)
        failed_result = _make_valid_replay_result(
            replay_id="replay-failed-003",
            trace_id="trace-failed-schema",
            status="failed",
        )
        with patch(
            "spectrum_systems.modules.runtime.replay_decision_engine.execute_replay",
            return_value=failed_result,
        ):
            analysis = run_replay_decision_analysis(
                "trace-failed-schema", base_dir=tmp_store
            )
        errors = validate_analysis(analysis)
        assert errors == [], f"Schema errors for indeterminate artifact: {errors}"

    def test_failed_replay_explanation_contains_cause(self, tmp_store):
        from unittest.mock import patch

        trace = _make_trace(
            "trace-failed-expl", n_spans=1, with_enforcement_span=True
        )
        persist_trace(trace, base_dir=tmp_store)
        failed_result = _make_valid_replay_result(
            replay_id="replay-failed-004",
            trace_id="trace-failed-expl",
            status="failed",
        )
        with patch(
            "spectrum_systems.modules.runtime.replay_decision_engine.execute_replay",
            return_value=failed_result,
        ):
            analysis = run_replay_decision_analysis(
                "trace-failed-expl", base_dir=tmp_store
            )
        # Explanation must mention indeterminate and include a cause
        explanation = analysis["explanation"]
        assert "indeterminate" in explanation.lower()

    def test_failed_replay_drift_type_is_null(self, tmp_store):
        from unittest.mock import patch

        trace = _make_trace(
            "trace-failed-drift", n_spans=1, with_enforcement_span=True
        )
        persist_trace(trace, base_dir=tmp_store)
        failed_result = _make_valid_replay_result(
            replay_id="replay-failed-005",
            trace_id="trace-failed-drift",
            status="failed",
        )
        with patch(
            "spectrum_systems.modules.runtime.replay_decision_engine.execute_replay",
            return_value=failed_result,
        ):
            analysis = run_replay_decision_analysis(
                "trace-failed-drift", base_dir=tmp_store
            )
        assert analysis["drift_type"] is None


# ---------------------------------------------------------------------------
# Test 23: schema-invalid replay result → failure
# ---------------------------------------------------------------------------


class TestSchemaInvalidReplayResult:
    """A replay result without required fields must not silently allow."""

    def test_missing_status_field_raises(self):
        result = _make_valid_replay_result(status="success")
        del result["status"]
        with pytest.raises(ReplayDecisionError):
            recompute_decision_from_replay(result)

    def test_missing_replay_id_does_not_silently_allow(self):
        result = _make_valid_replay_result(status="success")
        del result["replay_id"]
        # Pipeline should still work (replay_id is optional for recompute, used elsewhere)
        # but status-derived decision must not be "allow" if status is missing/unknown
        result["status"] = "unknown_missing"
        with pytest.raises(ReplayDecisionError):
            recompute_decision_from_replay(result)


# ---------------------------------------------------------------------------
# Test 24: CLI exit codes (consistent→0, drifted→1, indeterminate→2)
# ---------------------------------------------------------------------------


class TestCLIExitCodes:
    """Verify that the CLI helper maps consistency status to the correct exit code."""

    def _import_cli(self):
        import importlib.util
        from pathlib import Path

        cli_path = Path(__file__).resolve().parents[1] / "scripts" / "run_replay_decision_analysis.py"
        spec = importlib.util.spec_from_file_location("run_replay_decision_analysis_cli", cli_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_consistent_exit_code_is_zero(self):
        cli = self._import_cli()
        analysis = _make_valid_analysis(consistency_status="consistent")
        code = cli._consistency_exit_code(analysis)
        assert code == 0

    def test_drifted_exit_code_is_one(self):
        cli = self._import_cli()
        analysis = _make_valid_analysis(consistency_status="drifted")
        code = cli._consistency_exit_code(analysis)
        assert code == 1

    def test_indeterminate_exit_code_is_two(self):
        cli = self._import_cli()
        analysis = _make_valid_analysis(consistency_status="indeterminate")
        code = cli._consistency_exit_code(analysis)
        assert code == 2

    def test_unknown_status_exit_code_is_two(self):
        """Any unrecognized status must produce exit code 2 (fail-closed)."""
        cli = self._import_cli()
        analysis = _make_valid_analysis(consistency_status="consistent")
        analysis["decision_consistency"]["status"] = "unrecognized_status"
        code = cli._consistency_exit_code(analysis)
        assert code == 2

    def test_missing_consistency_exit_code_is_two(self):
        """Missing decision_consistency must produce exit code 2 (fail-closed)."""
        cli = self._import_cli()
        analysis = _make_valid_analysis()
        del analysis["decision_consistency"]
        code = cli._consistency_exit_code(analysis)
        assert code == 2


# ---------------------------------------------------------------------------
# Test 25: drift detected but classification could not be completed
# ---------------------------------------------------------------------------


class TestDriftDetectedClassificationSkipped:
    """When drift is detected but classify_drift returns None (e.g. mocked edge
    case), the pipeline must not crash and must log a warning."""

    def test_pipeline_tolerates_none_drift_type_with_drifted_consistency(self, tmp_store):
        from unittest.mock import patch

        trace = _make_trace("trace-drift-none", n_spans=1, with_enforcement_span=True)
        persist_trace(trace, base_dir=tmp_store)

        orig = _make_decision_summary(status="allow")
        replay_d = _make_decision_summary(status="fail")
        drifted_consistency = {
            "status": CONSISTENCY_DRIFTED,
            "differences": [
                {
                    "field": "decision_status",
                    "original_value": "allow",
                    "replay_value": "fail",
                }
            ],
        }

        with patch(
            "spectrum_systems.modules.runtime.replay_decision_engine.compare_decisions",
            return_value=drifted_consistency,
        ), patch(
            "spectrum_systems.modules.runtime.replay_decision_engine.classify_drift",
            return_value=None,
        ):
            analysis = run_replay_decision_analysis("trace-drift-none", base_dir=tmp_store)

        # Pipeline must complete and return a schema-valid artifact
        errors = validate_analysis(analysis)
        assert errors == [], f"Schema errors: {errors}"
        assert analysis["decision_consistency"]["status"] == CONSISTENCY_DRIFTED
        # drift_type is None — score uses unknown-drift fallback (0.1)
        assert analysis["drift_type"] is None
