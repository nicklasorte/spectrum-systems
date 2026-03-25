"""Tests for BAG deterministic control replay engine."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402
from spectrum_systems.modules.runtime.control_loop import run_control_loop  # noqa: E402
from spectrum_systems.modules.runtime.control_loop import ControlLoopError  # noqa: E402
from spectrum_systems.modules.runtime.enforcement_engine import (  # noqa: E402
    EnforcementError,
    enforce_control_decision,
)
from spectrum_systems.modules.runtime.replay_engine import (  # noqa: E402
    ReplayEngineError,
    ReplayPrerequisiteError,
    execute_replay,
    replay_run,
    run_replay,
    validate_replay_result_legacy,
    validate_replay_result,
)
from spectrum_systems.modules.runtime.trace_store import persist_trace  # noqa: E402


def _artifact() -> dict:
    return {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": "44444444-4444-4444-8444-444444444444",
        "eval_run_id": "eval-run-20260322T000000Z",
        "pass_rate": 0.99,
        "failure_rate": 0.01,
        "drift_rate": 0.01,
        "reproducibility_score": 0.99,
        "system_status": "healthy",
    }


def _trace_context() -> dict:
    return {
        "trace_id": "44444444-4444-4444-8444-444444444444",
        "execution_id": "exec-001",
        "stage": "runtime_gate",
        "runtime_environment": "test",
    }


def _originals(artifact: dict | None = None, trace_context: dict | None = None) -> tuple[dict, dict]:
    payload = copy.deepcopy(artifact or _artifact())
    context = copy.deepcopy(trace_context or _trace_context())
    decision = run_control_loop(payload, context)["evaluation_control_decision"]
    enforcement = enforce_control_decision(decision)
    return decision, enforcement


def test_matching_replay_returns_match_and_no_drift() -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    result = run_replay(artifact, original_decision, original_enforcement, _trace_context())

    assert result["consistency_status"] == "match"
    assert result["drift_detected"] is False
    assert result["failure_reason"] is None
    assert "drift_result" in result
    assert result["drift_result"]["drift_type"] == "none"
    assert result["drift_result"]["drift_detected"] is False

def test_matching_replay_round_trip_contract_validation() -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    result = run_replay(artifact, original_decision, original_enforcement, _trace_context())

    validate_artifact(result, "replay_result")


def test_mismatched_replay_returns_mismatch_and_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    def _force_mismatch(_decision: dict) -> dict:
        return {
            "artifact_type": "enforcement_result",
            "schema_version": "1.1.0",
            "enforcement_result_id": "ENF-MISMATCH-001",
            "timestamp": "2026-03-22T00:00:00Z",
            "trace_id": original_enforcement["trace_id"],
            "run_id": original_enforcement["run_id"],
            "input_decision_reference": original_enforcement["input_decision_reference"],
            "enforcement_action": "deny_execution",
            "final_status": "deny",
            "rationale_code": "deny_reliability_breach",
            "fail_closed": True,
            "enforcement_path": "baf_single_path",
            "provenance": {
                "source_artifact_type": "evaluation_control_decision",
                "source_artifact_id": original_enforcement["input_decision_reference"],
            },
        }

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.enforcement_engine.enforce_control_decision",
        _force_mismatch,
    )

    result = run_replay(artifact, original_decision, original_enforcement, _trace_context())
    assert result["consistency_status"] == "mismatch"
    assert result["drift_detected"] is True
    assert result["failure_reason"] is None
    assert "drift_result" in result
    assert result["drift_result"]["drift_type"] in {"status_mismatch", "action_mismatch"}
    assert result["drift_result"]["drift_detected"] is True


def test_invalid_original_decision_fails_closed() -> None:
    artifact = _artifact()
    _, original_enforcement = _originals(artifact)
    with pytest.raises(ReplayEngineError):
        run_replay(artifact, {"artifact_type": "evaluation_control_decision"}, original_enforcement, _trace_context())


def test_invalid_original_enforcement_fails_closed() -> None:
    artifact = _artifact()
    original_decision, _ = _originals(artifact)
    with pytest.raises(ReplayEngineError):
        run_replay(artifact, original_decision, {"artifact_type": "enforcement_result"}, _trace_context())


def test_malformed_input_artifact_fails_closed() -> None:
    original_decision, original_enforcement = _originals()
    malformed = {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "eval_run_id": "missing-required-fields"
    }
    with pytest.raises(ReplayEngineError):
        run_replay(malformed, original_decision, original_enforcement, _trace_context())


def test_run_replay_rejects_unsupported_artifact_type_at_boundary() -> None:
    original_decision, original_enforcement = _originals()
    unsupported = {
        "artifact_type": "evaluation_control_decision",
        "schema_version": "1.1.0",
        "decision_id": "ecd-unsupported",
        "eval_run_id": "run-unsupported",
        "system_status": "healthy",
        "system_response": "allow",
        "triggered_signals": [],
        "threshold_snapshot": {
            "reliability_threshold": 0.85,
            "drift_threshold": 0.2,
            "trust_threshold": 0.8,
        },
        "trace_id": "44444444-4444-4444-8444-444444444444",
        "created_at": "2026-03-22T00:00:00Z",
        "decision": "allow",
        "rationale_code": "allow_healthy_eval_summary",
        "input_signal_reference": {
            "signal_type": "eval_summary",
            "source_artifact_id": "run-unsupported",
        },
        "run_id": "run-unsupported",
    }

    with pytest.raises(ReplayEngineError, match="REPLAY_UNSUPPORTED_INPUT_ARTIFACT"):
        run_replay(unsupported, original_decision, original_enforcement, _trace_context())


def test_deterministic_outcome_classification_and_no_input_mutation() -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    artifact_before = copy.deepcopy(artifact)
    decision_before = copy.deepcopy(original_decision)
    enforcement_before = copy.deepcopy(original_enforcement)

    result_1 = run_replay(artifact, original_decision, original_enforcement, _trace_context())
    result_2 = run_replay(artifact, original_decision, original_enforcement, _trace_context())

    assert result_1["consistency_status"] == result_2["consistency_status"]
    assert result_1["drift_detected"] == result_2["drift_detected"]
    assert result_1["replay_id"] == result_2["replay_id"]

    assert artifact == artifact_before
    assert original_decision == decision_before
    assert original_enforcement == enforcement_before


def test_replay_uses_canonical_enforcement_path_not_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    called = {"canonical": 0, "legacy": 0}
    original_canonical = enforce_control_decision

    def _canonical_spy(decision: dict) -> dict:
        called["canonical"] += 1
        return original_canonical(decision)

    def _legacy_forbidden(_decision: dict) -> dict:
        called["legacy"] += 1
        raise AssertionError("legacy enforcement path must not be called")

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.enforcement_engine.enforce_control_decision",
        _canonical_spy,
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.enforcement_engine.enforce_budget_decision",
        _legacy_forbidden,
    )

    result = run_replay(artifact, original_decision, original_enforcement, _trace_context())

    assert result["replay_path"] == "bag_replay_engine"
    assert called["canonical"] == 1
    assert called["legacy"] == 0


def test_run_replay_does_not_use_legacy_execute_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    def _forbidden_execute_replay(*_args, **_kwargs):
        raise AssertionError("run_replay must not call execute_replay")

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.replay_engine.execute_replay",
        _forbidden_execute_replay,
    )

    result = run_replay(artifact, original_decision, original_enforcement, _trace_context())
    assert result["replay_path"] == "bag_replay_engine"


def test_run_replay_raises_on_canonical_path_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    def _raise_control_loop(_artifact: dict, _trace_context: dict) -> dict:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.control_loop.run_control_loop",
        _raise_control_loop,
    )

    with pytest.raises(ReplayEngineError, match="REPLAY_EXECUTION_FAILED:RuntimeError"):
        run_replay(artifact, original_decision, original_enforcement, _trace_context())


def test_run_replay_wraps_control_loop_error_as_hard_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    def _raise_control_loop(_artifact: dict, _trace_context: dict) -> dict:
        raise ControlLoopError("boom")

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.control_loop.run_control_loop",
        _raise_control_loop,
    )

    with pytest.raises(ReplayEngineError, match="REPLAY_EXECUTION_FAILED:ControlLoopError"):
        run_replay(artifact, original_decision, original_enforcement, _trace_context())


def test_run_replay_wraps_enforcement_error_as_hard_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    def _raise_enforcement(_decision: dict) -> dict:
        raise EnforcementError("boom")

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.enforcement_engine.enforce_control_decision",
        _raise_enforcement,
    )

    with pytest.raises(ReplayEngineError, match="REPLAY_EXECUTION_FAILED:EnforcementError"):
        run_replay(artifact, original_decision, original_enforcement, _trace_context())


def test_replay_run_raises_hard_failure_on_control_loop_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.run_bundle_validator.validate_and_emit_decision",
        lambda _bundle_path: {"trace_id": "44444444-4444-4444-8444-444444444444", "run_id": "run-1"},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.evaluation_monitor.build_validation_monitor_record",
        lambda _decision: {"ok": True},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.evaluation_monitor.summarize_validation_monitor_records",
        lambda _records: {
            "aggregated_slis": {
                "bundle_validation_success_rate": 1.0,
                "provenance_required_rate": 1.0,
            }
        },
    )

    def _raise_control_loop(_artifact: dict, _ctx: dict) -> dict:
        raise ControlLoopError("control loop exploded")

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.control_loop.run_control_loop",
        _raise_control_loop,
    )

    with pytest.raises(ReplayEngineError, match="REPLAY_EXECUTION_FAILED:ControlLoopError"):
        replay_run("bundle/path.json", {"run_id": "run-1", "trace_id": "trace-1", "decision": "allow"})


def test_replay_run_raises_hard_failure_on_enforcement_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.run_bundle_validator.validate_and_emit_decision",
        lambda _bundle_path: {"trace_id": "44444444-4444-4444-8444-444444444444", "run_id": "run-2"},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.evaluation_monitor.build_validation_monitor_record",
        lambda _decision: {"ok": True},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.evaluation_monitor.summarize_validation_monitor_records",
        lambda _records: {
            "aggregated_slis": {
                "bundle_validation_success_rate": 1.0,
                "provenance_required_rate": 1.0,
            }
        },
    )

    def _raise_enforcement(_decision: dict) -> dict:
        raise EnforcementError("enforcement exploded")

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.enforcement_engine.enforce_control_decision",
        _raise_enforcement,
    )

    with pytest.raises(ReplayEngineError, match="REPLAY_EXECUTION_FAILED:EnforcementError"):
        replay_run("bundle/path.json", {"run_id": "run-2", "trace_id": "trace-2", "decision": "allow"})


def test_run_replay_rejects_unknown_enforcement_status_without_defaulting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    def _bad_enforcement(_decision: dict) -> dict:
        malformed = copy.deepcopy(original_enforcement)
        malformed["final_status"] = "unknown"
        return malformed

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.enforcement_engine.enforce_control_decision",
        _bad_enforcement,
    )

    with pytest.raises(ReplayEngineError, match="unsupported final_status"):
        run_replay(artifact, original_decision, original_enforcement, _trace_context())


@pytest.mark.parametrize("invalid_value", [None, "bad", 42])
def test_run_replay_rejects_invalid_artifact_types(invalid_value: object) -> None:
    original_decision, original_enforcement = _originals()
    with pytest.raises(ReplayEngineError, match="REPLAY_INVALID_ARTIFACT"):
        run_replay(invalid_value, original_decision, original_enforcement, _trace_context())


@pytest.mark.parametrize("invalid_value", [None, "bad", 42])
def test_run_replay_rejects_invalid_original_decision_types(invalid_value: object) -> None:
    artifact = _artifact()
    _, original_enforcement = _originals(artifact)
    with pytest.raises(ReplayEngineError, match="REPLAY_MISSING_ORIGINAL_DECISION"):
        run_replay(artifact, invalid_value, original_enforcement, _trace_context())


@pytest.mark.parametrize("invalid_value", [None, "bad", 42])
def test_run_replay_rejects_invalid_original_enforcement_types(invalid_value: object) -> None:
    artifact = _artifact()
    original_decision, _ = _originals(artifact)
    with pytest.raises(ReplayEngineError, match="REPLAY_MISSING_ORIGINAL_ENFORCEMENT"):
        run_replay(artifact, original_decision, invalid_value, _trace_context())


@pytest.mark.parametrize("invalid_value", [None, "bad", 42])
def test_run_replay_rejects_invalid_trace_context_types(invalid_value: object) -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)
    with pytest.raises(ReplayEngineError, match="REPLAY_INVALID_TRACE_CONTEXT"):
        run_replay(artifact, original_decision, original_enforcement, invalid_value)


def test_replay_missing_linkage_fails() -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)
    original_decision.pop("decision_id", None)
    with pytest.raises(ReplayEngineError, match="decision_id|linkage requires"):
        run_replay(artifact, original_decision, original_enforcement, _trace_context())


def test_replay_persistence_matches_runtime_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trace_id = "trace-replay-persist-001"
    trace = {
        "trace_id": trace_id,
        "root_span_id": "span-1",
        "spans": [
            {
                "span_id": "span-1",
                "trace_id": trace_id,
                "parent_span_id": None,
                "name": "root",
                "status": "ok",
                "start_time": "2026-03-23T00:00:00+00:00",
                "end_time": "2026-03-23T00:00:01+00:00",
                "events": [],
            }
        ],
        "artifacts": [],
        "start_time": "2026-03-23T00:00:00+00:00",
        "end_time": "2026-03-23T00:00:01+00:00",
        "context": {},
        "schema_version": "1.0.0",
    }
    traces_dir = tmp_path / "traces"
    persist_trace(trace, base_dir=traces_dir)

    monkeypatch.setattr("spectrum_systems.modules.runtime.replay_engine._new_id", lambda: "fixed-replay-id")

    with pytest.raises(ReplayEngineError, match="persist_result=True is not allowed"):
        execute_replay(trace_id, base_dir=traces_dir, persist_result=True)
    with pytest.raises(ReplayEngineError, match="persist_result=True is not allowed"):
        execute_replay(trace_id, base_dir=traces_dir, persist_result=True)


def test_replay_schema_canonical_only() -> None:
    legacy_payload = {
        "artifact_type": "replay_result",
        "schema_version": "1.0.0",
        "replay_path": "bag_replay_engine",
        "replay_id": "legacy-replay-id",
        "source_trace_id": "trace-legacy",
        "replayed_at": "2026-03-23T00:00:00+00:00",
        "status": "success",
        "prerequisites_valid": True,
        "prerequisite_errors": [],
        "steps_executed": [],
        "output_comparison": {},
        "determinism_notes": [],
        "context": {},
    }
    errors = validate_replay_result(legacy_payload)
    assert errors


def test_governed_replay_validation_does_not_fallback_to_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy_payload = {
        "artifact_type": "replay_result",
        "schema_version": "1.0.0",
        "replay_id": "legacy-replay-id",
        "source_trace_id": "trace-legacy",
        "replayed_at": "2026-03-23T00:00:00+00:00",
        "status": "success",
        "prerequisites_valid": True,
        "prerequisite_errors": [],
        "steps_executed": [],
        "output_comparison": {},
        "determinism_notes": [],
        "context": {},
    }

    def _forbidden_legacy_validator(_result: dict) -> list[str]:
        raise AssertionError("legacy replay validator must not be called on governed validation")

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.replay_engine.validate_replay_result_legacy",
        _forbidden_legacy_validator,
    )

    errors = validate_replay_result(legacy_payload)
    assert errors


def test_legacy_replay_validator_accepts_legacy_shape() -> None:
    legacy_payload = {
        "artifact_type": "replay_result",
        "schema_version": "1.0.0",
        "replay_id": "legacy-replay-id",
        "source_trace_id": "trace-legacy",
        "replayed_at": "2026-03-23T00:00:00+00:00",
        "status": "success",
        "prerequisites_valid": True,
        "prerequisite_errors": [],
        "steps_executed": [],
        "output_comparison": {},
        "determinism_notes": [],
        "context": {},
    }

    assert validate_replay_result_legacy(legacy_payload) == []


def test_replay_persistence_enforced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trace_id = "trace-replay-persist-002"
    trace = {
        "trace_id": trace_id,
        "root_span_id": "span-1",
        "spans": [
            {
                "span_id": "span-1",
                "trace_id": trace_id,
                "parent_span_id": None,
                "name": "root",
                "status": "ok",
                "start_time": "2026-03-23T00:00:00+00:00",
                "end_time": "2026-03-23T00:00:01+00:00",
                "events": [],
            }
        ],
        "artifacts": [],
        "start_time": "2026-03-23T00:00:00+00:00",
        "end_time": "2026-03-23T00:00:01+00:00",
        "context": {},
        "schema_version": "1.0.0",
    }
    traces_dir = tmp_path / "traces"
    persist_trace(trace, base_dir=traces_dir)
    monkeypatch.setattr("spectrum_systems.modules.runtime.replay_engine._new_id", lambda: "fixed-replay-id-2")

    with pytest.raises(ReplayEngineError, match="persist_result=True is not allowed"):
        execute_replay(trace_id, base_dir=traces_dir, persist_result=True)
    replay_path = tmp_path / "replays" / "fixed-replay-id-2.json"
    assert not replay_path.exists()


def test_execute_replay_analysis_mutation_disabled(tmp_path: Path) -> None:
    trace_id = "trace-exec-analysis-disabled-001"
    persist_trace(
        {
            "trace_id": trace_id,
            "root_span_id": "span-1",
            "spans": [{
                "span_id": "span-1",
                "trace_id": trace_id,
                "parent_span_id": None,
                "name": "runtime",
                "status": "ok",
                "start_time": "2026-03-23T00:00:00+00:00",
                "end_time": "2026-03-23T00:00:01+00:00",
                "events": [],
            }],
            "artifacts": [],
            "start_time": "2026-03-23T00:00:00+00:00",
            "end_time": "2026-03-23T00:00:01+00:00",
            "context": {},
            "schema_version": "1.0.0",
        },
        base_dir=tmp_path / "traces",
    )
    with pytest.raises(ReplayEngineError, match="run_decision_analysis=True is not supported"):
        execute_replay(trace_id, base_dir=tmp_path / "traces", run_decision_analysis=True)


def test_execute_replay_can_hard_fail_prerequisites() -> None:
    with pytest.raises(ReplayPrerequisiteError, match="prerequisites not met"):
        execute_replay(
            "missing-trace-for-hard-fail",
            base_dir=Path("/tmp/nonexistent-traces-dir"),
            require_prerequisites=True,
        )


def test_runtime_replay_observability_parity(tmp_path: Path) -> None:
    runtime_result = run_control_loop(_artifact(), _trace_context())["evaluation_control_decision"]
    assert runtime_result["trace_id"] == _trace_context()["trace_id"]

    trace_id = "trace-replay-parity-001"
    persist_trace(
        {
            "trace_id": trace_id,
            "root_span_id": "span-1",
            "spans": [{
                "span_id": "span-1",
                "trace_id": trace_id,
                "parent_span_id": None,
                "name": "runtime",
                "status": "ok",
                "start_time": "2026-03-23T00:00:00+00:00",
                "end_time": "2026-03-23T00:00:01+00:00",
                "events": [],
            }],
            "artifacts": [],
            "start_time": "2026-03-23T00:00:00+00:00",
            "end_time": "2026-03-23T00:00:01+00:00",
            "context": {},
            "schema_version": "1.0.0",
        },
        base_dir=tmp_path / "traces",
    )
    replay_result = execute_replay(trace_id, base_dir=tmp_path / "traces")
    assert replay_result["source_trace_id"] == trace_id

def test_run_replay_attaches_baseline_artifacts_when_baseline_present() -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    baseline = run_replay(artifact, original_decision, original_enforcement, _trace_context())
    result = run_replay(
        artifact,
        original_decision,
        original_enforcement,
        _trace_context(),
        baseline_artifact=baseline,
    )

    assert "drift_detection_result" in result
    assert "baseline_gate_decision" in result
    assert result["baseline_gate_decision"]["status"] in {"pass", "warn"}


def test_run_replay_blocks_when_baseline_gate_blocks() -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    baseline = run_replay(artifact, original_decision, original_enforcement, _trace_context())
    blocked = copy.deepcopy(artifact)
    blocked["pass_rate"] = 0.0
    blocked["failure_rate"] = 1.0
    blocked["drift_rate"] = 1.0
    blocked["reproducibility_score"] = 0.0
    blocked["system_status"] = "failing"

    with pytest.raises(ReplayEngineError, match="BASELINE_GATE_BLOCKED"):
        run_replay(
            blocked,
            original_decision,
            original_enforcement,
            _trace_context(),
            baseline_artifact=baseline,
        )


def test_run_replay_attaches_observability_metrics_with_trace_linkage() -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    result = run_replay(artifact, original_decision, original_enforcement, _trace_context())

    assert "observability_metrics" in result
    observability = result["observability_metrics"]
    assert observability["artifact_type"] == "observability_metrics"
    assert observability["trace_refs"]["trace_id"] == result["trace_id"]
    assert result["replay_id"] in observability["source_artifact_ids"]


def test_run_replay_attaches_error_budget_status_when_slo_is_provided() -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    slo_definition = {
        "slo_id": "7f6f4f35a3d9c73fec0faece8f35f98af88c9b270e2d6a8a907a5162e03f8f8f",
        "artifact_type": "service_level_objective",
        "schema_version": "1.0.0",
        "timestamp": "2026-03-24T00:00:00Z",
        "service_name": "spectrum-runtime-control",
        "service_scope": "runtime_replay_control_surface",
        "objective_window": "rolling_24h",
        "objectives": [
            {
                "metric_name": "replay_success_rate",
                "target_operator": "gte",
                "target_value": 0.99,
                "unit": "ratio",
                "severity_on_breach": "block",
                "description": "Replay consistency objective",
            }
        ],
        "policy_id": "sre-observability-policy-v1",
        "generated_by_version": "sre-08-sre-10@1.0.0",
    }
    error_budget_policy = {
        "artifact_type": "error_budget_policy",
        "schema_version": "1.0.0",
        "policy_id": "sre-error-budget-policy-v1",
        "measurement_window": "single_run",
        "supported_metrics": ["replay_success_rate"],
        "warning_consumption_ratio": 0.5,
        "exhausted_consumption_ratio": 1.0,
        "unknown_metric_handling": "fail_closed",
        "missing_metric_handling": "fail_closed",
        "generated_by_version": "sre-09@1.0.0",
    }

    result = run_replay(
        artifact,
        original_decision,
        original_enforcement,
        _trace_context(),
        slo_definition=slo_definition,
        error_budget_policy=error_budget_policy,
    )

    assert "error_budget_status" in result
    assert result["error_budget_status"]["artifact_type"] == "error_budget_status"
    assert result["error_budget_status"]["trace_refs"]["trace_id"] == result["trace_id"]
    assert result["error_budget_status"]["observability_metrics_id"] == result["observability_metrics"]["artifact_id"]
    validate_artifact(result, "replay_result")
