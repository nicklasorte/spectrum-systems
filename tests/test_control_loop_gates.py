"""Unit tests for AdmissionGate, EvalGate, PromotionGate — Phase 2.3 (11 tests + RT-2.3)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spectrum_systems.execution.admission_gate import AdmissionGate
from spectrum_systems.evaluation.eval_gate import EvalGate
from spectrum_systems.promotion.promotion_gate import PromotionGate


# ===========================================================================
# AdmissionGate Tests
# ===========================================================================


@pytest.fixture
def adm():
    return AdmissionGate()


def _valid_input():
    return {"artifact_type": "context_bundle", "trace_id": "TRC-VALID-001"}


# ---------------------------------------------------------------------------
# Test 1: Valid input is admitted
# ---------------------------------------------------------------------------


def test_admission_valid_input_allowed(adm):
    result = adm.check(_valid_input())
    assert result["decision"] == "allow"
    assert result["blocking_checks"] == []


# ---------------------------------------------------------------------------
# Test 2: RT-2.3 Admission: invalid schema (missing artifact_type) → blocked
# ---------------------------------------------------------------------------


def test_admission_missing_schema_fields_blocked(adm):
    result = adm.check({"trace_id": "TRC-NO-TYPE"})
    assert result["decision"] == "block"
    assert "input_schema_valid" in result["blocking_checks"]


# ---------------------------------------------------------------------------
# Test 3: RT-2.3 Admission: corrupted context → blocked
# ---------------------------------------------------------------------------


def test_admission_corrupted_context_blocked(adm):
    inp = {**_valid_input(), "_corrupted": True}
    result = adm.check(inp)
    assert result["decision"] == "block"
    assert "context_integrity" in result["blocking_checks"]


# ---------------------------------------------------------------------------
# Test 4: RT-2.3 Admission: security flag → blocked
# ---------------------------------------------------------------------------


def test_admission_security_blocked(adm):
    inp = {**_valid_input(), "security_blocked": True}
    result = adm.check(inp)
    assert result["decision"] == "block"
    assert "security_admission" in result["blocking_checks"]


# ---------------------------------------------------------------------------
# Test 5: RT-2.3 Admission: resource over limit → blocked
# ---------------------------------------------------------------------------


def test_admission_resource_limit_blocked():
    gate = AdmissionGate(resource_limit=100)
    inp = {**_valid_input(), "resource_units": 200}
    result = gate.check(inp)
    assert result["decision"] == "block"
    assert "resource_availability" in result["blocking_checks"]


# ===========================================================================
# EvalGate Tests
# ===========================================================================


@pytest.fixture
def eval_gate():
    return EvalGate()


def _eval_results(passed, total, trace_id="TRC-EVAL"):
    return {"passed": passed, "total": total, "trace_id": trace_id}


# ---------------------------------------------------------------------------
# Test 6: RT-2.3 Eval: 94% pass rate → blocked
# ---------------------------------------------------------------------------


def test_eval_gate_94pct_blocked(eval_gate):
    result = eval_gate.check(_eval_results(94, 100))
    assert result["decision"] == "block"
    assert "eval_pass_rate_met" in result["blocking_checks"]


# ---------------------------------------------------------------------------
# Test 7: RT-2.3 Eval: 96% pass rate → allowed
# ---------------------------------------------------------------------------


def test_eval_gate_96pct_allowed(eval_gate):
    result = eval_gate.check(_eval_results(96, 100))
    assert result["decision"] == "allow"
    assert result["blocking_checks"] == []


# ---------------------------------------------------------------------------
# Test 8: Eval: exactly 95% → allowed (boundary)
# ---------------------------------------------------------------------------


def test_eval_gate_exactly_threshold_allowed(eval_gate):
    result = eval_gate.check(_eval_results(95, 100))
    assert result["decision"] == "allow"


# ---------------------------------------------------------------------------
# Test 9: Eval: zero total → blocked (no evals run)
# ---------------------------------------------------------------------------


def test_eval_gate_zero_total_blocked(eval_gate):
    result = eval_gate.check(_eval_results(0, 0))
    assert result["decision"] == "block"


# ===========================================================================
# PromotionGate Tests
# ===========================================================================


@pytest.fixture
def promo():
    return PromotionGate()


def _valid_promotion():
    return {
        "trace_id": "TRC-PROMO",
        "lineage_complete": True,
        "replay_deterministic": True,
        "prior_gates_passed": True,
        "security_approved": True,
        "slo_compliant": True,
    }


# ---------------------------------------------------------------------------
# Test 10: RT-2.3 Chain: all checks pass → allowed
# ---------------------------------------------------------------------------


def test_promotion_all_pass_allowed(promo):
    result = promo.check(_valid_promotion())
    assert result["decision"] == "allow"
    assert result["blocking_checks"] == []


# ---------------------------------------------------------------------------
# Test 11: RT-2.3 Promotion: missing lineage → blocked
# ---------------------------------------------------------------------------


def test_promotion_missing_lineage_blocked(promo):
    req = {**_valid_promotion(), "lineage_complete": False}
    result = promo.check(req)
    assert result["decision"] == "block"
    assert "lineage_complete" in result["blocking_checks"]


# ---------------------------------------------------------------------------
# RT-2.3: Promotion: failed replay → blocked
# ---------------------------------------------------------------------------


def test_promotion_failed_replay_blocked(promo):
    req = {**_valid_promotion(), "replay_deterministic": False}
    result = promo.check(req)
    assert result["decision"] == "block"
    assert "replay_deterministic" in result["blocking_checks"]


# ---------------------------------------------------------------------------
# RT-2.3: Promotion: no security approval → blocked
# ---------------------------------------------------------------------------


def test_promotion_no_security_approval_blocked(promo):
    req = {**_valid_promotion(), "security_approved": False}
    result = promo.check(req)
    assert result["decision"] == "block"
    assert "security_approved" in result["blocking_checks"]


# ---------------------------------------------------------------------------
# RT-2.3: Promotion: over budget → blocked
# ---------------------------------------------------------------------------


def test_promotion_over_budget_blocked(promo):
    req = {**_valid_promotion(), "budget_used": 500, "budget_limit": 100}
    result = promo.check(req)
    assert result["decision"] == "block"
    assert "slo_compliant" in result["blocking_checks"]


# ---------------------------------------------------------------------------
# Gate decisions carry gate_id and trace_id
# ---------------------------------------------------------------------------


def test_gate_decisions_carry_metadata(promo, adm, eval_gate):
    trace = "TRC-META"
    inp = {**_valid_input(), "trace_id": trace}
    r_adm = adm.check(inp)
    assert r_adm["trace_id"] == trace
    assert r_adm["gate_id"] == "admission_gate"

    r_eval = eval_gate.check(_eval_results(100, 100, trace_id=trace))
    assert r_eval["trace_id"] == trace
    assert r_eval["gate_id"] == "eval_gate"

    r_promo = promo.check({**_valid_promotion(), "trace_id": trace})
    assert r_promo["trace_id"] == trace
    assert r_promo["gate_id"] == "promotion_gate"
