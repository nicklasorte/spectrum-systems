"""AEX engine: canonical admission boundary before TLC orchestration.

AEX must never execute work, decide trust policy, or replace TLC orchestration.
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable, Mapping

from spectrum_systems.aex.classifier import classify_execution_type, is_repo_sensitive_unknown
from spectrum_systems.aex.errors import INVALID_REQUEST_SHAPE, MISSING_REQUIRED_FIELD, UNKNOWN_EXECUTION_TYPE
from spectrum_systems.aex.models import AdmissionResult, CodexBuildRequest
from spectrum_systems.contracts import validate_artifact


class AEXEngine:
    """Deterministic AEX admission engine with fail-closed behavior."""

    def admit_codex_request(self, request: Mapping[str, Any]) -> AdmissionResult:
        if not isinstance(request, Mapping):
            return self._reject("unknown", "unknown", [INVALID_REQUEST_SHAPE], "request must be an object")

        missing = [field for field in ("request_id", "prompt_text", "trace_id", "created_at", "produced_by") if not request.get(field)]
        request_id = str(request.get("request_id") or "unknown")
        trace_id = str(request.get("trace_id") or "unknown")
        if missing:
            return self._reject(request_id, trace_id, [MISSING_REQUIRED_FIELD], f"missing required fields: {', '.join(missing)}")

        normalized_input = CodexBuildRequest(
            request_id=str(request["request_id"]),
            prompt_text=str(request["prompt_text"]),
            trace_id=str(request["trace_id"]),
            created_at=str(request["created_at"]),
            produced_by=str(request["produced_by"]),
            target_paths=[str(item) for item in request.get("target_paths", [])],
            requested_outputs=[str(item) for item in request.get("requested_outputs", [])],
            source_prompt_kind=str(request.get("source_prompt_kind") or "codex_build_request"),
        )

        execution_type = classify_execution_type(normalized_input.prompt_text, normalized_input.target_paths)
        repo_mutation_requested = execution_type == "repo_write" or bool(normalized_input.target_paths)

        normalized = {
            "artifact_type": "normalized_execution_request",
            "request_id": normalized_input.request_id,
            "prompt_text": normalized_input.prompt_text,
            "execution_type": execution_type,
            "repo_mutation_requested": repo_mutation_requested,
            "target_paths": normalized_input.target_paths,
            "requested_outputs": normalized_input.requested_outputs,
            "source_prompt_kind": normalized_input.source_prompt_kind,
            "trace_id": normalized_input.trace_id,
            "created_at": normalized_input.created_at,
            "produced_by": normalized_input.produced_by,
        }
        validate_artifact(normalized, "normalized_execution_request")

        if is_repo_sensitive_unknown(
            execution_type=execution_type,
            repo_mutation_requested=repo_mutation_requested,
            target_paths=normalized_input.target_paths,
        ):
            return self._reject(
                normalized_input.request_id,
                normalized_input.trace_id,
                [UNKNOWN_EXECUTION_TYPE],
                "execution type is unknown and repo mutation cannot be ruled out",
                normalized=normalized,
            )

        admission_id = self._id("adm", normalized_input.request_id, normalized_input.trace_id)
        record = {
            "artifact_type": "build_admission_record",
            "admission_id": admission_id,
            "request_id": normalized_input.request_id,
            "execution_type": execution_type,
            "admission_status": "accepted",
            "normalized_execution_request_ref": f"normalized_execution_request:{normalized_input.request_id}",
            "trace_id": normalized_input.trace_id,
            "created_at": normalized_input.created_at,
            "produced_by": normalized_input.produced_by,
            "reason_codes": [],
            "target_scope": {
                "repo": "spectrum-systems",
                "paths": normalized_input.target_paths,
            },
        }
        validate_artifact(record, "build_admission_record")
        return AdmissionResult(normalized_execution_request=normalized, build_admission_record=record, admission_rejection_record=None)

    def _reject(
        self,
        request_id: str,
        trace_id: str,
        reason_codes: list[str],
        summary: str,
        *,
        normalized: dict[str, Any] | None = None,
    ) -> AdmissionResult:
        record = {
            "artifact_type": "admission_rejection_record",
            "rejection_id": self._id("rej", request_id, trace_id),
            "request_id": request_id,
            "trace_id": trace_id,
            "created_at": "2026-04-08T00:00:00Z",
            "rejection_reason_codes": reason_codes,
            "rejection_summary": summary,
            "produced_by": "AEXEngine",
        }
        validate_artifact(record, "admission_rejection_record")
        return AdmissionResult(normalized_execution_request=normalized, build_admission_record=None, admission_rejection_record=record)

    @staticmethod
    def _id(prefix: str, request_id: str, trace_id: str) -> str:
        digest = hashlib.sha256(f"{request_id}|{trace_id}".encode("utf-8")).hexdigest()[:12]
        return f"{prefix}-{digest}"


def admit_codex_request(request: Mapping[str, Any]) -> AdmissionResult:
    """Module-level convenience entrypoint for AEX admission."""
    return AEXEngine().admit_codex_request(request)


def admit_and_handoff_to_tlc(
    codex_request: Mapping[str, Any],
    *,
    tlc_runner: Callable[[dict[str, Any]], dict[str, Any]],
    tlc_request: dict[str, Any],
) -> dict[str, Any]:
    """Enforce AEX admission before TLC is invoked for repo-mutating work."""
    result = admit_codex_request(codex_request)
    if not result.accepted:
        raise ValueError("repo_mutation_without_admission")
    handoff = dict(tlc_request)
    handoff["build_admission_record"] = result.build_admission_record
    handoff["normalized_execution_request"] = result.normalized_execution_request
    handoff["repo_mutation_requested"] = bool(result.normalized_execution_request and result.normalized_execution_request.get("repo_mutation_requested"))
    return tlc_runner(handoff)
