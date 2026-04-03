from __future__ import annotations

from pathlib import Path

from spectrum_systems.contracts import validate_artifact
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
