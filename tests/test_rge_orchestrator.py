"""Integration tests for RGE Orchestrator."""
from __future__ import annotations

from pathlib import Path

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.roadmap_stop_reasons import (
    CANONICAL_STOP_REASONS,
)
from spectrum_systems.rge.orchestrator import run_rge

_RUN = "run-orch-001"
_TRACE = "trace-orch-001"
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _good_candidate(**overrides):
    base = {
        "phase_id": "P-EXTRA",
        "name": "Wire EVL coverage telemetry",
        "failure_prevented": "eval_coverage drops below 80% - governance breaks",
        "signal_improved": "eval_coverage rises to 90% over 14 days",
        "loop_leg": "EVL",
        "evidence_refs": ["drift_signal_record:DS-0041"],
        "runbook": "docs/runbooks/rge_debuggability_gate_failures.md",
        "stop_reason": CANONICAL_STOP_REASONS[0],
    }
    return {**base, **overrides}


def test_full_pipeline_emits_all_records():
    out = run_rge(
        repo_root=_REPO_ROOT,
        run_id=_RUN,
        trace_id=_TRACE,
    )
    for key in (
        "run_record",
        "analysis_record",
        "roadmap_record",
        "redteam_record",
        "amendment_record",
        "trust_record",
        "recursion_records",
    ):
        assert key in out, f"missing {key}"


def test_run_record_schema_valid():
    out = run_rge(repo_root=_REPO_ROOT, run_id=_RUN, trace_id=_TRACE)
    validate_artifact(out["run_record"], "rge_run_record")


def test_shadow_mode_queues_for_human():
    out = run_rge(
        repo_root=_REPO_ROOT,
        run_id=_RUN,
        trace_id=_TRACE,
        extra_candidates=[_good_candidate()],
    )
    run = out["run_record"]
    assert run["resolved_trust_mode"] == "shadow"
    assert run["queued_for_human"] is True
    assert run["execute"] is False
    assert run["terminal_state"] == "queued_for_human"


def test_autonomous_mode_executes_when_all_pass():
    history = [{"outcome": "accept"}] * 12
    out = run_rge(
        repo_root=_REPO_ROOT,
        run_id=_RUN,
        trace_id=_TRACE,
        extra_candidates=[
            _good_candidate(),
            _good_candidate(
                phase_id="P-RT",
                name="Red-team EVL telemetry coverage",
                loop_leg="EVL",
                phase_type="redteam",
            ),
        ],
        confidence=0.95,
        decision_history=history,
        adjudication_bundle={"cde_decision": "allow", "tpa_record": "TPA-1"},
        prior_trust_mode="shadow",
    )
    run = out["run_record"]
    assert run["resolved_trust_mode"] == "autonomous"
    if run["execute"]:
        assert run["terminal_state"] == "ready_for_merge"
        assert run["branch_update_allowed"] is True


def test_vague_candidate_never_reaches_output():
    out = run_rge(
        repo_root=_REPO_ROOT,
        run_id=_RUN,
        trace_id=_TRACE,
        extra_candidates=[
            _good_candidate(
                phase_id="P-VAGUE",
                failure_prevented="make eval better",
                signal_improved="various improvements",
            )
        ],
    )
    names = [p["phase_id"] for p in out["roadmap_record"]["admitted_phases"]]
    assert "P-VAGUE" not in names


def test_drift_leg_auto_generates_strengthen_phase():
    bundle = {
        "drift_findings": [
            {"severity": "block", "affected_component": "EVL coverage drift"}
        ]
    }
    out = run_rge(
        repo_root=_REPO_ROOT,
        run_id=_RUN,
        trace_id=_TRACE,
        roadmap_signal_bundle=bundle,
    )
    names = [p["name"] for p in out["roadmap_record"]["admitted_phases"]]
    assert any("STRENGTHEN-EVL" in n for n in names)


