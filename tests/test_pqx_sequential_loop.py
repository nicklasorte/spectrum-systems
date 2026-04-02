from __future__ import annotations

import copy

import pytest

from spectrum_systems.modules.runtime.pqx_sequential_loop import (
    PQXSequentialLoopError,
    run_pqx_sequential,
)


class _AllowContextResult:
    status = "allow"
    blocking_reasons: tuple[str, ...] = ()


def _base_initial_context() -> dict[str, object]:
    return {
        "stage": "sequence_execution",
        "runtime_environment": "cli",
        "classification": "governed_pqx_required",
        "execution_context": "pqx_governed",
        "authority_evidence_ref": "data/pqx_runs/authority.pqx_slice_execution_record.json",
        "artifact_refs": ["seed:artifact"],
        "context_bundle": {"bundle_id": "ctx-1"},
    }


def _wrapper(wrapper_id: str) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "artifact_type": "codex_pqx_task_wrapper",
        "wrapper_id": wrapper_id,
        "task_identity": {
            "task_id": "task-1",
            "run_id": "run-1",
            "step_id": "B11",
            "step_name": "Step",
        },
        "task_source": {"source_type": "codex_prompt", "prompt": "Do thing"},
        "execution_intent": {"execution_context": "pqx_governed", "mode": "governed"},
        "governance": {
            "classification": "governed_pqx_required",
            "pqx_required": True,
            "authority_state": "authoritative_governed_pqx",
            "authority_resolution": "authoritative",
            "authority_evidence_ref": "data/pqx_runs/authority.pqx_slice_execution_record.json",
            "contract_preflight_result_artifact_path": None,
        },
        "changed_paths": ["tests/test_pqx_sequential_loop.py"],
        "metadata": {"requested_at": "2026-04-02T00:00:00Z", "dependencies": [], "policy_version": "1.0.0", "authority_notes": None},
        "pqx_execution_request": {
            "schema_version": "1.1.0",
            "run_id": "run-1",
            "step_id": "B11",
            "step_name": "Step",
            "dependencies": [],
            "requested_at": "2026-04-02T00:00:00Z",
            "prompt": "Do thing",
            "roadmap_version": "roadmap:v1",
            "row_snapshot": {"row_index": 0, "step_id": "B11", "step_name": "Step", "dependencies": [], "status": "ready"},
        },
    }


def _slice(slice_id: str) -> dict[str, object]:
    return {
        "slice_id": slice_id,
        "wrapper": _wrapper(f"wrap-{slice_id}"),
        "roadmap_path": "docs/roadmaps/system_roadmap.md",
        "state_path": "data/pqx_state.json",
        "runs_root": "data/pqx_runs",
        "pqx_output_text": f"output-{slice_id}",
        "input_ref": f"input:{slice_id}",
        "changed_paths": ["tests/test_pqx_sequential_loop.py"],
    }


def test_three_slices_all_allow_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    counters = {"i": 0}

    def _fake_run_wrapped_pqx_task(**kwargs: object) -> dict[str, object]:
        counters["i"] += 1
        idx = counters["i"]
        return {
            "status": "complete",
            "result": f"/repo/data/pqx_runs/s{idx}.result.json",
            "slice_execution_record": f"/repo/data/pqx_runs/s{idx}.pqx_slice_execution_record.json",
        }

    def _fake_load_json_ref(path_ref: str) -> dict[str, object]:
        idx = path_ref.split("s")[-1].split(".")[0]
        if path_ref.endswith("pqx_slice_execution_record.json"):
            return {"replay_result_ref": f"data/pqx_runs/s{idx}.replay_result.json"}
        return {
            "artifact_type": "replay_result",
            "replay_id": f"replay-{idx}",
            "replay_run_id": f"run-{idx}",
            "trace_id": f"trace-{idx}",
            "timestamp": "2026-04-02T00:00:00Z",
            "observability_metrics": {"artifact_type": "observability_metrics", "schema_version": "1.0.0", "artifact_id": "obs", "run_id": "run", "trace_refs": {"trace_id": f"trace-{idx}"}, "timestamp": "2026-04-02T00:00:00Z", "window": {"start": "2026-04-01T00:00:00Z", "end": "2026-04-02T00:00:00Z", "sample_size": 1}, "metrics": {"replay_success_rate": 1.0, "drift_exceed_threshold_rate": 0.0, "total_runs": 1}},
            "error_budget_status": {"artifact_type": "error_budget_status", "schema_version": "1.0.0", "run_id": "run", "trace_refs": {"trace_id": f"trace-{idx}"}, "observability_metrics_id": "obs", "timestamp": "2026-04-02T00:00:00Z", "budget_status": "healthy", "highest_severity": "healthy", "objectives": [{"metric_name": "replay_success_rate", "target": 0.9, "observed_value": 1.0, "consumed_error": 0.0, "remaining_error": 0.1, "consumption_ratio": 0.0, "status": "healthy"}], "triggered_conditions": []},
            "drift_detected": False,
            "consistency_status": "match",
        }

    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.run_wrapped_pqx_task", _fake_run_wrapped_pqx_task)
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop._load_json_ref", _fake_load_json_ref)
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.enforce_pqx_required_context",
        lambda **kwargs: _AllowContextResult(),
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.build_trace_context_from_replay_artifact",
        lambda artifact: {"trace_id": artifact["trace_id"], "replay_id": artifact["replay_id"], "replay_run_id": artifact["replay_run_id"]},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.run_control_loop",
        lambda artifact, trace: {"evaluation_control_decision": {"decision": "allow", "decision_id": f"d-{artifact['replay_id']}"}},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.enforce_control_before_execution",
        lambda context: {"enforcement_result": {"final_status": "allow"}},
    )
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.validate_artifact", lambda payload, schema: None)

    trace = run_pqx_sequential([_slice("1"), _slice("2"), _slice("3")], _base_initial_context())
    assert trace["final_status"] == "ALLOW"
    assert len(trace["slices"]) == 3
    assert all(item["final_slice_status"] == "ALLOW" for item in trace["slices"])
    assert len(trace["authority_evidence_refs"]) == 3
    assert trace["slices"][0]["slice_execution_record_ref"] is not None


