"""Tests for RGE Analysis Engine (Wave 0 repo audit)."""
from __future__ import annotations

from pathlib import Path

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.rge.analysis_engine import (
    _audit_fragile_point_signals,
    _count_silent_excepts,
    _count_stubs,
    analyze_repository,
)

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


def test_schema_version_is_1_1_0():
    r = analyze_repository(repo_root=_REPO_ROOT, run_id=_RUN, trace_id=_TRACE)
    assert r["schema_version"] == "1.1.0"


def test_wave_status_in_range_and_reflects_indicators():
    r = analyze_repository(repo_root=_REPO_ROOT, run_id=_RUN, trace_id=_TRACE)
    assert 0 <= r["wave_status"] <= 4
    # This repo has the RGE orchestrator indicator, so wave should be 4.
    assert r["wave_status"] == 4


def test_entropy_vectors_have_all_seven_keys_and_valid_values(tmp_path):
    r = analyze_repository(repo_root=_REPO_ROOT, run_id=_RUN, trace_id=_TRACE)
    expected = {
        "decision_entropy",
        "silent_drift",
        "exception_accumulation",
        "hidden_logic_creep",
        "evaluation_blind_spots",
        "overconfidence_risk",
        "loss_of_causality",
    }
    assert set(r["entropy_vectors"].keys()) == expected
    for v in r["entropy_vectors"].values():
        assert v in {"clean", "warn", "critical"}


def test_autonomy_gate_derived_from_maturity(tmp_path):
    # Empty tmp dir => maturity 0 => cannot operate, shadow mode
    r = analyze_repository(repo_root=tmp_path, run_id=_RUN, trace_id=_TRACE)
    assert r["rge_can_operate"] is False
    assert r["rge_max_autonomy"] == "shadow"
    assert r["entropy_vectors"]["overconfidence_risk"] == "warn"


def test_ast_detectors_find_stubs_and_silent_excepts(tmp_path):
    stub_file = tmp_path / "mod_stubby.py"
    stub_file.write_text(
        "def a(): pass\n"
        "def b(): pass\n"
        "def c(): pass\n"
        "def d(): pass\n"
        "def e(): pass\n"
    )
    silent_file = tmp_path / "mod_silent.py"
    silent_file.write_text(
        "def x():\n"
        "    try:\n        a = 1\n    except Exception:\n        pass\n"
        "def y():\n"
        "    try:\n        b = 2\n    except Exception:\n        ...\n"
        "def z():\n"
        "    try:\n        c = 3\n    except Exception:\n        pass\n"
    )

    assert _count_stubs(stub_file.read_text()) == 5
    assert _count_silent_excepts(silent_file.read_text()) == 3

    signals = _audit_fragile_point_signals(tmp_path)
    types = {(s["type"], s["file"]) for s in signals}
    assert ("stub_heavy", "mod_stubby.py") in types
    assert ("silent_excepts", "mod_silent.py") in types
    for s in signals:
        assert isinstance(s["count"], int)
        assert s["count"] >= 0
