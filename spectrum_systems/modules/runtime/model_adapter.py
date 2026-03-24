"""HS-03 canonical model adapter boundary for AG runtime execution.

This module enforces a strict provider edge:
- Canonical request artifact (ai_model_request)
- Canonical response artifact (ai_model_response)
- Fail-closed validation on both sides of the adapter seam
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Mapping, Protocol

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import canonical_json, deterministic_id

REQUEST_SCHEMA = "ai_model_request"
RESPONSE_SCHEMA = "ai_model_response"
REQUEST_SCHEMA_VERSION = "1.0.0"
RESPONSE_SCHEMA_VERSION = "1.0.0"

_ALLOWED_FINISH_REASONS = {"stop", "length", "content_filter", "error"}


class ModelAdapterError(RuntimeError):
    """Fail-closed model adapter boundary error."""


class ProviderAdapter(Protocol):
    """Minimal provider adapter interface used by AG runtime."""

    provider_name: str

    def invoke(self, provider_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute provider call and return provider-native payload."""


@dataclass(frozen=True)
class CanonicalModelAdapter:
    """Canonical model adapter wiring one provider path behind a governed boundary."""

    provider: ProviderAdapter

    def execute(self, canonical_request: Dict[str, Any]) -> Dict[str, Any]:
        validated_request = validate_canonical_request(canonical_request)
        provider_request = to_provider_request(validated_request)
        provider_response = self.provider.invoke(provider_request)
        canonical_response = normalize_provider_response(
            provider_name=self.provider.provider_name,
            request=validated_request,
            provider_response=provider_response,
        )
        return validate_canonical_response(canonical_response)


def _validate_contract(instance: Dict[str, Any], schema_name: str) -> Dict[str, Any]:
    schema = load_schema(schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)
    return instance


def _deterministic_timestamp(seed_payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(seed_payload).encode("utf-8")).hexdigest()
    offset_seconds = int(digest[:8], 16) % (365 * 24 * 60 * 60)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_canonical_request(
    *,
    prompt_id: str,
    prompt_version: str,
    requested_model_id: str,
    input_text: str,
    trace_id: str,
    agent_run_id: str,
    step_id: str,
    max_output_tokens: int = 512,
    temperature: float = 0.0,
) -> Dict[str, Any]:
    """Construct deterministic canonical ai_model_request payload."""
    identity_payload = {
        "prompt_id": prompt_id,
        "prompt_version": prompt_version,
        "requested_model_id": requested_model_id,
        "input_text": input_text,
        "trace": {
            "trace_id": trace_id,
            "agent_run_id": agent_run_id,
            "step_id": step_id,
        },
        "execution_constraints": {
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
        },
    }
    request_id = deterministic_id(prefix="amr", namespace="ai_model_request", payload=identity_payload)
    created_at = _deterministic_timestamp({"request_id": request_id, "identity": identity_payload})
    request = {
        "artifact_type": REQUEST_SCHEMA,
        "schema_version": REQUEST_SCHEMA_VERSION,
        "request_id": request_id,
        "created_at": created_at,
        "prompt_id": prompt_id,
        "prompt_version": prompt_version,
        "requested_model_id": requested_model_id,
        "input_text": input_text,
        "execution_constraints": {
            "max_output_tokens": int(max_output_tokens),
            "temperature": float(temperature),
        },
        "trace": {
            "trace_id": trace_id,
            "agent_run_id": agent_run_id,
            "step_id": step_id,
        },
    }
    return validate_canonical_request(request)


def validate_canonical_request(canonical_request: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return _validate_contract(canonical_request, REQUEST_SCHEMA)
    except ValidationError as exc:
        raise ModelAdapterError(f"invalid canonical request: {exc.message}") from exc


def validate_canonical_response(canonical_response: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return _validate_contract(canonical_response, RESPONSE_SCHEMA)
    except ValidationError as exc:
        raise ModelAdapterError(f"invalid canonical response: {exc.message}") from exc


def to_provider_request(canonical_request: Dict[str, Any]) -> Dict[str, Any]:
    """Map canonical request to minimal provider request shape."""
    validate_canonical_request(canonical_request)
    return {
        "model": canonical_request["requested_model_id"],
        "input": canonical_request["input_text"],
        "max_output_tokens": canonical_request["execution_constraints"]["max_output_tokens"],
        "temperature": canonical_request["execution_constraints"]["temperature"],
        "request_id": canonical_request["request_id"],
    }


def normalize_provider_response(
    *,
    provider_name: str,
    request: Dict[str, Any],
    provider_response: Dict[str, Any],
) -> Dict[str, Any]:
    """Normalize provider-native payload into strict canonical ai_model_response."""
    validate_canonical_request(request)
    if not isinstance(provider_response, dict):
        raise ModelAdapterError("provider response must be an object")

    output_text = provider_response.get("output_text")
    model_name = provider_response.get("model")
    finish_reason = provider_response.get("finish_reason")

    if not isinstance(output_text, str) or not output_text.strip():
        raise ModelAdapterError("provider response missing non-empty output_text")
    if not isinstance(model_name, str) or not model_name.strip():
        raise ModelAdapterError("provider response missing non-empty model")
    if finish_reason not in _ALLOWED_FINISH_REASONS:
        raise ModelAdapterError(f"unknown provider finish_reason '{finish_reason}'")

    response_status = "completed" if finish_reason != "error" else "failed"
    identity_payload = {
        "request_id": request["request_id"],
        "provider_name": provider_name,
        "provider_model_name": model_name,
        "normalized_output_text": output_text,
        "finish_reason": finish_reason,
        "response_status": response_status,
    }
    response_id = deterministic_id(prefix="amres", namespace="ai_model_response", payload=identity_payload)
    created_at = _deterministic_timestamp({"response_id": response_id, "identity": identity_payload})

    canonical_response = {
        "artifact_type": RESPONSE_SCHEMA,
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "response_id": response_id,
        "created_at": created_at,
        "request_id": request["request_id"],
        "provider_name": provider_name,
        "provider_model_name": model_name,
        "normalized_output_text": output_text,
        "finish_reason": finish_reason,
        "response_status": response_status,
        "trace": dict(request["trace"]),
    }
    return validate_canonical_response(canonical_response)