def test_second_slice_block_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    idx = {"v": 0}

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.run_wrapped_pqx_task",
        lambda **kwargs: {"status": "complete", "result": "/repo/out.result.json", "slice_execution_record": f"/repo/s{(idx.__setitem__('v', idx['v'] + 1) or idx['v'])}.pqx_slice_execution_record.json"},
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop._load_json_ref",
        lambda path: {"replay_result_ref": "data/replay.json"} if "execution_record" in path else {"artifact_type": "replay_result", "replay_id": "r", "replay_run_id": "rr", "trace_id": "tt", "timestamp": "2026-04-02T00:00:00Z", "observability_metrics": {"metrics": {}}, "error_budget_status": {"objectives": []}, "drift_detected": False, "consistency_status": "match"},
    )
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.build_trace_context_from_replay_artifact", lambda a: {"trace_id": "tt", "replay_id": "r", "replay_run_id": "rr"})
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.run_control_loop", lambda a, t: {"evaluation_control_decision": {"decision": "deny", "decision_id": "d1"}})
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.enforce_pqx_required_context",
        lambda **kwargs: _AllowContextResult(),
    )
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.validate_artifact", lambda payload, schema: None)

    calls = {"n": 0}

    def _gate(_: dict[str, object]) -> dict[str, object]:
        calls["n"] += 1
        final = "deny" if calls["n"] == 2 else "allow"
        return {"enforcement_result": {"final_status": final, "rationale": final}}

    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.enforce_control_before_execution", _gate)

    trace = run_pqx_sequential([_slice("1"), _slice("2"), _slice("3")], _base_initial_context())
    assert trace["final_status"] == "BLOCK"
    assert len(trace["slices"]) == 2
    assert trace["slices"][-1]["final_slice_status"] == "BLOCK"
    assert trace["stopping_slice_id"] == "2"


def test_second_slice_require_review_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.run_wrapped_pqx_task", lambda **kwargs: {"status": "complete", "result": "/repo/out.result.json", "slice_execution_record": "/repo/execution_record.json"})
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop._load_json_ref",
        lambda path: {"replay_result_ref": "data/replay.json"} if "execution_record" in path else {"artifact_type": "replay_result", "replay_id": "r", "replay_run_id": "rr", "trace_id": "tt", "timestamp": "2026-04-02T00:00:00Z", "observability_metrics": {"metrics": {}}, "error_budget_status": {"objectives": []}, "drift_detected": False, "consistency_status": "match"},
    )
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.build_trace_context_from_replay_artifact", lambda a: {"trace_id": "tt", "replay_id": "r", "replay_run_id": "rr"})
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.run_control_loop", lambda a, t: {"evaluation_control_decision": {"decision": "require_review", "decision_id": "d1"}})
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.enforce_pqx_required_context",
        lambda **kwargs: _AllowContextResult(),
    )
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.validate_artifact", lambda payload, schema: None)

    calls = {"n": 0}
    def _gate(_: dict[str, object]) -> dict[str, object]:
        calls["n"] += 1
        final = "require_review" if calls["n"] == 2 else "allow"
        return {"enforcement_result": {"final_status": final, "rationale": final}}
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.enforce_control_before_execution", _gate)

    trace = run_pqx_sequential([_slice("1"), _slice("2"), _slice("3")], _base_initial_context())
    assert trace["final_status"] == "REQUIRE_REVIEW"
    assert len(trace["slices"]) == 2
    assert trace["stopping_slice_id"] == "2"


def test_missing_context_fail_closed() -> None:
    with pytest.raises(PQXSequentialLoopError, match="initial_context.stage"):
        run_pqx_sequential([_slice("1")], {"runtime_environment": "cli"})


