"""Deterministic bounded context injection adapter for Codex/PQX consumers."""

from __future__ import annotations

from typing import Any, Dict, Mapping


class ContextInjectionError(RuntimeError):
    """Fail-closed context injection error."""


def build_context_injection_payload(
    *,
    context_bundle: Mapping[str, Any],
    consumer: str,
    max_refs: int = 12,
) -> Dict[str, Any]:
    """Convert context_bundle_v2 into bounded advisory-only execution context payload."""

    if str(context_bundle.get("artifact_type") or "") != "context_bundle_v2":
        raise ContextInjectionError("context bundle must be context_bundle_v2")

    if consumer not in {"codex", "pqx"}:
        raise ContextInjectionError("consumer must be codex or pqx")

    selected_refs = list(context_bundle.get("selected_artifact_refs") or [])
    source_refs = list(context_bundle.get("source_refs") or [])
    trace_id = str(context_bundle.get("trace_id") or "")
    if not trace_id:
        raise ContextInjectionError("context bundle missing trace_id")

    bounded_refs = selected_refs[:max_refs]
    bounded_sources = source_refs[: max_refs * 2]

    return {
        "artifact_type": "context_injection_payload",
        "schema_version": "1.0.0",
        "consumer": consumer,
        "trace_id": trace_id,
        "context_id": context_bundle["context_id"],
        "target_scope": dict(context_bundle["target_scope"]),
        "advisory_only": True,
        "authority_boundary": "control_eval_certification_remains_authoritative",
        "max_refs": max_refs,
        "selected_artifact_refs": bounded_refs,
        "source_refs": bounded_sources,
        "replayable_from_artifacts": True,
        "hidden_context_allowed": False,
    }


__all__ = ["ContextInjectionError", "build_context_injection_payload"]
