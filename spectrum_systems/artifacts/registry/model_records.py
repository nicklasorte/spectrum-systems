from __future__ import annotations

from typing import Any, Dict


def build_ai_model_request(request_id: str, target_schema_ref: str, trace_id: str, agent_run_id: str, step_id: str) -> Dict[str, Any]:
    return {
        "artifact_type": "ai_model_request",
        "schema_version": "1.0.0",
        "request_id": request_id,
        "created_at": "2026-01-01T00:00:00Z",
        "target_schema_ref": target_schema_ref,
        "trace": {"trace_id": trace_id, "agent_run_id": agent_run_id, "step_id": step_id},
    }


def build_ai_model_response(response_id: str, request_id: str, output_text: str, trace_id: str, agent_run_id: str, step_id: str) -> Dict[str, Any]:
    return {
        "artifact_type": "ai_model_response",
        "schema_version": "1.1.0",
        "response_id": response_id,
        "created_at": "2026-01-01T00:00:00Z",
        "request_id": request_id,
        "provider_name": "governed-provider",
        "provider_model_name": "governed-model",
        "normalized_output_text": output_text,
        "finish_reason": "stop",
        "response_status": "completed",
        "structured_output": {
            "requested": True,
            "target_schema_ref": "ai_model_response",
            "generation_mode": "adapter_json_schema_strict",
            "enforcement_path": "adapter_json_schema",
            "status": "succeeded",
            "failure_reason": None,
        },
        "trace": {"trace_id": trace_id, "agent_run_id": agent_run_id, "step_id": step_id},
    }