def test_deterministic_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.run_wrapped_pqx_task", lambda **kwargs: {"status": "complete", "result": "/repo/out.result.json", "slice_execution_record": "/repo/execution_record.json"})
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop._load_json_ref",
        lambda path: {"replay_result_ref": "data/replay.json"} if "execution_record" in path else {"artifact_type": "replay_result", "replay_id": "r", "replay_run_id": "rr", "trace_id": "tt", "timestamp": "2026-04-02T00:00:00Z", "observability_metrics": {"metrics": {}}, "error_budget_status": {"objectives": []}, "drift_detected": False, "consistency_status": "match"},
    )
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.build_trace_context_from_replay_artifact", lambda a: {"trace_id": "tt", "replay_id": "r", "replay_run_id": "rr"})
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.run_control_loop", lambda a, t: {"evaluation_control_decision": {"decision": "allow", "decision_id": "d1"}})
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.enforce_control_before_execution", lambda c: {"enforcement_result": {"final_status": "allow"}})
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.enforce_pqx_required_context",
        lambda **kwargs: _AllowContextResult(),
    )
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.validate_artifact", lambda payload, schema: None)

    slices = [_slice("1")]
    ctx = _base_initial_context()
    first = run_pqx_sequential(copy.deepcopy(slices), copy.deepcopy(ctx))
    second = run_pqx_sequential(copy.deepcopy(slices), copy.deepcopy(ctx))
    assert first == second


def test_artifact_refs_passed_and_wrapper_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_wrappers: list[dict[str, object]] = []

    def _fake_runner(**kwargs: object) -> dict[str, object]:
        seen_wrappers.append(kwargs["wrapper"])
        return {"status": "complete", "result": "/repo/out.result.json", "slice_execution_record": "/repo/execution_record.json"}

    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.run_wrapped_pqx_task", _fake_runner)
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop._load_json_ref",
        lambda path: {"replay_result_ref": "data/replay.json"} if "execution_record" in path else {"artifact_type": "replay_result", "replay_id": "r", "replay_run_id": "rr", "trace_id": "tt", "timestamp": "2026-04-02T00:00:00Z", "observability_metrics": {"metrics": {}}, "error_budget_status": {"objectives": []}, "drift_detected": False, "consistency_status": "match"},
    )
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.build_trace_context_from_replay_artifact", lambda a: {"trace_id": "tt", "replay_id": "r", "replay_run_id": "rr"})
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.run_control_loop", lambda a, t: {"evaluation_control_decision": {"decision": "allow", "decision_id": "d1"}})
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.enforce_control_before_execution", lambda c: {"enforcement_result": {"final_status": "allow"}})
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.enforce_pqx_required_context",
        lambda **kwargs: _AllowContextResult(),
    )
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.validate_artifact", lambda payload, schema: None)

    slice_payload = _slice("1")
    wrapper = slice_payload["wrapper"]
    trace = run_pqx_sequential([slice_payload], _base_initial_context())
    assert seen_wrappers[0] is wrapper
    assert trace["slices"][0]["eval_result_ref"].startswith("evaluation_control_decision:")
    assert trace["slices"][0]["wrapper_ref"].startswith("codex_pqx_task_wrapper:")
    assert trace["authority_evidence_refs"][0].endswith("execution_record.json")


def test_execution_record_schema_validation_and_preflight_compatible_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[dict[str, object], str]] = []
    required_contexts: list[dict[str, object]] = []

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.run_wrapped_pqx_task",
        lambda **kwargs: {
            "status": "complete",
            "result": "/repo/out.result.json",
            "slice_execution_record": "/repo/step-1.pqx_slice_execution_record.json",
        },
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop._load_json_ref",
        lambda path: (
            {
                "artifact_type": "pqx_slice_execution_record",
                "schema_version": "1.1.0",
                "step_id": "B11",
                "run_id": "run-1",
                "trace_id": "trace-1",
                "status": "completed",
                "certification_status": "certified",
                "replay_result_ref": "data/replay.json",
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
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.build_trace_context_from_replay_artifact", lambda a: {"trace_id": "tt", "replay_id": "r", "replay_run_id": "rr"})
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.run_control_loop", lambda a, t: {"evaluation_control_decision": {"decision": "allow", "decision_id": "d1"}})
    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.enforce_control_before_execution", lambda c: {"enforcement_result": {"final_status": "allow"}})

    def _record_required_context(**kwargs: object) -> _AllowContextResult:
        required_contexts.append({"authority_evidence_ref": kwargs.get("authority_evidence_ref")})
        return _AllowContextResult()

    monkeypatch.setattr("spectrum_systems.modules.runtime.pqx_sequential_loop.enforce_pqx_required_context", _record_required_context)
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_sequential_loop.validate_artifact",
        lambda payload, schema: calls.append((payload, schema)),
    )

    slices = [_slice("1"), _slice("2")]
    slices[1]["required_context"] = {
        "classification": "governed_pqx_required",
        "execution_context": "pqx_governed",
    }
    trace = run_pqx_sequential(slices, _base_initial_context())

    assert trace["authority_evidence_refs"][0].endswith(".pqx_slice_execution_record.json")
    assert required_contexts[1]["authority_evidence_ref"].endswith(".pqx_slice_execution_record.json")
    assert any(schema == "pqx_slice_execution_record" for _, schema in calls)
