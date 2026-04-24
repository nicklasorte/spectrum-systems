"""Tests for RGE Roadmap Generator."""
from __future__ import annotations

from pathlib import Path

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.roadmap_stop_reasons import (
    CANONICAL_STOP_REASONS,
)
from spectrum_systems.rge.analysis_engine import analyze_repository
from spectrum_systems.rge.roadmap_generator import generate_roadmap

_RUN = "run-gen-001"
_TRACE = "trace-gen-001"
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _analysis(**overrides):
    a = analyze_repository(repo_root=_REPO_ROOT, run_id=_RUN, trace_id=_TRACE)
    for k, v in overrides.items():
        a[k] = v
    return a


def _good_candidate(**overrides):
    base = {
        "phase_id": "P-EXTRA",
        "name": "Wire EVL coverage metric",
        "failure_prevented": (
            "Phases shipping without eval coverage drops eval_coverage_rate "
            "below 80% threshold"
        ),
        "signal_improved": "eval_coverage_rate climbs from 62% to 90%",
        "loop_leg": "EVL",
        "evidence_refs": ["drift_signal_record:DS-0041"],
        "runbook": "docs/runbooks/rge_debuggability_gate_failures.md",
        "stop_reason": CANONICAL_STOP_REASONS[0],
    }
    return {**base, **overrides}


def test_empty_analysis_produces_empty_roadmap():
    a = _analysis(
        complexity_budget_by_module={},
        active_drift_legs=[],
    )
    r = generate_roadmap(analysis=a, run_id=_RUN, trace_id=_TRACE)
    assert r["admitted_count"] == 0
    assert r["candidate_count"] == 0
    validate_artifact(r, "rge_roadmap_record")


def test_exceeded_budget_generates_delete_phase():
    a = _analysis(
        complexity_budget_by_module={
            "spectrum_systems/some/module.py": {
                "budget_status": "exceeded",
                "current_complexity": 120,
                "baseline_complexity": 80,
                "burn_rate": 3.0,
            }
        },
        active_drift_legs=[],
    )
    r = generate_roadmap(analysis=a, run_id=_RUN, trace_id=_TRACE)
    assert r["admitted_count"] >= 1
    names = [p["name"] for p in r["admitted_phases"]]
    assert any("Delete" in n for n in names)


def test_drift_leg_generates_strengthen_phase():
    a = _analysis(active_drift_legs=["EVL"])
    r = generate_roadmap(analysis=a, run_id=_RUN, trace_id=_TRACE)
    names = [p["name"] for p in r["admitted_phases"]]
    assert any(n.startswith("STRENGTHEN-EVL") for n in names)


def test_extra_candidates_admitted():
    a = _analysis(active_drift_legs=[], complexity_budget_by_module={})
    r = generate_roadmap(
        analysis=a,
        run_id=_RUN,
        trace_id=_TRACE,
        extra_candidates=[_good_candidate()],
    )
    assert r["admitted_count"] == 1


def test_candidate_without_improvement_signal_blocked():
    a = _analysis(active_drift_legs=[], complexity_budget_by_module={})
    bad = _good_candidate(
        phase_id="P-BAD",
        failure_prevented="Random unrelated failure condition happens sometimes",
        signal_improved="timing gets faster by 30 ms",
    )
    r = generate_roadmap(
        analysis=a,
        run_id=_RUN,
        trace_id=_TRACE,
        extra_candidates=[bad],
    )
    assert r["admitted_count"] == 0
    assert r["blocked_count"] == 1
    assert r["blocked_proposals"][0]["block_gate"] == "improvement_fingerprint"


def test_bad_candidate_blocked_by_filter():
    a = _analysis(active_drift_legs=[], complexity_budget_by_module={})
    bad = _good_candidate(loop_leg="MAGIC", phase_id="P-LEG-BAD")
    r = generate_roadmap(
        analysis=a,
        run_id=_RUN,
        trace_id=_TRACE,
        extra_candidates=[bad],
    )
    assert r["admitted_count"] == 0
    assert r["blocked_count"] == 1


def test_admitted_phase_carries_filter_result():
    a = _analysis(active_drift_legs=[], complexity_budget_by_module={})
    r = generate_roadmap(
        analysis=a,
        run_id=_RUN,
        trace_id=_TRACE,
        extra_candidates=[_good_candidate()],
    )
    assert "filter_result" in r["admitted_phases"][0]


def test_content_hash_is_stable():
    a = _analysis(active_drift_legs=[], complexity_budget_by_module={})
    r1 = generate_roadmap(
        analysis=a,
        run_id=_RUN,
        trace_id=_TRACE,
        extra_candidates=[_good_candidate()],
    )
    r2 = generate_roadmap(
        analysis=a,
        run_id=_RUN,
        trace_id=_TRACE,
        extra_candidates=[_good_candidate()],
    )
    assert r1["content_hash"] == r2["content_hash"]


def test_stop_reason_catalog_included():
    a = _analysis()
    r = generate_roadmap(analysis=a, run_id=_RUN, trace_id=_TRACE)
    assert r["stop_reason_catalog"]
    assert r["diminishing_returns_sentinel"] in r["stop_reason_catalog"]
    assert r["invalid_state_sentinel"] in r["stop_reason_catalog"]


def test_multiple_drift_legs_multiple_strengthens():
    a = _analysis(active_drift_legs=["EVL", "TPA", "CDE"])
    r = generate_roadmap(analysis=a, run_id=_RUN, trace_id=_TRACE)
    admitted_names = [p["name"] for p in r["admitted_phases"]]
    for leg in ("EVL", "TPA", "CDE"):
        assert any(leg in n for n in admitted_names)


def test_candidate_count_matches_all_proposals():
    a = _analysis(
        complexity_budget_by_module={
            "mod/a": {"budget_status": "exceeded", "current_complexity": 10, "baseline_complexity": 5},
        },
        active_drift_legs=["EVL"],
    )
    r = generate_roadmap(
        analysis=a,
        run_id=_RUN,
        trace_id=_TRACE,
        extra_candidates=[_good_candidate()],
    )
    assert r["candidate_count"] == r["admitted_count"] + r["blocked_count"]


def test_saturated_leg_blocks_extra_candidate():
    a = _analysis(active_drift_legs=[], complexity_budget_by_module={})
    r = generate_roadmap(
        analysis=a,
        run_id=_RUN,
        trace_id=_TRACE,
        extra_candidates=[_good_candidate()],
        current_leg_counts={"EVL": 8},
    )
    assert r["admitted_count"] == 0
    assert r["blocked_count"] == 1


def test_schema_validates():
    a = _analysis()
    r = generate_roadmap(analysis=a, run_id=_RUN, trace_id=_TRACE)
    validate_artifact(r, "rge_roadmap_record")


def test_record_references_analysis_id():
    a = _analysis()
    r = generate_roadmap(analysis=a, run_id=_RUN, trace_id=_TRACE)
    assert r["analysis_record_id"] == a["record_id"]


def test_vague_candidate_filtered_at_gate_1():
    a = _analysis(active_drift_legs=[], complexity_budget_by_module={})
    vague = _good_candidate(
        phase_id="P-VAGUE",
        failure_prevented="make eval better",
        signal_improved="general improvement",
    )
    r = generate_roadmap(
        analysis=a,
        run_id=_RUN,
        trace_id=_TRACE,
        extra_candidates=[vague],
    )
    assert r["admitted_count"] == 0