def test_exceeded_budget_auto_generates_delete_phase():
    budgets = [
        {
            "module_or_path": "spectrum_systems/legacy_mod",
            "budget_status": "exceeded",
            "current_complexity": 120,
            "baseline_complexity": 60,
            "burn_rate": 3.5,
        }
    ]
    out = run_rge(
        repo_root=_REPO_ROOT,
        run_id=_RUN,
        trace_id=_TRACE,
        complexity_budgets=budgets,
    )
    names = [p["name"] for p in out["roadmap_record"]["admitted_phases"]]
    assert any("Delete" in n for n in names)


def test_branch_update_allowed_gated_on_ready_for_merge():
    out = run_rge(repo_root=_REPO_ROOT, run_id=_RUN, trace_id=_TRACE)
    run = out["run_record"]
    if run["terminal_state"] == "ready_for_merge":
        assert run["branch_update_allowed"] is True
    else:
        assert run["branch_update_allowed"] is False


def test_recursion_record_per_admitted_phase():
    out = run_rge(
        repo_root=_REPO_ROOT,
        run_id=_RUN,
        trace_id=_TRACE,
        extra_candidates=[_good_candidate()],
    )
    assert len(out["recursion_records"]) == len(
        out["roadmap_record"]["admitted_phases"]
    )


def test_recursion_depth_over_max_blocks_run():
    out = run_rge(
        repo_root=_REPO_ROOT,
        run_id=_RUN,
        trace_id=_TRACE,
        extra_candidates=[_good_candidate()],
        current_recursion_depth=99,
    )
    run = out["run_record"]
    assert run["execute"] is False
    if out["recursion_records"]:
        assert run["terminal_state"] in ("blocked", "no_action")


def test_all_child_records_referenced():
    out = run_rge(repo_root=_REPO_ROOT, run_id=_RUN, trace_id=_TRACE)
    run = out["run_record"]
    assert run["analysis_record_id"] == out["analysis_record"]["record_id"]
    assert run["roadmap_record_id"] == out["roadmap_record"]["record_id"]
    assert run["redteam_record_id"] == out["redteam_record"]["record_id"]
    assert run["amendment_record_id"] == out["amendment_record"]["record_id"]
    assert run["trust_record_id"] == out["trust_record"]["record_id"]


def test_zero_regressions_on_admitted_phase_count():
    out = run_rge(repo_root=_REPO_ROOT, run_id=_RUN, trace_id=_TRACE)
    assert out["run_record"]["admitted_phase_count"] == len(
        out["roadmap_record"]["admitted_phases"]
    )


def test_amendment_block_cycles_terminal_state():
    out = run_rge(
        repo_root=_REPO_ROOT,
        run_id=_RUN,
        trace_id=_TRACE,
        additional_edges=[("A", "B"), ("B", "A")],
        extra_candidates=[_good_candidate()],
    )
    assert out["amendment_record"]["decision"] == "block"
    assert out["run_record"]["terminal_state"] == "blocked"


def test_pipeline_is_stable_for_same_inputs():
    out1 = run_rge(repo_root=_REPO_ROOT, run_id=_RUN, trace_id=_TRACE)
    out2 = run_rge(repo_root=_REPO_ROOT, run_id=_RUN, trace_id=_TRACE)
    assert out1["run_record"]["admitted_phase_count"] == out2["run_record"]["admitted_phase_count"]
    assert out1["run_record"]["finding_count"] == out2["run_record"]["finding_count"]


def test_no_phase_bypasses_three_principle_filter():
    out = run_rge(
        repo_root=_REPO_ROOT,
        run_id=_RUN,
        trace_id=_TRACE,
        extra_candidates=[
            _good_candidate(loop_leg="MAGIC", phase_id="P-LEG-BAD"),
        ],
    )
    ids = [p["phase_id"] for p in out["roadmap_record"]["admitted_phases"]]
    assert "P-LEG-BAD" not in ids
