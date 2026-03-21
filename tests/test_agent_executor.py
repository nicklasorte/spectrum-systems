"""Tests for BAZ bounded agent execution module."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.agents.agent_executor import (  # noqa: E402
    AgentExecutionBlockedError,
    emit_agent_execution_trace,
    execute_step_sequence,
    generate_step_plan,
)


def _context_bundle(*, with_context_data: bool = True) -> Dict[str, Any]:
    retrieved = [
        {
            "artifact_id": "ART-001",
            "content": "relevant context",
            "relevance_score": 0.9,
            "provenance": {"source": "fixture"},
        }
    ] if with_context_data else []

    return {
        "context_id": "ctx-1234abcd5678ef90",
        "task_type": "agent_execution",
        "primary_input": {"goal": "execute bounded plan"},
        "policy_constraints": {"max_steps": 4},
        "retrieved_context": retrieved,
        "prior_artifacts": [],
        "glossary_terms": [],
        "unresolved_questions": [],
        "metadata": {
            "created_at": "2026-03-21T00:00:00+00:00",
            "retrieval_status": "available" if with_context_data else "empty",
            "source_artifact_ids": ["ART-001"],
        },
        "token_estimates": {"total": 100},
        "truncation_log": [],
    }


def test_successful_bounded_execution() -> None:
    bundle = _context_bundle()
    declared_steps: List[Dict[str, Any]] = [
        {"step_type": "tool", "tool_name": "echo", "tool_input": {"value": "ok"}},
        {"step_type": "transform"},
    ]
    plan = generate_step_plan(bundle, declared_steps)

    def echo_tool(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "artifact_id": "artifact-echo-001",
            "artifact_type": "tool_output",
            "schema_name": "artifact_envelope",
            "payload": payload,
        }

    trace = execute_step_sequence(
        agent_run_id="agent-run-001",
        trace_id="trace-001",
        context_bundle=bundle,
        step_plan=plan,
        final_output_schema="context_bundle",
        tool_registry={"echo": echo_tool},
        final_output_builder=lambda b, _: b,
    )

    assert trace["execution_status"] == "completed"
    assert trace["failure_reason"] is None
    assert len(trace["step_sequence"]) == 2
    assert trace["step_sequence"][0]["status"] == "completed"
    assert trace["tool_calls"][0]["tool_name"] == "echo"


def test_tool_step_failure() -> None:
    bundle = _context_bundle()
    plan = generate_step_plan(
        bundle,
        [{"step_type": "tool", "tool_name": "explode", "tool_input": {"value": "boom"}}],
    )

    def fail_tool(_: Dict[str, Any]) -> Dict[str, Any]:
        raise RuntimeError("tool explosion")

    trace = execute_step_sequence(
        agent_run_id="agent-run-002",
        trace_id="trace-002",
        context_bundle=bundle,
        step_plan=plan,
        final_output_schema="context_bundle",
        tool_registry={"explode": fail_tool},
        final_output_builder=lambda b, _: b,
    )

    assert trace["execution_status"] == "failed"
    assert "tool explosion" in (trace["failure_reason"] or "")
    assert trace["tool_calls"][0]["status"] == "failed"


def test_schema_invalid_final_output() -> None:
    bundle = _context_bundle()
    plan = generate_step_plan(bundle, [{"step_type": "transform"}])

    trace = execute_step_sequence(
        agent_run_id="agent-run-003",
        trace_id="trace-003",
        context_bundle=bundle,
        step_plan=plan,
        final_output_schema="context_bundle",
        final_output_builder=lambda *_: {"invalid": True},
    )

    assert trace["execution_status"] == "failed"
    assert "validate_final_output failed" in (trace["failure_reason"] or "")


def test_blocked_execution_when_context_bundle_missing_required_data() -> None:
    bundle = _context_bundle(with_context_data=False)
    plan = generate_step_plan(bundle, [{"step_type": "transform"}])

    with pytest.raises(AgentExecutionBlockedError):
        execute_step_sequence(
            agent_run_id="agent-run-004",
            trace_id="trace-004",
            context_bundle=bundle,
            step_plan=plan,
            final_output_schema="context_bundle",
            final_output_builder=lambda b, _: b,
        )


def test_full_trace_emission_shape_validation() -> None:
    valid_trace = {
        "agent_run_id": "agent-run-005",
        "context_bundle_id": "ctx-1234abcd5678ef90",
        "trace_id": "trace-005",
        "step_sequence": [
            {
                "step_id": "step-001",
                "step_type": "transform",
                "status": "completed",
                "input_ref": "context://ctx-1234abcd5678ef90",
                "output_ref": "transform://step-001",
                "error": None,
            }
        ],
        "tool_calls": [],
        "intermediate_artifacts": [],
        "final_output_artifact_id": "agent-output://agent-run-005",
        "execution_status": "completed",
        "failure_reason": None,
        "started_at": "2026-03-21T00:00:00+00:00",
        "completed_at": "2026-03-21T00:00:01+00:00",
    }

    emitted = emit_agent_execution_trace(valid_trace)
    assert emitted["trace_id"] == "trace-005"
    assert emitted["execution_status"] == "completed"
