from __future__ import annotations

from pathlib import Path

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.mvp_20_slice_execution import run_mvp_20_slice_execution_drill
from spectrum_systems.modules.runtime.system_mvp_validation import run_system_mvp_validation


def test_system_mvp_validation_is_deterministic_and_contract_valid() -> None:
    kwargs = {
        "pqx_state_path": Path("tests/fixtures/pqx_runs/state.json"),
        "pqx_runs_root": Path("tests/fixtures/pqx_runs"),
        "created_at": "2026-04-03T23:59:00Z",
    }

    first = run_system_mvp_validation(**kwargs)
    second = run_system_mvp_validation(**kwargs)

    assert first == second
    validate_artifact(first["system_mvp_validation_report"], "system_mvp_validation_report")


def test_system_mvp_report_structure_is_stable() -> None:
    result = run_system_mvp_validation(
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        created_at="2026-04-03T23:59:00Z",
    )

    report = result["system_mvp_validation_report"]
    assert len(report["runs_executed"]) == 5
    assert {item["scenario_id"] for item in report["runs_executed"]} == {
        "SCN-HAPPY_PATH_BOUNDED",
        "SCN-MISSING_REQUIRED_REVIEW",
        "SCN-PROGRAM_MISALIGNMENT",
        "SCN-NOISY_FAILURE_SURFACE",
        "SCN-COMPLETE_WITH_NEXT_STEP",
    }
    assert report["success_cases"]
    assert report["failure_cases"]
    assert report["efficiency_metrics"]["total_cycles"] == 5

    run_by_scenario = {item["scenario_id"]: item for item in report["runs_executed"]}
    assert run_by_scenario["SCN-MISSING_REQUIRED_REVIEW"]["required_reviews"]
    assert run_by_scenario["SCN-NOISY_FAILURE_SURFACE"]["status"] == "blocked"

    for item in report["runs_executed"]:
        refs = item["artifact_refs"]
        assert refs["build_summary"].startswith("build_summary:BSR-")
        assert refs["next_step_recommendation"].startswith("next_step_recommendation:NSR-")
        assert refs["trace_navigation"].startswith("trace_navigation:CSIV-")
        assert refs["adaptive_execution_observability"].startswith("adaptive_execution_observability:AEO-")
        assert refs["adaptive_execution_trend_report"].startswith("adaptive_execution_trend_report:AET-")
        assert refs["adaptive_execution_policy_review"].startswith("adaptive_execution_policy_review:AEPR-")


def test_mvp_20_slice_execution_drill_is_deterministic_and_contract_valid() -> None:
    kwargs = {
        "pqx_state_path": Path("tests/fixtures/pqx_runs/state.json"),
        "pqx_runs_root": Path("tests/fixtures/pqx_runs"),
        "created_at": "2026-04-04T00:00:00Z",
    }

    first = run_mvp_20_slice_execution_drill(**kwargs)
    second = run_mvp_20_slice_execution_drill(**kwargs)

    assert first == second
    validate_artifact(first["mvp_20_slice_execution_report"], "mvp_20_slice_execution_report")


def test_mvp_20_slice_execution_drill_enforces_stop_and_parity() -> None:
    result = run_mvp_20_slice_execution_drill(
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        created_at="2026-04-04T00:00:00Z",
    )

    report = result["mvp_20_slice_execution_report"]
    assert report["total_slices_planned"] == 20
    assert report["total_slices_attempted"] >= 10
    assert report["total_slices_completed"] >= 9
    assert report["stop_or_completion_reason"] == "execution_blocked"
    assert report["determinism_status"] == "deterministic"
    assert report["replay_status"] == "parity_verified"
    assert report["trace_integrity_status"] == "complete"
    assert report["program_alignment_status"] == "aligned"
    assert report["operator_clarity_assessment"]["build_summary_readable"] is True
    assert report["evidence_refs"]["drill_input"].startswith("roadmap_artifact:RDX-BATCH-MVP-20")

    decisions = report["continuation_decision_sequence"]
    assert decisions
    assert all(item["decision"] in {"continue", "stop", "escalate"} for item in decisions)
    assert any(item["reason_code"] == "continue_safe" for item in decisions)

    run_a = result["run_a"]
    run_b = result["run_b"]
    assert run_a["attempted_sequence"] == run_b["attempted_sequence"]
    assert run_a["completed_sequence"] == run_b["completed_sequence"]
    assert run_a["stop_reason"] == run_b["stop_reason"]
    assert run_a["required_review_hits"] >= 1
