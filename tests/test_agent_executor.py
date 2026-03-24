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
    AgentExecutionError,
    emit_agent_execution_trace,
    execute_step_sequence,
    generate_step_plan,
)
from spectrum_systems.modules.runtime.model_adapter import CanonicalModelAdapter


def _prompt_resolution() -> Dict[str, Any]:
    return {
        "prompt_id": "ag.runtime.default",
        "prompt_version": "v1.0.0",
        "requested_alias": "prod",
        "resolution_source": "prompt_alias_map",
        "status": "resolved",
    }




def _routing_decision() -> Dict[str, Any]:
    return {
        "routing_decision_id": "rd-f43caad7a69a5ce1",
        "policy_id": "rp-ag-runtime-v1",
        "route_key": "meeting_minutes_default",
        "task_class": "meeting_minutes",
        "selected_model_id": "openai:gpt-4o-mini",
    }

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
        prompt_resolution=_prompt_resolution(),
        context_bundle=bundle,
        step_plan=plan,
        final_output_schema="context_bundle",
        tool_registry={"echo": echo_tool},
        final_output_builder=lambda b, _: b,
        routing_decision=_routing_decision(),
    )

    assert trace["execution_status"] == "completed"
    assert trace["failure_reason"] is None
    assert len(trace["step_sequence"]) == 2
    assert trace["step_sequence"][0]["status"] == "completed"
    assert trace["tool_calls"][0]["tool_name"] == "echo"
    assert trace["prompt_resolution"]["prompt_id"] == "ag.runtime.default"
    assert trace["prompt_resolution"]["prompt_version"] == "v1.0.0"


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
        prompt_resolution=_prompt_resolution(),
        context_bundle=bundle,
        step_plan=plan,
        final_output_schema="context_bundle",
        tool_registry={"explode": fail_tool},
        final_output_builder=lambda b, _: b,
        routing_decision=_routing_decision(),
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
        prompt_resolution=_prompt_resolution(),
        context_bundle=bundle,
        step_plan=plan,
        final_output_schema="context_bundle",
        final_output_builder=lambda *_: {"invalid": True},
        routing_decision=_routing_decision(),
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
            prompt_resolution=_prompt_resolution(),
            context_bundle=bundle,
            step_plan=plan,
            final_output_schema="context_bundle",
            final_output_builder=lambda b, _: b,
            routing_decision=_routing_decision(),
        )


def test_full_trace_emission_shape_validation() -> None:
    valid_trace = {
        "agent_run_id": "agent-run-005",
        "context_bundle_id": "ctx-1234abcd5678ef90",
        "trace_id": "trace-005",
        "prompt_resolution": _prompt_resolution(),
        "routing_decision": _routing_decision(),
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
        "model_invocations": [],
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


def test_missing_prompt_resolution_fails_closed() -> None:
    bundle = _context_bundle()
    plan = generate_step_plan(bundle, [{"step_type": "transform"}])

    with pytest.raises(AgentExecutionError):
        execute_step_sequence(
            agent_run_id="agent-run-006",
            trace_id="trace-006",
            prompt_resolution={},
            context_bundle=bundle,
            step_plan=plan,
            final_output_schema="context_bundle",
            final_output_builder=lambda b, _: b,
            routing_decision=_routing_decision(),
        )


def test_model_step_records_prompt_and_model_linkage() -> None:
    bundle = _context_bundle()
    plan = generate_step_plan(
        bundle,
        [
            {
                "step_id": "step-001",
                "step_type": "model",
                "requested_model_id": "openai:gpt-4o-mini",
                "input_text": "Summarize context",
                "execution_constraints": {"max_output_tokens": 128, "temperature": 0.0},
            }
        ],
    )

    class _Provider:
        provider_name = "openai"

        def invoke(self, provider_request: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "model": "gpt-4o-mini",
                "output_text": f"ok::{provider_request['request_id']}",
                "finish_reason": "stop",
                "raw_provider_field": "do_not_leak",
            }

    trace = execute_step_sequence(
        agent_run_id="agent-run-007",
        trace_id="trace-007",
        prompt_resolution=_prompt_resolution(),
        context_bundle=bundle,
        step_plan=plan,
        final_output_schema="context_bundle",
        model_adapter=CanonicalModelAdapter(provider=_Provider()),
        final_output_builder=lambda b, _: b,
        routing_decision=_routing_decision(),
    )

    assert trace["execution_status"] == "completed"
    assert len(trace["model_invocations"]) == 1
    invocation = trace["model_invocations"][0]
    assert invocation["requested_model_id"] == "openai:gpt-4o-mini"
    assert invocation["provider_name"] == "openai"
    assert invocation["provider_model_name"] == "gpt-4o-mini"
    assert "raw_provider_field" not in invocation
    assert trace["prompt_resolution"]["prompt_id"] == "ag.runtime.default"
    assert trace["prompt_resolution"]["prompt_version"] == "v1.0.0"


def test_model_step_fails_closed_on_malformed_provider_response() -> None:
    bundle = _context_bundle()
    plan = generate_step_plan(
        bundle,
        [
            {
                "step_id": "step-001",
                "step_type": "model",
                "requested_model_id": "openai:gpt-4o-mini",
                "input_text": "Summarize context",
            }
        ],
    )

    class _BadProvider:
        provider_name = "openai"

        def invoke(self, _: Dict[str, Any]) -> Dict[str, Any]:
            return {"model": "gpt-4o-mini", "output_text": "bad", "finish_reason": "unknown"}

    trace = execute_step_sequence(
        agent_run_id="agent-run-008",
        trace_id="trace-008",
        prompt_resolution=_prompt_resolution(),
        context_bundle=bundle,
        step_plan=plan,
        final_output_schema="context_bundle",
        model_adapter=CanonicalModelAdapter(provider=_BadProvider()),
        final_output_builder=lambda b, _: b,
        routing_decision=_routing_decision(),
    )

    assert trace["execution_status"] == "failed"
    assert "model adapter failure" in (trace["failure_reason"] or "")
