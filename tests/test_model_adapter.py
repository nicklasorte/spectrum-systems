from __future__ import annotations

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
    }
    first = build_canonical_request(**kwargs)
    second = build_canonical_request(**kwargs)

    assert first == second


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
    assert "extra" not in response


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
        "trace",
    }
