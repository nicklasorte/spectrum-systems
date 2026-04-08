"""Typed models for AEX admission input/output surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CodexBuildRequest:
    request_id: str
    prompt_text: str
    trace_id: str
    created_at: str
    produced_by: str
    target_paths: list[str]
    requested_outputs: list[str]
    source_prompt_kind: str = "codex_build_request"


@dataclass(frozen=True)
class AdmissionResult:
    normalized_execution_request: dict[str, Any] | None
    build_admission_record: dict[str, Any] | None
    admission_rejection_record: dict[str, Any] | None

    @property
    def accepted(self) -> bool:
        return self.build_admission_record is not None and self.admission_rejection_record is None
