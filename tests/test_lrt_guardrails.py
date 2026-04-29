"""LRT guardrails — focused unit tests (6 cases, fail-closed assertions).

Tests prove: broad prompt blocking, bounded admission, keep-going blocking,
checkpoint serialization, stop_after_checkpoint enforcement, and timeout
trend capture.
"""

from __future__ import annotations

import pytest

from spectrum_systems.aex.lrt_admission_guard import check_lrt_admission
from spectrum_systems.modules.runtime.cde_lrt_continuation import decide_lrt_continuation
from spectrum_systems.modules.runtime.lrt_checkpoint_record import (
    LRTCheckpointError,
    build_lrt_checkpoint_record,
)
from spectrum_systems.modules.runtime.obs_timeout_trend import build_timeout_trend_record
from spectrum_systems.modules.runtime.pqx_execution_budget import (
    EXECUTION_BUDGET_DEFAULTS,
    PQXBudgetError,
    validate_execution_budget,
)

_VALID_BUDGET = {
    "max_files_changed": 3,
    "max_lines_added": 300,
    "max_test_file_lines": 150,
    "max_stage_minutes": 10,
    "checkpoint_required": True,
    "stop_after_checkpoint": True,
}


def test_broad_prompt_without_budget_is_blocked() -> None:
    result = check_lrt_admission(
        prompt_text="write the comprehensive test file for every module",
        execution_budget=None,
    )
    assert result.admitted is False
    assert result.broad_pattern_detected is True
    assert "execution_budget_missing" in result.reason_codes

    with pytest.raises(PQXBudgetError, match="broad task requires execution_budget"):
        validate_execution_budget(None, broad_task=True)


def test_broad_prompt_with_budget_is_admitted_as_bounded() -> None:
    result = check_lrt_admission(
        prompt_text="write the comprehensive test file",
        execution_budget=_VALID_BUDGET,
    )
    assert result.admitted is True
    assert result.broad_pattern_detected is True
    assert result.budget_valid is True
    assert "admitted_as_bounded" in result.reason_codes

    budget_result = validate_execution_budget(_VALID_BUDGET, broad_task=True)
    assert budget_result["valid"] is True


def test_keep_going_without_checkpoint_is_blocked() -> None:
    for phrase in ("keep going", "continue", "go ahead", "proceed"):
        decision = decide_lrt_continuation(
            continuation_phrase=phrase,
            checkpoint_present=False,
            stop_after_checkpoint=False,
        )
        assert decision["decision"] == "block", f"phrase {phrase!r} should be blocked without checkpoint"

    # Unrecognised phrase also blocked when no checkpoint present (safety net)
    decision = decide_lrt_continuation(
        continuation_phrase="do something else",
        checkpoint_present=False,
        stop_after_checkpoint=False,
    )
    assert decision["decision"] == "block"
    assert "continuation_without_checkpoint" in decision["reason_codes"]


def test_checkpoint_record_validates_and_serializes() -> None:
    record = build_lrt_checkpoint_record(
        checkpoint_id="ckpt-001",
        trace_id="trace-abc",
        task_id="task-xyz",
        stage="lrt_slice_1",
        files_changed=2,
        tests_added=3,
        commands_run=["python -m pytest -q tests/test_lrt_guardrails.py"],
        next_recommended_slice="add_integration_tests",
        resume_instructions="start from lrt_slice_2 with existing checkpoint",
        status="checkpointed",
    )
    assert record["artifact_type"] == "lrt_checkpoint_record"
    assert record["status"] == "checkpointed"
    assert isinstance(record["commands_run"], list)

    with pytest.raises(LRTCheckpointError):
        build_lrt_checkpoint_record(
            checkpoint_id="x", trace_id="t", task_id="t", stage="s",
            files_changed=0, tests_added=0, commands_run=[],
            next_recommended_slice="", resume_instructions="",
            status="invalid_status",
        )


def test_stop_after_checkpoint_prevents_continuation() -> None:
    decision = decide_lrt_continuation(
        continuation_phrase="keep going",
        checkpoint_present=True,
        stop_after_checkpoint=True,
    )
    assert decision["decision"] == "freeze"
    assert "stop_after_checkpoint_required" in decision["reason_codes"]

    decision_without_budget = decide_lrt_continuation(
        continuation_phrase="keep going",
        checkpoint_present=True,
        stop_after_checkpoint=False,
        execution_budget=None,
    )
    assert decision_without_budget["decision"] == "split"


def test_oversized_budget_is_rejected_and_invalid_budget_blocks_continuation() -> None:
    oversized = {**_VALID_BUDGET, "max_lines_added": 300 * 11}  # exceeds 10x default
    with pytest.raises(PQXBudgetError, match="exceeds limits"):
        validate_execution_budget(oversized, broad_task=True)

    empty_budget: dict = {}
    decision = decide_lrt_continuation(
        continuation_phrase="keep going",
        checkpoint_present=True,
        stop_after_checkpoint=False,
        execution_budget=empty_budget,
    )
    assert decision["decision"] == "split"
    assert "execution_budget_invalid" in decision["reason_codes"]


def test_timeout_trend_record_captures_stream_idle_timeout_no_checkpoint() -> None:
    record = build_timeout_trend_record(
        provider="claude_code",
        failure_type="stream_idle_timeout",
        stage="lrt_slice_1",
        task_size_class="broad",
        prompt_pattern="comprehensive_test_file",
        files_changed_before_timeout=2,
        checkpoint_present=False,
    )
    assert record["artifact_type"] == "obs_timeout_trend_record"
    assert record["failure_type"] == "stream_idle_timeout"
    assert record["checkpoint_present"] is False
    assert record["provider"] == "claude_code"
