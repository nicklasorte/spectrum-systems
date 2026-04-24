"""Tests for RGE Red-Teamer."""
from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.rge.rge_red_teamer import (
    red_team_roadmap,
    route_finding_owner,
)

_RUN = "run-rt-001"
_TRACE = "trace-rt-001"


def _phase(**overrides):
    base = {
        "phase_id": "P1",
        "name": "Wire EVL telemetry",
        "loop_leg": "EVL",
        "failure_prevented": "eval_coverage drops below 80%",
        "signal_improved": "eval_coverage rises to 90%",
    }
    return {**base, **overrides}


def _roadmap(phases):
    return {
        "record_id": "RMR-TEST",
        "admitted_phases": phases,
    }


def test_empty_roadmap_no_findings():
    r = red_team_roadmap(
        roadmap=_roadmap([]), run_id=_RUN, trace_id=_TRACE
    )
    assert r["decision"] == "pass"
    assert r["finding_count"] == 0
    validate_artifact(r, "rge_redteam_record")


def test_no_redteam_phase_flagged():
    r = red_team_roadmap(
        roadmap=_roadmap([_phase()]), run_id=_RUN, trace_id=_TRACE
    )
    classes = [f["finding_class"] for f in r["findings"]]
    assert "red_team_pairing_missing" in classes


def test_redteam_phase_satisfies_pairing():
    phases = [
        _phase(),
        _phase(phase_id="P2", name="Red-team EVL telemetry", phase_type="redteam"),
    ]
    r = red_team_roadmap(roadmap=_roadmap(phases), run_id=_RUN, trace_id=_TRACE)
    classes = [f["finding_class"] for f in r["findings"]]
    assert "red_team_pairing_missing" not in classes


def test_circular_failure_flagged():
    phases = [_phase(name="resolve failure X", failure_prevented="resolve failure x event")]
    r = red_team_roadmap(roadmap=_roadmap(phases), run_id=_RUN, trace_id=_TRACE)
    classes = [f["finding_class"] for f in r["findings"]]
    assert "circular_failure_chain" in classes


def test_same_leg_same_batch_flagged():
    phases = [
        _phase(phase_id="P1"),
        _phase(phase_id="P2", name="Another EVL phase"),
    ]
    r = red_team_roadmap(roadmap=_roadmap(phases), run_id=_RUN, trace_id=_TRACE)
    classes = [f["finding_class"] for f in r["findings"]]
    assert "same_leg_same_batch" in classes


def test_complexity_on_freeze_flagged():
    analysis = {
        "complexity_budget_by_module": {
            "mod/a": {"budget_status": "exceeded"},
        }
    }
    r = red_team_roadmap(
        roadmap=_roadmap([_phase()]),
        run_id=_RUN,
        trace_id=_TRACE,
        analysis=analysis,
    )
    classes = [f["finding_class"] for f in r["findings"]]
    assert "complexity_on_freeze" in classes


def test_deletion_guard_violation():
    phases = [
        _phase(phase_id="DEL-X", phase_type="delete", evidence_refs=["vague prose"])
    ]
    r = red_team_roadmap(roadmap=_roadmap(phases), run_id=_RUN, trace_id=_TRACE)
    classes = [f["finding_class"] for f in r["findings"]]
    assert "deletion_guard_violation" in classes


def test_deletion_with_good_refs_passes_deletion_check():
    phases = [
        _phase(
            phase_id="DEL-Y",
            phase_type="delete",
            evidence_refs=["complexity_budget:module/a.py"],
        )
    ]
    r = red_team_roadmap(roadmap=_roadmap(phases), run_id=_RUN, trace_id=_TRACE)
    classes = [f["finding_class"] for f in r["findings"]]
    assert "deletion_guard_violation" not in classes


def test_mg_21_session_violation_flagged():
    r = red_team_roadmap(
        roadmap=_roadmap([_phase()]),
        run_id=_RUN,
        trace_id=_TRACE,
        session_budget_hours=12.0,
    )
    classes = [f["finding_class"] for f in r["findings"]]
    assert "mg_21_session_violation" in classes


def test_findings_routed_to_owner():
    phases = [_phase()]
    r = red_team_roadmap(roadmap=_roadmap(phases), run_id=_RUN, trace_id=_TRACE)
    for f in r["findings"]:
        assert f["owner"]
        assert "class:" in f["routing_reason"]


def test_route_unknown_class_falls_back():
    assert route_finding_owner("fictional_class") == "RGE"


def test_decision_blocks_when_findings_present():
    r = red_team_roadmap(
        roadmap=_roadmap([_phase()]), run_id=_RUN, trace_id=_TRACE
    )
    assert r["decision"] == "block"
    assert r["finding_count"] > 0
