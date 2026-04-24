"""Tests for RGE Debuggability Gate (Principle 3)."""
from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.roadmap_stop_reasons import (
    CANONICAL_STOP_REASONS,
)
from spectrum_systems.rge.debuggability_gate import (
    EXPLAINABILITY_THRESHOLD,
    THREE_LS_GLOSSARY,
    assess_debuggability,
)

_RUN = "run-dbg-001"
_TRACE = "trace-dbg-001"


def _full() -> dict:
    return {
        "phase_id": "P3",
        "name": "Add EVL coverage metric",
        "evidence_refs": [
            "drift_signal_record:DS-0041",
            "complexity_budget:CB-0012",
        ],
        "runbook": "docs/runbooks/rge_debuggability_gate_failures.md",
        "stop_reason": CANONICAL_STOP_REASONS[0],
        "failure_prevented": "Phases shipping without eval coverage drops eval_coverage_rate below 80%",
        "signal_improved": "eval_coverage_rate climbs from 62% to 90%",
    }


def test_full_phase_passes():
    r = assess_debuggability(_full(), run_id=_RUN, trace_id=_TRACE)
    assert r["decision"] == "pass"
    assert r["explainability_score"] >= EXPLAINABILITY_THRESHOLD
    assert r["gaps"] == []
    assert r["principle"] == "optimize_for_debuggability"


def test_missing_evidence_refs_flagged():
    phase = _full()
    phase["evidence_refs"] = []
    r = assess_debuggability(phase, run_id=_RUN, trace_id=_TRACE)
    assert any("evidence_refs" in g for g in r["gaps"])


def test_prose_only_evidence_refs_flagged():
    phase = _full()
    phase["evidence_refs"] = ["something vague"]
    r = assess_debuggability(phase, run_id=_RUN, trace_id=_TRACE)
    assert any("evidence_refs" in g for g in r["gaps"])


def test_missing_runbook_flagged():
    phase = _full()
    phase["runbook"] = ""
    r = assess_debuggability(phase, run_id=_RUN, trace_id=_TRACE)
    assert any("runbook" in g for g in r["gaps"])


def test_invalid_stop_reason_flagged():
    phase = _full()
    phase["stop_reason"] = "made_up_reason"
    r = assess_debuggability(phase, run_id=_RUN, trace_id=_TRACE)
    assert any("stop_reason" in g for g in r["gaps"])


def test_short_failure_prevented_flagged():
    phase = _full()
    phase["failure_prevented"] = "short"
    r = assess_debuggability(phase, run_id=_RUN, trace_id=_TRACE)
    assert any("failure_prevented" in g for g in r["gaps"])


def test_no_number_in_signal_flagged():
    phase = _full()
    phase["signal_improved"] = "makes coverage better"
    r = assess_debuggability(phase, run_id=_RUN, trace_id=_TRACE)
    assert any("signal_improved" in g for g in r["gaps"])


def test_returns_for_rewrite_when_below_threshold():
    phase = {"phase_id": "bad", "name": "Vague"}
    r = assess_debuggability(phase, run_id=_RUN, trace_id=_TRACE)
    assert r["decision"] == "return_for_rewrite"
    assert r["explainability_score"] < EXPLAINABILITY_THRESHOLD


def test_glossary_injected_for_references():
    phase = _full()
    phase["name"] = "Wire EVL through CDE"
    r = assess_debuggability(phase, run_id=_RUN, trace_id=_TRACE)
    systems = {g["system"] for g in r["glossary"]}
    assert "EVL" in systems
    assert "CDE" in systems


def test_glossary_entries_match_canonical_definitions():
    phase = _full()
    r = assess_debuggability(phase, run_id=_RUN, trace_id=_TRACE)
    for entry in r["glossary"]:
        assert THREE_LS_GLOSSARY[entry["system"]] == entry["definition"]


def test_record_schema_validates():
    r = assess_debuggability(_full(), run_id=_RUN, trace_id=_TRACE)
    validate_artifact(r, "debuggability_assessment_record")


def test_record_includes_runbook_path():
    r = assess_debuggability(_full(), run_id=_RUN, trace_id=_TRACE)
    assert "rge_debuggability_gate" in r["runbook"] or r["runbook"].endswith(".md")
