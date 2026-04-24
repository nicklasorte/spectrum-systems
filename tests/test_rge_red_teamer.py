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


def test_schema_version_is_1_1_0():
    r = red_team_roadmap(
        roadmap=_roadmap([_phase()]), run_id=_RUN, trace_id=_TRACE
    )
    assert r["schema_version"] == "1.1.0"


def test_findings_routed_through_rqx():
    """Each finding carries a schema-validated RQX routing record."""
    r = red_team_roadmap(roadmap=_roadmap([_phase()]), run_id=_RUN, trace_id=_TRACE)
    assert r["findings"]
    for f in r["findings"]:
        assert "rqx_routing" in f
        rr = f["rqx_routing"]
        assert rr["rqx_routed"] is True
        assert rr["rqx_class"] in {
            "interpretation", "repair_planning", "decision_quality",
            "enforcement_mismatch", "execution_trace", "trust_policy",
        }
        assert rr["finding_id"].startswith("rqx-find-")
        assert rr["routing_ref"].startswith("redteam_finding_record:")


def test_canonical_3ls_owners_replace_local_labels():
    """Owners come from RQX's _OWNER_BY_CLASS, not the old local map."""
    # red_team_pairing_missing -> execution_trace -> PQX (unchanged)
    # mg_21_session_violation  -> interpretation  -> RIL (was MG)
    r = red_team_roadmap(
        roadmap=_roadmap([_phase()]),
        run_id=_RUN,
        trace_id=_TRACE,
        session_budget_hours=12.0,
    )
    by_class = {f["finding_class"]: f for f in r["findings"]}
    assert by_class["red_team_pairing_missing"]["owner"] == "PQX"
    assert by_class["mg_21_session_violation"]["owner"] == "RIL"


def test_must_fix_warn_split():
    """red_team_pairing is must_fix; mg_21_session is warn (advisory)."""
    r = red_team_roadmap(
        roadmap=_roadmap([_phase()]),
        run_id=_RUN,
        trace_id=_TRACE,
        session_budget_hours=12.0,
    )
    by_class = {f["finding_class"]: f for f in r["findings"]}
    assert by_class["red_team_pairing_missing"]["must_fix"] is True
    assert by_class["mg_21_session_violation"]["must_fix"] is False
    assert r["must_fix_count"] >= 1
    assert r["warn_count"] >= 1
    assert r["finding_count"] == r["must_fix_count"] + r["warn_count"]


def test_warn_only_findings_do_not_block():
    """A roadmap with only warn findings should pass; old behavior blocked."""
    # Pair the EVL phase with a red-team phase (clears red_team_pairing must_fix).
    # The redteam phase satisfies pairing but its loop_leg='EVL' would also
    # collide with the ADD phase under same_leg_same_batch — so we put the
    # redteam phase on a different leg. Remaining: mg_21_session_violation (warn).
    phases = [
        _phase(),
        _phase(
            phase_id="P2",
            name="Red-team EVL telemetry",
            phase_type="redteam",
            loop_leg="OBS",
        ),
    ]
    r = red_team_roadmap(
        roadmap=_roadmap(phases),
        run_id=_RUN,
        trace_id=_TRACE,
        session_budget_hours=12.0,
    )
    classes = {f["finding_class"] for f in r["findings"]}
    # Only warn-class findings should be present
    must_fix_classes = {
        "red_team_pairing_missing",
        "circular_failure_chain",
        "complexity_on_freeze",
        "deletion_guard_violation",
    }
    assert not (classes & must_fix_classes), f"unexpected must_fix in {classes}"
    assert "mg_21_session_violation" in classes
    assert r["must_fix_count"] == 0
    assert r["warn_count"] >= 1
    assert r["decision"] == "pass"
    assert r["roadmap_approved"] is True


def test_roadmap_approved_false_when_must_fix_present():
    r = red_team_roadmap(roadmap=_roadmap([_phase()]), run_id=_RUN, trace_id=_TRACE)
    assert r["must_fix_count"] >= 1
    assert r["roadmap_approved"] is False
    assert r["decision"] == "block"
