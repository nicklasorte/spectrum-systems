from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.governance_chain_guard import (
    GovernanceChainGuardError,
    validate_governance_chain,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _replay(trace_id: str, run_id: str) -> dict:
    replay = json.loads((REPO_ROOT / "contracts" / "examples" / "replay_result.json").read_text(encoding="utf-8"))
    replay["trace_id"] = trace_id
    replay["replay_run_id"] = run_id
    replay["original_run_id"] = run_id
    replay["observability_metrics"]["trace_refs"]["trace_id"] = trace_id
    replay["error_budget_status"]["trace_refs"]["trace_id"] = trace_id
    replay["error_budget_status"]["observability_metrics_id"] = replay["observability_metrics"]["artifact_id"]
    return replay


def _regression(trace_id: str, run_id: str) -> dict:
    return {
        "artifact_type": "regression_result",
        "schema_version": "1.1.0",
        "run_id": run_id,
        "suite_id": "suite-1",
        "created_at": "2026-04-11T00:00:00Z",
        "total_traces": 1,
        "passed_traces": 1,
        "failed_traces": 0,
        "pass_rate": 1.0,
        "overall_status": "pass",
        "regression_status": "pass",
        "blocked": False,
        "results": [
            {
                "trace_id": trace_id,
                "replay_result_id": "replay:1",
                "analysis_id": "analysis:1",
                "decision_status": "consistent",
                "reproducibility_score": 1.0,
                "drift_type": "",
                "passed": True,
                "failure_reasons": [],
                "baseline_replay_result_id": "replay:1",
                "current_replay_result_id": "replay:1",
                "baseline_trace_id": trace_id,
                "current_trace_id": trace_id,
                "baseline_reference": "contracts/examples/replay_result.json",
                "current_reference": "contracts/examples/replay_result.json",
                "mismatch_summary": [],
                "comparison_digest": "a" * 64,
            }
        ],
        "summary": {"drift_counts": {"none": 1}, "average_reproducibility_score": 1.0},
    }


def _control(run_id: str, trace_id: str) -> dict:
    control = json.loads(
        (REPO_ROOT / "contracts" / "examples" / "evaluation_control_decision.json").read_text(encoding="utf-8")
    )
    control["run_id"] = run_id
    control["trace_id"] = trace_id
    return control


def _execution_record(run_id: str, trace_id: str) -> dict:
    return {
        "schema_version": "1.1.0",
        "artifact_type": "pqx_slice_execution_record",
        "step_id": "AI-01",
        "run_id": run_id,
        "trace_id": trace_id,
        "status": "completed",
        "decision_summary": {
            "execution_status": "success",
            "control_decision": "allow",
            "enforcement_action": "allow",
        },
        "artifacts_emitted": [
            "runs/run.request.json",
            "runs/run.result.json",
            "runs/run.replay_result.json",
            "runs/run.regression_run_result.json",
            "runs/run.control_decision.json",
        ],
        "certification_status": "certified",
        "replay_result_ref": "runs/run.replay_result.json",
        "control_decision_ref": "runs/run.control_decision.json",
        "control_surface_gap_packet_ref": None,
        "control_surface_gap_packet_consumed": False,
        "prioritized_control_surface_gaps": [],
        "pqx_gap_work_items": [],
        "control_surface_gap_influence": {
            "influenced_execution_block": False,
            "influenced_next_step_selection": False,
            "influenced_priority_ordering": False,
            "influenced_transition_decision": False,
            "reason_codes": [],
            "control_surface_blocking_reason_refs": [],
        },
    }


def test_validate_governance_chain_returns_replay_comparison_evidence(tmp_path: Path) -> None:
    run_id = "run-001"
    trace_id = "trace:run-001:AI-01"
    replay = _replay(trace_id, run_id)

    result = validate_governance_chain(
        run_id=run_id,
        trace_id=trace_id,
        replay_result_path=_write(tmp_path / "replay.json", replay),
        replay_baseline_path=REPO_ROOT / "contracts" / "examples" / "replay_result.json",
        regression_result_path=_write(tmp_path / "regression.json", _regression(trace_id, run_id)),
        control_decision_path=_write(tmp_path / "control.json", _control(run_id, trace_id)),
        execution_record_path=_write(tmp_path / "record.json", _execution_record(run_id, trace_id)),
    )

    assert result["comparison_digest"]
    assert isinstance(result["hash_match"], bool)
    assert isinstance(result["fingerprint_match"], bool)


def test_validate_governance_chain_fails_when_regression_eval_missing(tmp_path: Path) -> None:
    run_id = "run-001"
    trace_id = "trace:run-001:AI-01"
    record = _execution_record(run_id, trace_id)
    record["artifacts_emitted"] = ["runs/run.request.json", "runs/run.replay_result.json"]

    with pytest.raises(GovernanceChainGuardError, match="required eval missing"):
        validate_governance_chain(
            run_id=run_id,
            trace_id=trace_id,
            replay_result_path=_write(tmp_path / "replay.json", _replay(trace_id, run_id)),
            replay_baseline_path=REPO_ROOT / "contracts" / "examples" / "replay_result.json",
            regression_result_path=_write(tmp_path / "regression.json", _regression(trace_id, run_id)),
            control_decision_path=_write(tmp_path / "control.json", _control(run_id, trace_id)),
            execution_record_path=_write(tmp_path / "record.json", record),
        )
