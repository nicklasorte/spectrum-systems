from spectrum_systems.modules.runtime.ai_adapter import build_ai_request, normalize_ai_response
from spectrum_systems.modules.runtime.eval_slice_runner import summarize_eval_slice
from spectrum_systems.modules.runtime.task_registry import resolve_task_spec


def test_task_registry_resolves_known_task() -> None:
    spec = resolve_task_spec(registry={"tasks": [{"task_id": "t1", "artifact_family": "review_projection_bundle_artifact"}]}, task_id="t1")
    assert spec["artifact_family"] == "review_projection_bundle_artifact"


def test_ai_adapter_request_and_response_are_trace_bound() -> None:
    request = build_ai_request(
        run_id="run-1",
        trace_id="trace-1",
        task_id="t1",
        prompt_id="p1",
        payload={"input": "x"},
    )
    response = normalize_ai_response(request=request, model_output={"ok": True}, success=True)
    assert response["run_id"] == "run-1"
    assert response["trace_id"] == "trace-1"
    assert response["success"] is True


def test_eval_slice_runner_summary_deterministic() -> None:
    summary = summarize_eval_slice(
        eval_id="e1",
        case_results=[{"case_id": "c1", "passed": True}, {"case_id": "c2", "passed": False}],
    )
    assert summary == {"eval_id": "e1", "total_cases": 2, "failed_cases": 1, "pass_rate": 0.5}
