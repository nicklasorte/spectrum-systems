"""Tests for RGE Self-Amender."""
from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.rge.rge_amender import (
    MAX_OSCILLATION_CYCLES,
    amend_roadmap,
)

_RUN = "run-am-001"
_TRACE = "trace-am-001"


def _roadmap(**ov):
    base = {"record_id": "RMR-A", "admitted_phases": []}
    return {**base, **ov}


def _redteam(findings=None):
    return {
        "record_id": "RTR-A",
        "findings": findings or [],
        "decision": "pass" if not findings else "block",
    }


def test_no_findings_no_amendment():
    r = amend_roadmap(
        roadmap=_roadmap(),
        redteam=_redteam(),
        run_id=_RUN,
        trace_id=_TRACE,
    )
    assert r["decision"] == "no_amendment"
    assert r["amendments"] == []
    validate_artifact(r, "rge_amendment_record")


def test_same_leg_batch_defer_amendment():
    findings = [{
        "finding_class": "same_leg_same_batch",
        "statement": "Leg EVL has 2 ADDs",
        "affected_phases": ["P1", "P2"],
        "owner": "TLC",
        "routing_reason": "class:same_leg_same_batch",
    }]
    r = amend_roadmap(
        roadmap=_roadmap(),
        redteam=_redteam(findings),
        run_id=_RUN,
        trace_id=_TRACE,
    )
    kinds = {a["amendment_type"] for a in r["amendments"]}
    assert "defer" in kinds
    assert r["decision"] == "apply"


def test_complexity_on_freeze_drop():
    findings = [{
        "finding_class": "complexity_on_freeze",
        "statement": "Budget frozen",
        "affected_phases": ["P1"],
        "owner": "TPA",
        "routing_reason": "class:complexity_on_freeze",
    }]
    r = amend_roadmap(
        roadmap=_roadmap(),
        redteam=_redteam(findings),
        run_id=_RUN,
        trace_id=_TRACE,
    )
    kinds = {a["amendment_type"] for a in r["amendments"]}
    assert "drop" in kinds


def test_deletion_guard_revise():
    findings = [{
        "finding_class": "deletion_guard_violation",
        "statement": "Missing citation",
        "affected_phases": ["DEL-1"],
        "owner": "GOV",
        "routing_reason": "class:deletion_guard_violation",
    }]
    r = amend_roadmap(
        roadmap=_roadmap(),
        redteam=_redteam(findings),
        run_id=_RUN,
        trace_id=_TRACE,
    )
    kinds = {a["amendment_type"] for a in r["amendments"]}
    assert "revise" in kinds


def test_canary_when_many_phases_touched():
    findings = [{
        "finding_class": "complexity_on_freeze",
        "statement": "Budget frozen",
        "affected_phases": ["P1", "P2", "P3", "P4", "P5"],
        "owner": "TPA",
        "routing_reason": "class:complexity_on_freeze",
    }]
    r = amend_roadmap(
        roadmap=_roadmap(),
        redteam=_redteam(findings),
        run_id=_RUN,
        trace_id=_TRACE,
    )
    assert r["rollout"].startswith("canary_")


def test_full_rollout_when_few_touched():
    findings = [{
        "finding_class": "complexity_on_freeze",
        "statement": "freeze",
        "affected_phases": ["P1"],
        "owner": "TPA",
        "routing_reason": "class:complexity_on_freeze",
    }]
    r = amend_roadmap(
        roadmap=_roadmap(),
        redteam=_redteam(findings),
        run_id=_RUN,
        trace_id=_TRACE,
    )
    assert r["rollout"] == "full"


def test_escalation_at_max_oscillation():
    r = amend_roadmap(
        roadmap=_roadmap(),
        redteam=_redteam(),
        run_id=_RUN,
        trace_id=_TRACE,
        oscillation_count=MAX_OSCILLATION_CYCLES,
    )
    assert r["decision"] == "escalate"
    assert r["escalated"] is True


def test_cycle_in_edges_blocks():
    r = amend_roadmap(
        roadmap=_roadmap(),
        redteam=_redteam(),
        run_id=_RUN,
        trace_id=_TRACE,
        additional_edges=[("A", "B"), ("B", "C"), ("C", "A")],
    )
    assert r["dag_ok"] is False
    assert r["decision"] == "block"


def test_dag_ok_when_no_cycle():
    r = amend_roadmap(
        roadmap=_roadmap(),
        redteam=_redteam(),
        run_id=_RUN,
        trace_id=_TRACE,
        additional_edges=[("A", "B"), ("B", "C")],
    )
    assert r["dag_ok"] is True


def test_red_team_pairing_adds_pair():
    findings = [{
        "finding_class": "red_team_pairing_missing",
        "statement": "No test phase",
        "affected_phases": ["P1"],
        "owner": "PQX",
        "routing_reason": "class:red_team_pairing_missing",
    }]
    r = amend_roadmap(
        roadmap=_roadmap(),
        redteam=_redteam(findings),
        run_id=_RUN,
        trace_id=_TRACE,
    )
    kinds = {a["amendment_type"] for a in r["amendments"]}
    assert "add_pair" in kinds


def test_mg21_violation_splits_session():
    findings = [{
        "finding_class": "mg_21_session_violation",
        "statement": "Too long",
        "affected_phases": ["P1", "P2"],
        "owner": "MG",
        "routing_reason": "class:mg_21_session_violation",
    }]
    r = amend_roadmap(
        roadmap=_roadmap(),
        redteam=_redteam(findings),
        run_id=_RUN,
        trace_id=_TRACE,
    )
    kinds = {a["amendment_type"] for a in r["amendments"]}
    assert "split_session" in kinds


def test_schema_validates():
    r = amend_roadmap(
        roadmap=_roadmap(), redteam=_redteam(), run_id=_RUN, trace_id=_TRACE
    )
    validate_artifact(r, "rge_amendment_record")
