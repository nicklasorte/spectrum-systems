from __future__ import annotations

import copy

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.pqx_sequential_loop import PQXSequentialLoopError, run_pqx_sequential


class _AllowContextResult:
    status = "allow"
    blocking_reasons: tuple[str, ...] = ()


def _initial_context() -> dict[str, object]:
    return {
        "stage": "sequence_execution",
        "runtime_environment": "cli",
        "classification": "governed_pqx_required",
        "execution_context": "pqx_governed",
        "authority_evidence_ref": "data/pqx_runs/authority.pqx_slice_execution_record.json",
        "run_id": "run-con-047",
    }


def _slice(slice_id: str) -> dict[str, object]:
    return {
        "slice_id": slice_id,
        "wrapper": {
            "schema_version": "1.0.0",
            "artifact_type": "codex_pqx_task_wrapper",
            "wrapper_id": f"wrap-{slice_id}",
            "task_identity": {"task_id": f"task-{slice_id}", "run_id": "run-con-047", "step_id": slice_id, "step_name": slice_id},
            "task_source": {"source_type": "codex_prompt", "prompt": "Execute"},
            "execution_intent": {"execution_context": "pqx_governed", "mode": "governed"},
            "governance": {
                "classification": "governed_pqx_required",
                "pqx_required": True,
                "authority_state": "authoritative_governed_pqx",
                "authority_resolution": "authoritative",
                "authority_evidence_ref": "data/pqx_runs/authority.pqx_slice_execution_record.json",
                "contract_preflight_result_artifact_path": None,
            },
            "changed_paths": ["tests/test_pqx_execution_trace.py"],
            "metadata": {
                "requested_at": "2026-04-02T00:00:00Z",
                "dependencies": [],
                "policy_version": "1.0.0",
                "authority_notes": None,
            },
            "pqx_execution_request": {
                "schema_version": "1.1.0",
                "run_id": "run-con-047",
                "step_id": slice_id,
                "step_name": slice_id,
                "dependencies": [],
                "requested_at": "2026-04-02T00:00:00Z",
                "prompt": "Execute",
                "roadmap_version": "roadmap:v1",
                "row_snapshot": {"row_index": 0, "step_id": slice_id, "step_name": slice_id, "dependencies": [], "status": "ready"},
            },
        },
        "roadmap_path": "docs/roadmaps/system_roadmap.md",
        "state_path": "data/pqx_state.json",
        "runs_root": "data/pqx_runs",
        "pqx_output_text": f"out-{slice_id}",
        "input_ref": f"input:{slice_id}",
    }


def _patch_allow_path(monkeypatch: pytest.MonkeyPatch, *, enforcement_status: str) -> None:
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.run_wrapped_pqx_task",
        lambda **kwargs: {
            "status": "complete",
            "result": "/repo/data/pqx_runs/step.result.json",
            "slice_execution_record": "/repo/data/pqx_runs/step.pqx_slice_execution_record.json",
        },
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop._load_json_ref",
        lambda path: (
            {
                "artifact_type": "pqx_slice_execution_record",
                "schema_version": "1.1.0",
                "step_id": "AI-01",
                "run_id": "run-con-047",
                "trace_id": "trace-1",
                "status": "completed",
                "decision_summary": {
                    "execution_status": "success",
                    "control_decision": "allow",
                    "enforcement_action": "allow"
                },
                "artifacts_emitted": ["data/pqx_runs/step.result.json"],
                "certification_status": "certified",
                "replay_result_ref": "data/replay.json",
                "control_decision_ref": "evaluation_control_decision:d-1",
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
                    "control_surface_blocking_reason_refs": []
                }
            }
            if "pqx_slice_execution_record" in path
            else {
                "artifact_type": "replay_result",
                "replay_id": "r",
                "replay_run_id": "rr",
                "trace_id": "tt",
                "timestamp": "2026-04-02T00:00:00Z",
                "observability_metrics": {"metrics": {}},
                "error_budget_status": {"objectives": []},
                "drift_detected": False,
                "consistency_status": "match",
            }
        ),
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.enforce_pqx_required_context",
        lambda **kwargs: _AllowContextResult(),
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.build_trace_context_from_replay_artifact",
        lambda _: {"trace_id": "tt", "replay_id": "r", "replay_run_id": "rr"},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.run_control_loop",
        lambda *_: {"evaluation_control_decision": {"decision": "allow", "decision_id": "d-1"}},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.enforce_control_before_execution",
        lambda _: {"enforcement_result": {"final_status": enforcement_status, "rationale": enforcement_status}},
    )


def test_contract_example_validates() -> None:
    validate_artifact(load_example("pqx_sequential_execution_trace"), "pqx_sequential_execution_trace")


def test_allow_and_review_runs_emit_schema_valid_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_allow_path(monkeypatch, enforcement_status="allow")
    allow_trace = run_pqx_sequential([_slice("AI-01")], _initial_context())
    validate_artifact(allow_trace, "pqx_sequential_execution_trace")
    assert allow_trace["final_status"] == "ALLOW"

    _patch_allow_path(monkeypatch, enforcement_status="require_review")
    review_trace = run_pqx_sequential([_slice("AI-01")], _initial_context())
    validate_artifact(review_trace, "pqx_sequential_execution_trace")
    assert review_trace["final_status"] == "REQUIRE_REVIEW"
    assert review_trace["stopping_slice_id"] == "AI-01"


def test_missing_required_refs_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_allow_path(monkeypatch, enforcement_status="allow")
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.run_control_loop",
        lambda *_: {"evaluation_control_decision": {"decision": "allow", "decision_id": ""}},
    )

    with pytest.raises(PQXSequentialLoopError, match="decision_id"):
        run_pqx_sequential([_slice("AI-01")], _initial_context())


def test_deterministic_for_identical_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_allow_path(monkeypatch, enforcement_status="allow")
    first = run_pqx_sequential([_slice("AI-01")], _initial_context())
    second = run_pqx_sequential([_slice("AI-01")], _initial_context())
    assert first == second
    assert first == copy.deepcopy(second)
