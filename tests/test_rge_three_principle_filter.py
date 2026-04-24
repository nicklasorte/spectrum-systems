"""Tests for RGE Three-Principle Filter (composition of gates 1-3)."""
from __future__ import annotations

from spectrum_systems.modules.runtime.roadmap_stop_reasons import (
    CANONICAL_STOP_REASONS,
)
from spectrum_systems.rge.three_principle_filter import (
    FilterResult,
    apply_three_principle_filter,
)

_RUN = "run-flt-001"
_TRACE = "trace-flt-001"


def _full_phase(**overrides) -> dict:
    base = {
        "phase_id": "P-OK",
        "name": "Wire EVL telemetry",
        "failure_prevented": "Phases shipping without eval coverage - eval_coverage_rate below 80%",
        "signal_improved": "eval_coverage_rate climbs from 62% to 90%",
        "loop_leg": "EVL",
        "evidence_refs": [
            "drift_signal_record:DS-0041",
            "complexity_budget:CB-0012",
        ],
        "runbook": "docs/runbooks/rge_debuggability_gate_failures.md",
        "stop_reason": CANONICAL_STOP_REASONS[0],
    }
    return {**base, **overrides}


def test_admitted_phase_full_pass():
    r = apply_three_principle_filter(_full_phase(), run_id=_RUN, trace_id=_TRACE)
    assert r.admitted
    assert r.block_gate is None
    assert not r.needs_rewrite
    assert r.justification_record is not None
    assert r.loop_record is not None
    assert r.debuggability_record is not None


def test_blocked_at_gate_1_justification():
    r = apply_three_principle_filter(
        _full_phase(failure_prevented=""), run_id=_RUN, trace_id=_TRACE
    )
    assert not r.admitted
    assert r.block_gate == "justification"
    assert r.justification_record is None
    assert r.loop_record is None
    assert r.debuggability_record is None


def test_blocked_at_gate_2_loop():
    r = apply_three_principle_filter(
        _full_phase(),
        run_id=_RUN,
        trace_id=_TRACE,
        active_drift_legs=["EVL"],
    )
    assert not r.admitted
    assert r.block_gate == "loop"
    assert r.justification_record is not None
    assert r.loop_record is None
    assert r.debuggability_record is None


def test_admitted_with_rewrite_gaps():
    phase = _full_phase()
    phase["evidence_refs"] = []
    phase["runbook"] = ""
    phase["stop_reason"] = "not_a_real_reason"
    r = apply_three_principle_filter(phase, run_id=_RUN, trace_id=_TRACE)
    assert r.admitted
    assert r.needs_rewrite
    assert any("evidence_refs" in g for g in r.rewrite_gaps)


def test_deletion_phase_passes_all_three():
    delete_phase = _full_phase(
        phase_id="DEL-1",
        name="Delete unused monitoring abstraction",
        failure_prevented="Complexity budget exceeded - 3 sustained regressions in abstraction_growth",
        signal_improved="complexity_score drops by 12 points below 80 threshold",
        loop_leg="TPA",
        phase_type="delete",
    )
    r = apply_three_principle_filter(delete_phase, run_id=_RUN, trace_id=_TRACE)
    assert r.admitted


def test_deletion_phase_bypasses_saturation():
    delete_phase = _full_phase(
        phase_id="DEL-2", phase_type="delete", loop_leg="EVL"
    )
    r = apply_three_principle_filter(
        delete_phase,
        run_id=_RUN,
        trace_id=_TRACE,
        current_leg_counts={"EVL": 8},
    )
    assert r.admitted


def test_strengthen_phase_admitted_on_drift_leg():
    phase = _full_phase(phase_type="strengthen", name="STRENGTHEN-EVL telemetry")
    r = apply_three_principle_filter(
        phase, run_id=_RUN, trace_id=_TRACE, active_drift_legs=["EVL"]
    )
    assert r.admitted


def test_short_circuit_at_gate_1_skips_gates_2_and_3():
    r = apply_three_principle_filter(
        _full_phase(loop_leg=""), run_id=_RUN, trace_id=_TRACE
    )
    assert not r.admitted
    assert r.block_gate == "justification"


def test_filter_result_is_stable():
    phase = _full_phase()
    r1 = apply_three_principle_filter(phase, run_id=_RUN, trace_id=_TRACE)
    r2 = apply_three_principle_filter(phase, run_id=_RUN, trace_id=_TRACE)
    assert r1.admitted == r2.admitted
    assert r1.phase_id == r2.phase_id


def test_filter_result_to_dict():
    r = apply_three_principle_filter(_full_phase(), run_id=_RUN, trace_id=_TRACE)
    d = r.to_dict()
    assert d["artifact_type"] == "filter_result"
    assert d["admitted"] is True
    assert "phase_id" in d
    assert "phase_name" in d


def test_block_gate_loop_carries_gate_1_record():
    r = apply_three_principle_filter(
        _full_phase(),
        run_id=_RUN,
        trace_id=_TRACE,
        active_drift_legs=["EVL"],
    )
    assert r.justification_record is not None
    assert r.justification_record["decision"] == "allow"


def test_debuggability_glossary_present_for_admitted():
    phase = _full_phase(name="Wire EVL through CDE")
    r = apply_three_principle_filter(phase, run_id=_RUN, trace_id=_TRACE)
    assert r.admitted
    systems = {g["system"] for g in r.debuggability_record["glossary"]}
    assert "EVL" in systems
    assert "CDE" in systems


def test_block_reason_is_populated_on_gate_1_block():
    r = apply_three_principle_filter(
        _full_phase(failure_prevented=""), run_id=_RUN, trace_id=_TRACE
    )
    assert r.block_reason is not None
    assert "Principle 1" in r.block_reason


def test_block_reason_is_populated_on_gate_2_block():
    r = apply_three_principle_filter(
        _full_phase(),
        run_id=_RUN,
        trace_id=_TRACE,
        active_drift_legs=["EVL"],
    )
    assert r.block_reason is not None
    assert "Principle 2" in r.block_reason


def test_admitted_phase_all_three_records_valid():
    r = apply_three_principle_filter(_full_phase(), run_id=_RUN, trace_id=_TRACE)
    assert r.justification_record["decision"] == "allow"
    assert r.loop_record["decision"] == "allow"
    assert r.debuggability_record["decision"] in ("pass", "return_for_rewrite")
