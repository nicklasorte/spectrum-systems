from __future__ import annotations

from spectrum_systems.modules.runtime.tpa_complexity_governance import (
    build_complexity_budget,
    build_complexity_trend,
    build_simplification_campaign,
    enforce_budget_trend_control,
)


def _signals(*, lines_added: int, lines_removed: int, abstractions: int = 0, deletions: int = 0) -> dict[str, int]:
    return {
        "files_changed_count": 1,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "net_line_delta": lines_added - lines_removed,
        "functions_added_count": 0,
        "functions_removed_count": 0,
        "helpers_added_count": 0,
        "helpers_removed_count": 0,
        "wrappers_collapsed_count": 0,
        "deletions_count": deletions,
        "public_surface_delta_count": 0,
        "approximate_max_nesting_delta": 0,
        "approximate_branching_delta": 0,
        "abstraction_added_count": abstractions,
        "abstraction_removed_count": 0,
    }


def test_budget_logic_within_budget_allows() -> None:
    budget = build_complexity_budget(
        run_id="run-1",
        trace_id="trace-1",
        step_id="AI-01",
        module_or_path="module.a",
        build_signals=_signals(lines_added=10, lines_removed=0),
        simplify_signals=_signals(lines_added=8, lines_removed=4),
        last_updated="2026-04-04T00:00:00Z",
        historical_scores=[4],
        allowed_growth_delta=10,
    )
    assert budget["budget_status"] == "healthy"
    assert budget["recommended_control_decision"] == "allow"


def test_budget_logic_exceeded_escalates_to_freeze_or_block() -> None:
    budget = build_complexity_budget(
        run_id="run-1",
        trace_id="trace-1",
        step_id="AI-01",
        module_or_path="module.a",
        build_signals=_signals(lines_added=5, lines_removed=0),
        simplify_signals=_signals(lines_added=30, lines_removed=0, abstractions=4),
        last_updated="2026-04-04T00:00:00Z",
        historical_scores=[5, 7, 8, 9],
        allowed_growth_delta=5,
    )
    assert budget["budget_status"] == "exceeded"
    assert budget["recommended_control_decision"] in {"freeze", "block"}


def test_trend_tracking_classifies_directions() -> None:
    improving = build_complexity_trend(
        run_id="run-1",
        trace_id="trace-1",
        step_id="AI-01",
        module="module.a",
        artifact_type_scope="runtime",
        slice_family="TPA",
        points=[
            {"index": 0, "step_id": "AI-01", "complexity": 10, "complexity_delta": -3, "simplify_effectiveness": 2.0, "deletions_count": 1, "abstraction_growth": 0},
            {"index": 1, "step_id": "AI-02", "complexity": 7, "complexity_delta": -2, "simplify_effectiveness": 2.0, "deletions_count": 2, "abstraction_growth": -1},
        ],
    )
    degrading = build_complexity_trend(
        run_id="run-1",
        trace_id="trace-1",
        step_id="AI-03",
        module="module.a",
        artifact_type_scope="runtime",
        slice_family="TPA",
        points=[
            {"index": 0, "step_id": "AI-01", "complexity": 10, "complexity_delta": 2, "simplify_effectiveness": -1.0, "deletions_count": 0, "abstraction_growth": 2},
            {"index": 1, "step_id": "AI-02", "complexity": 12, "complexity_delta": 3, "simplify_effectiveness": -2.0, "deletions_count": 0, "abstraction_growth": 3},
        ],
    )
    assert improving["trend_direction"] == "improving"
    assert degrading["trend_direction"] == "degrading"


def test_campaign_generation_emits_hotspot_signal() -> None:
    budget = build_complexity_budget(
        run_id="run-1",
        trace_id="trace-1",
        step_id="AI-01",
        module_or_path="module.hot",
        build_signals=_signals(lines_added=5, lines_removed=0),
        simplify_signals=_signals(lines_added=20, lines_removed=0, abstractions=3),
        last_updated="2026-04-04T00:00:00Z",
        historical_scores=[1, 2, 3],
        allowed_growth_delta=4,
    )
    trend = build_complexity_trend(
        run_id="run-1",
        trace_id="trace-1",
        step_id="AI-01",
        module="module.hot",
        artifact_type_scope="runtime",
        slice_family="TPA",
        points=[
            {"index": 0, "step_id": "AI-01", "complexity": 9, "complexity_delta": 4, "simplify_effectiveness": -2.0, "deletions_count": 0, "abstraction_growth": 2},
            {"index": 1, "step_id": "AI-02", "complexity": 13, "complexity_delta": 3, "simplify_effectiveness": -1.0, "deletions_count": 0, "abstraction_growth": 2},
        ],
    )
    campaign = build_simplification_campaign(
        run_id="run-1",
        trace_id="trace-1",
        step_id="AI-01",
        target_module="module.hot",
        trend=trend,
        budget=budget,
    )
    assert campaign["artifact_type"] == "tpa_simplification_campaign"
    assert campaign["pqx_cleanup_ready"] is True
    assert campaign["recommended_action"] in {"simplify", "refactor", "delete"}


def test_control_integration_uses_budget_and_trend_signals() -> None:
    budget = {"recommended_control_decision": "freeze"}
    trend = {"recommended_control_decision": "warn"}
    assert enforce_budget_trend_control(existing_decision="allow", budget=budget, trend=trend) == "freeze"
    assert enforce_budget_trend_control(existing_decision="block", budget=budget, trend=trend) == "block"


def test_replay_determinism_same_inputs_same_outputs() -> None:
    kwargs = {
        "run_id": "run-1",
        "trace_id": "trace-1",
        "step_id": "AI-01",
        "module_or_path": "module.a",
        "build_signals": _signals(lines_added=8, lines_removed=1),
        "simplify_signals": _signals(lines_added=7, lines_removed=3),
        "last_updated": "2026-04-04T00:00:00Z",
        "historical_scores": [4, 5],
        "allowed_growth_delta": 6,
    }
    a = build_complexity_budget(**kwargs)
    b = build_complexity_budget(**kwargs)
    assert a == b
