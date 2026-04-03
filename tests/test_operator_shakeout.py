from __future__ import annotations

from pathlib import Path

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.operator_shakeout import run_operator_shakeout


def test_operator_shakeout_is_deterministic_and_contract_valid() -> None:
    kwargs = {
        "pqx_state_path": Path("tests/fixtures/pqx_runs/state.json"),
        "pqx_runs_root": Path("tests/fixtures/pqx_runs"),
        "created_at": "2026-04-03T23:59:00Z",
    }

    first = run_operator_shakeout(**kwargs)
    second = run_operator_shakeout(**kwargs)

    assert first == second
    validate_artifact(first["operator_friction_report"], "operator_friction_report")
    validate_artifact(first["operator_backlog_handoff"], "operator_backlog_handoff")

    scenario_ids = [item["scenario_id"] for item in first["scenario_results"]]
    assert scenario_ids == [
        "SCN-HAPPY_PATH_BOUNDED",
        "SCN-MISSING_REQUIRED_REVIEW",
        "SCN-PROGRAM_MISALIGNMENT",
        "SCN-REPEATED_RISK_TPA_GATE",
        "SCN-COMPLETE_WITH_NEXT_STEP",
        "SCN-NOISY_FAILURE_SURFACE",
        "SCN-WEAK_RECOMMENDATION_QUALITY",
    ]


def test_friction_classification_and_backlog_priority_are_traceable() -> None:
    result = run_operator_shakeout(
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        created_at="2026-04-03T23:59:00Z",
    )

    friction = result["operator_friction_report"]
    backlog = result["operator_backlog_handoff"]

    friction_types = {item["friction_type"] for item in friction["friction_items"]}
    assert "review/context surfacing quality" in friction_types
    assert "trace/replay discoverability" in friction_types
    assert "noisy summary artifact" in friction_types

    ranks = [item["rank"] for item in backlog["prioritized_items"]]
    assert ranks == sorted(ranks)
    assert backlog["source_refs"] == [f"operator_friction_report:{friction['report_id']}"]

    for item in backlog["prioritized_items"]:
        assert item["source_friction_refs"]
        for ref in item["source_friction_refs"]:
            assert ref in friction["scenarios_exercised"]

    noisy = next(item for item in result["scenario_results"] if item["scenario_id"] == "SCN-NOISY_FAILURE_SURFACE")
    summary = noisy["artifacts"]["build_summary"]
    recommendation = noisy["artifacts"]["next_step_recommendation"]
    assert summary["artifact_index"]["next_step_recommendation"] == f"next_step_recommendation:{recommendation['recommendation_id']}"
    assert summary["failure_surface"]["source_refs"]
    assert recommendation["next_step"]["required_artifacts"]


def test_subset_execution_runs_only_requested_scenarios() -> None:
    result = run_operator_shakeout(
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        created_at="2026-04-03T23:59:00Z",
        scenario_ids=["SCN-HAPPY_PATH_BOUNDED", "SCN-WEAK_RECOMMENDATION_QUALITY"],
    )

    assert [item["scenario_id"] for item in result["scenario_results"]] == [
        "SCN-HAPPY_PATH_BOUNDED",
        "SCN-WEAK_RECOMMENDATION_QUALITY",
    ]
    assert set(result["operator_friction_report"]["scenarios_exercised"]) == {
        "SCN-HAPPY_PATH_BOUNDED",
        "SCN-WEAK_RECOMMENDATION_QUALITY",
    }
