from __future__ import annotations

import json
from typing import Any, Dict

import pytest

from spectrum_systems.modules.runtime.model_adapter import (
    CanonicalModelAdapter,
    ModelAdapterError,
    build_canonical_request,
    normalize_provider_response,
)


class _Provider:
    provider_name = "openai"

    def invoke(self, provider_request: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "model": str(provider_request["model"]).split(":")[-1],
            "output_text": f"ok::{provider_request['request_id']}",
            "finish_reason": "stop",
            "provider_debug": {"not": "allowed outside adapter"},
        }


class _StructuredProvider:
    provider_name = "openai"
    supported_structured_modes = {"provider_native_strict"}

    def invoke(self, provider_request: Dict[str, Any]) -> Dict[str, Any]:
        output_object = {
            "artifact_type": "routing_decision",
            "schema_version": "1.0.0",
            "routing_decision_id": "rd-f43caad7a69a5ce1",
            "created_at": "2026-03-24T00:00:00Z",
            "route_key": "meeting_minutes_default",
            "task_class": "meeting_minutes",
            "risk_class": "low",
            "selected_prompt_id": "ag.runtime.default",
            "selected_prompt_alias": "prod",
            "resolved_prompt_version": "v1.0.0",
            "selected_model_id": "openai:gpt-4o-mini",
            "policy_id": "rp-ag-runtime-v1",
            "trace": {
                "trace_id": "trace-001",
                "agent_run_id": "agrun-001"
            },
            "related_artifact_refs": ["context_bundle:ctx-1", "prompt_resolution:ag.runtime.default@v1.0.0"]
        }
        return {
            "model": "gpt-4o-mini",
            "output_object": output_object,
            "output_text": json.dumps(output_object, sort_keys=True),
            "finish_reason": "stop",
        }


def test_build_canonical_request_is_deterministic() -> None:
    kwargs = {
        "prompt_id": "ag.runtime.default",
        "prompt_version": "v1.0.0",
        "requested_model_id": "openai:gpt-4o-mini",
        "input_text": "Summarize bounded context",
        "trace_id": "trace-001",
        "agent_run_id": "agrun-001",
        "step_id": "step-001",
        "max_output_tokens": 128,
        "temperature": 0.0,
        "structured_output": {
            "generation_mode": "provider_native_strict",
            "target_schema_ref": "routing_decision",
        },
    }
    first = build_canonical_request(**kwargs)
    second = build_canonical_request(**kwargs)

    assert first == second
    assert first["structured_output"]["target_schema_ref"] == "routing_decision"


def test_provider_response_normalized_to_canonical_shape() -> None:
    request = build_canonical_request(
        prompt_id="ag.runtime.default",
        prompt_version="v1.0.0",
        requested_model_id="openai:gpt-4o-mini",
        input_text="Summarize bounded context",
        trace_id="trace-001",
        agent_run_id="agrun-001",
        step_id="step-001",
    )

    response = normalize_provider_response(
        provider_name="openai",
        request=request,
        provider_response={
            "model": "gpt-4o-mini",
            "output_text": "Normalized output",
            "finish_reason": "stop",
            "extra": "provider-native",
        },
    )

    assert response["artifact_type"] == "ai_model_response"
    assert response["provider_name"] == "openai"
    assert response["provider_model_name"] == "gpt-4o-mini"
    assert response["request_id"] == request["request_id"]
    assert response["structured_output"]["status"] == "not_requested"
    assert "extra" not in response


def test_structured_provider_response_normalized_with_schema_linkage() -> None:
    adapter = CanonicalModelAdapter(provider=_StructuredProvider())
    request = build_canonical_request(
        prompt_id="ag.runtime.default",
        prompt_version="v1.0.0",
        requested_model_id="openai:gpt-4o-mini",
        input_text="Return structured routing decision",
        trace_id="trace-001",
        agent_run_id="agrun-001",
        step_id="step-001",
        structured_output={
            "generation_mode": "provider_native_strict",
            "target_schema_ref": "routing_decision",
        },
    )

    response = adapter.execute(request)

    assert response["response_status"] == "completed"
    assert response["structured_output"]["generation_mode"] == "provider_native_strict"
    assert response["structured_output"]["target_schema_ref"] == "routing_decision"
    assert response["structured_output"]["enforcement_path"] == "provider_native"
    assert response["structured_output"]["status"] == "succeeded"


def test_malformed_provider_response_rejected_fail_closed() -> None:
    request = build_canonical_request(
        prompt_id="ag.runtime.default",
        prompt_version="v1.0.0",
        requested_model_id="openai:gpt-4o-mini",
        input_text="Summarize bounded context",
        trace_id="trace-001",
        agent_run_id="agrun-001",
        step_id="step-001",
    )

    with pytest.raises(ModelAdapterError, match="unknown provider finish_reason"):
        normalize_provider_response(
            provider_name="openai",
            request=request,
            provider_response={"model": "gpt-4o-mini", "output_text": "x", "finish_reason": "unknown"},
        )


def test_structured_response_schema_mismatch_rejected() -> None:
    request = build_canonical_request(
        prompt_id="ag.runtime.default",
        prompt_version="v1.0.0",
        requested_model_id="openai:gpt-4o-mini",
        input_text="Return structured routing decision",
        trace_id="trace-001",
        agent_run_id="agrun-001",
        step_id="step-001",
        structured_output={
            "generation_mode": "adapter_json_schema_strict",
            "target_schema_ref": "routing_decision",
        },
    )

    with pytest.raises(ModelAdapterError, match="schema mismatch"):
        normalize_provider_response(
            provider_name="openai",
            request=request,
            provider_response={
                "model": "gpt-4o-mini",
                "output_text": json.dumps({"bad": "shape"}),
                "finish_reason": "stop",
            },
        )


def test_provider_incapable_path_rejected_when_structured_required() -> None:
    class _IncapableProvider:
        provider_name = "openai"

        def invoke(self, provider_request: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "model": "gpt-4o-mini",
                "output_text": "{}",
                "finish_reason": "stop",
            }

    adapter = CanonicalModelAdapter(provider=_IncapableProvider())
    request = build_canonical_request(
        prompt_id="ag.runtime.default",
        prompt_version="v1.0.0",
        requested_model_id="openai:gpt-4o-mini",
        input_text="Return structured routing decision",
        trace_id="trace-001",
        agent_run_id="agrun-001",
        step_id="step-001",
        structured_output={
            "generation_mode": "provider_native_strict",
            "target_schema_ref": "routing_decision",
        },
    )

    with pytest.raises(ModelAdapterError, match="cannot honor required structured mode"):
        adapter.execute(request)


def test_adapter_execute_returns_only_canonical_response() -> None:
    adapter = CanonicalModelAdapter(provider=_Provider())
    request = build_canonical_request(
        prompt_id="ag.runtime.default",
        prompt_version="v1.0.0",
        requested_model_id="openai:gpt-4o-mini",
        input_text="Summarize bounded context",
        trace_id="trace-001",
        agent_run_id="agrun-001",
        step_id="step-001",
    )

    response = adapter.execute(request)

    assert response["artifact_type"] == "ai_model_response"
    assert set(response.keys()) == {
        "artifact_type",
        "schema_version",
        "response_id",
        "created_at",
        "request_id",
        "provider_name",
        "provider_model_name",
        "normalized_output_text",
        "finish_reason",
        "response_status",
        "structured_output",
        "trace",
    }
