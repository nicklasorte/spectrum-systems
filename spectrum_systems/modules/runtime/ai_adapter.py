"""Governed AI adapter for schema-bound request/response handling."""

from __future__ import annotations

from typing import Any


def build_ai_request(*, run_id: str, trace_id: str, task_id: str, prompt_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "ai_model_request",
        "artifact_version": "1.2.0",
        "schema_version": "1.2.0",
        "run_id": run_id,
        "trace_id": trace_id,
        "task_id": task_id,
        "prompt_id": prompt_id,
        "payload": payload,
    }


def normalize_ai_response(*, request: dict[str, Any], model_output: dict[str, Any], success: bool, error: str | None = None) -> dict[str, Any]:
    return {
        "artifact_type": "ai_model_response",
        "artifact_version": "1.2.0",
        "schema_version": "1.2.0",
        "run_id": request["run_id"],
        "trace_id": request["trace_id"],
        "task_id": request["task_id"],
        "prompt_id": request["prompt_id"],
        "success": bool(success),
        "output": model_output if success else {},
        "error": error,
    }
