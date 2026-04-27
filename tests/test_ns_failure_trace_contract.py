"""NS-07..09: One-page failure trace contract + new-engineer debug drill.

For every blocked / frozen case below, the trace produced by
``build_failure_trace`` must answer:

  - what failed              → ``failing_artifact_type`` / ``one_page_summary``
  - where it failed          → ``failed_stage``
  - who owns the failure     → ``owning_system_for_failed_stage``
  - what artifact proves it  → ``failing_artifact_id``
  - what action is blocked   → ``downstream_blocked_action``
  - what the next fix is     → ``next_recommended_action``

The output must remain machine- and human-readable: ``one_page_summary`` is
a multi-line string that a new engineer can read in under a minute.
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.observability.failure_trace import build_failure_trace
from spectrum_systems.modules.observability.reason_code_canonicalizer import (
    CANONICAL_CATEGORIES,
)


REQUIRED_FIELDS = (
    "failed_stage",
    "owning_system_for_failed_stage",
    "canonical_reason_category",
    "primary_reason_code",
    "failing_artifact_id",
    "failing_artifact_type",
    "downstream_blocked_action",
    "next_recommended_action",
    "one_page_summary",
)


def _good() -> dict:
    return {
        "execution_record": {
            "artifact_id": "exec-1",
            "artifact_type": "pqx_slice_execution_record",
            "status": "ok",
        },
        "output_artifact": {
            "artifact_id": "out-1",
            "artifact_type": "eval_summary",
        },
        "eval_result": {
            "artifact_id": "eval-1",
            "artifact_type": "eval_slice_summary",
            "status": "healthy",
        },
        "control_decision": {"decision_id": "cde-1", "decision": "allow"},
        "enforcement_action": {
            "enforcement_id": "sel-1",
            "enforcement_action": "allow_execution",
        },
    }


def _assert_debug_drill_contract(trace: dict) -> None:
    """All seven NS-08 questions must be answerable without scrolling."""
    assert trace["overall_status"] in {"failed", "ok"}
    if trace["overall_status"] != "failed":
        return
    for field in REQUIRED_FIELDS:
        assert field in trace, f"trace missing required field {field!r}"

    # one_page_summary must be a non-empty string and contain key fields
    summary = trace["one_page_summary"]
    assert isinstance(summary, str) and summary.strip()
    assert "failed_stage" in summary
    assert "canonical_category" in summary
    assert "next_recommended_action" in summary
    # canonical category must be from finite set
    cc = trace["canonical_reason_category"]
    assert cc in set(CANONICAL_CATEGORIES) or cc == "UNKNOWN"


# ---- 10 blocked/frozen drill cases ----


def test_drill_01_missing_execution_record() -> None:
    inputs = _good()
    inputs["execution_record"] = None
    trace = build_failure_trace(trace_id="d1", **inputs)
    assert trace["failed_stage"] == "execution"
    assert trace["owning_system_for_failed_stage"] == "PQX"
    assert trace["canonical_reason_category"] == "MISSING_ARTIFACT"
    _assert_debug_drill_contract(trace)


def test_drill_02_execution_error_status() -> None:
    inputs = _good()
    inputs["execution_record"] = {
        "artifact_id": "exec-bad",
        "artifact_type": "pqx_slice_execution_record",
        "status": "error",
        "reason_code": "PQX_TIMEOUT",
    }
    trace = build_failure_trace(trace_id="d2", **inputs)
    assert trace["failed_stage"] == "execution"
    assert "PQX_TIMEOUT" in trace["one_page_summary"]
    _assert_debug_drill_contract(trace)


def test_drill_03_missing_output_artifact() -> None:
    inputs = _good()
    inputs["output_artifact"] = None
    trace = build_failure_trace(trace_id="d3", **inputs)
    assert trace["failed_stage"] == "output"
    assert trace["canonical_reason_category"] == "MISSING_ARTIFACT"
    _assert_debug_drill_contract(trace)


def test_drill_04_eval_blocked_missing_required_eval_result() -> None:
    inputs = _good()
    inputs["eval_result"] = {
        "artifact_id": "eval-bad",
        "artifact_type": "eval_slice_summary",
        "status": "blocked",
        "block_reason": "missing_required_eval_result",
    }
    trace = build_failure_trace(trace_id="d4", **inputs)
    assert trace["failed_stage"] == "eval"
    assert trace["owning_system_for_failed_stage"] == "EVL"
    assert trace["canonical_reason_category"] == "EVAL_FAILURE"
    _assert_debug_drill_contract(trace)


def test_drill_05_replay_mismatch_surfaced_as_eval_block() -> None:
    inputs = _good()
    inputs["eval_result"] = {
        "artifact_id": "eval-bad",
        "artifact_type": "eval_slice_summary",
        "status": "blocked",
        "block_reason": "REPLAY_HASH_MISMATCH_OUTPUT",
    }
    trace = build_failure_trace(trace_id="d5", **inputs)
    assert trace["failed_stage"] == "eval"
    assert trace["canonical_reason_category"] == "REPLAY_MISMATCH"
    _assert_debug_drill_contract(trace)


def test_drill_06_control_decision_block() -> None:
    inputs = _good()
    inputs["control_decision"] = {
        "decision_id": "cde-bad",
        "decision": "block",
        "reason_code": "policy_mismatch",
    }
    trace = build_failure_trace(trace_id="d6", **inputs)
    assert trace["failed_stage"] == "control"
    assert trace["owning_system_for_failed_stage"] == "CDE"
    assert trace["canonical_reason_category"] == "POLICY_MISMATCH"
    _assert_debug_drill_contract(trace)


def test_drill_07_enforcement_deny_execution() -> None:
    inputs = _good()
    inputs["enforcement_action"] = {
        "enforcement_id": "sel-bad",
        "enforcement_action": "deny_execution",
        "reason_code": "policy_mismatch",
    }
    trace = build_failure_trace(trace_id="d7", **inputs)
    assert trace["failed_stage"] == "enforcement"
    assert trace["owning_system_for_failed_stage"] == "SEL"
    _assert_debug_drill_contract(trace)


def test_drill_08_freeze_at_control() -> None:
    inputs = _good()
    inputs["control_decision"] = {
        "decision_id": "cde-frz",
        "decision": "freeze",
        "reason_code": "SLO_BUDGET_EXHAUSTED",
    }
    trace = build_failure_trace(trace_id="d8", **inputs)
    assert trace["failed_stage"] == "control"
    assert trace["canonical_reason_category"] == "SLO_BUDGET_FAILURE"
    _assert_debug_drill_contract(trace)


def test_drill_09_lineage_gap_surfaced_at_eval() -> None:
    inputs = _good()
    inputs["eval_result"] = {
        "artifact_id": "eval-lin",
        "artifact_type": "eval_slice_summary",
        "status": "blocked",
        "block_reason": "LINEAGE_MISSING_TRACE_ID",
    }
    trace = build_failure_trace(trace_id="d9", **inputs)
    assert trace["failed_stage"] == "eval"
    assert trace["canonical_reason_category"] == "TRACE_GAP"
    _assert_debug_drill_contract(trace)


def test_drill_10_context_admission_failure_surfaced_at_eval() -> None:
    inputs = _good()
    inputs["eval_result"] = {
        "artifact_id": "eval-ctx",
        "artifact_type": "eval_slice_summary",
        "status": "blocked",
        "block_reason": "CTX_UNTRUSTED_INSTRUCTION",
    }
    trace = build_failure_trace(trace_id="d10", **inputs)
    assert trace["failed_stage"] == "eval"
    assert trace["canonical_reason_category"] == "CONTEXT_ADMISSION_FAILURE"
    _assert_debug_drill_contract(trace)


# Sanity: passing path produces no failure but still has one_page_summary
def test_drill_passing_path_has_one_page_summary() -> None:
    trace = build_failure_trace(trace_id="d-pass", **_good())
    assert trace["overall_status"] == "ok"
    assert "trace_id=d-pass" in trace["one_page_summary"]


def test_upstream_artifact_attached_for_eval_failure() -> None:
    inputs = _good()
    inputs["eval_result"] = {
        "artifact_id": "eval-bad",
        "artifact_type": "eval_slice_summary",
        "status": "blocked",
        "block_reason": "missing_required_eval_result",
    }
    trace = build_failure_trace(trace_id="up-1", **inputs)
    assert trace["upstream_artifact"]["stage"] == "output"
    assert trace["upstream_artifact"]["artifact_id"] == "out-1"
