"""Tests for RGE Analysis Engine (Wave 0 repo audit)."""
from __future__ import annotations

from pathlib import Path

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.rge.analysis_engine import analyze_repository

_RUN = "run-ae-001"
_TRACE = "trace-ae-001"

# Resolve once — repo root is two levels up from spectrum_systems/rge
_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_basic_analysis_returns_valid_record():
    r = analyze_repository(repo_root=_REPO_ROOT, run_id=_RUN, trace_id=_TRACE)
    assert r["artifact_type"] == "rge_analysis_record"
    validate_artifact(r, "rge_analysis_record")


def test_context_maturity_bounded():
    r = analyze_repository(repo_root=_REPO_ROOT, run_id=_RUN, trace_id=_TRACE)
    assert 0 <= r["context_maturity_level"] <= r["context_maturity_max"]


def test_modules_present_matches_maturity():
    r = analyze_repository(repo_root=_REPO_ROOT, run_id=_RUN, trace_id=_TRACE)
    assert len(r["modules_present"]) == r["context_maturity_level"]


def test_missing_repo_yields_zero_maturity(tmp_path):
    r = analyze_repository(repo_root=tmp_path, run_id=_RUN, trace_id=_TRACE)
    assert r["context_maturity_level"] == 0
    assert r["modules_present"] == []


def test_drift_legs_from_bundle():
    bundle = {
        "drift_findings": [
            {"severity": "block", "affected_component": "EVL_coverage"},
            {"severity": "warning", "affected_component": "TPA_budget"},
            {"severity": "none", "affected_component": "AEX_boundary"},
        ]
    }
    r = analyze_repository(
        repo_root=_REPO_ROOT,
        run_id=_RUN,
        trace_id=_TRACE,
        roadmap_signal_bundle=bundle,
    )
    assert "EVL" in r["active_drift_legs"]
    assert "TPA" in r["active_drift_legs"]
    assert "AEX" not in r["active_drift_legs"]


def test_complexity_budgets_grouped_by_module():
    budgets = [
        {
            "module_or_path": "spectrum_systems/rge",
            "budget_status": "healthy",
            "burn_rate": 0.2,
            "current_complexity": 5,
            "baseline_complexity": 4,
        },
        {
            "module_or_path": "spectrum_systems/modules/runtime",
            "budget_status": "exceeded",
            "burn_rate": 2.5,
            "current_complexity": 42,
            "baseline_complexity": 20,
        },
    ]
    r = analyze_repository(
        repo_root=_REPO_ROOT,
        run_id=_RUN,
        trace_id=_TRACE,
        complexity_budgets=budgets,
    )
    cbb = r["complexity_budget_by_module"]
    assert cbb["spectrum_systems/rge"]["budget_status"] == "healthy"
    assert cbb["spectrum_systems/modules/runtime"]["budget_status"] == "exceeded"


def test_mg_slices_reflected():
    r = analyze_repository(
        repo_root=_REPO_ROOT,
        run_id=_RUN,
        trace_id=_TRACE,
        mg_slices_present=["MG-01", "MG-02", "MG-03"],
    )
    assert "MG-01" in r["mg_slice_health"]["present"]
    assert len(r["mg_slice_health"]["present"]) == 3


def test_fragile_points_deduplicated():
    r = analyze_repository(
        repo_root=_REPO_ROOT,
        run_id=_RUN,
        trace_id=_TRACE,
        fragile_points=["mod/a.py", "mod/a.py", "mod/b.py"],
    )
    assert r["fragile_points"] == ["mod/a.py", "mod/b.py"]


def test_bottlenecks_identified():
    r = analyze_repository(repo_root=_REPO_ROOT, run_id=_RUN, trace_id=_TRACE)
    assert isinstance(r["bottlenecks"], list)
    for leg in r["bottlenecks"]:
        assert r["leg_saturation"][leg] >= 6


def test_stable_record_id_for_same_inputs():
    r1 = analyze_repository(repo_root=_REPO_ROOT, run_id=_RUN, trace_id=_TRACE)
    r2 = analyze_repository(repo_root=_REPO_ROOT, run_id=_RUN, trace_id=_TRACE)
    assert r1["record_id"] == r2["record_id"]
