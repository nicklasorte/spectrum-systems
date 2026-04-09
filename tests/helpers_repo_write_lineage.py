from __future__ import annotations

from copy import deepcopy
from typing import Any

from spectrum_systems.aex.engine import AEXEngine
from spectrum_systems.modules.runtime.top_level_conductor import _build_tlc_handoff_record


def build_valid_repo_write_lineage(
    *,
    request_id: str = "req-1",
    trace_id: str = "trace-repo-write",
    created_at: str = "2026-04-08T00:00:00Z",
) -> dict[str, Any]:
    admission_result = AEXEngine().admit_codex_request(
        {
            "request_id": request_id,
            "prompt_text": "modify repo",
            "trace_id": trace_id,
            "created_at": created_at,
            "produced_by": "AEXEngine",
            "target_paths": ["x"],
            "requested_outputs": ["patch"],
            "source_prompt_kind": "codex_build_request",
        }
    )
    if not admission_result.accepted or not admission_result.build_admission_record or not admission_result.normalized_execution_request:
        raise RuntimeError("failed to build valid lineage fixture")

    handoff = _build_tlc_handoff_record(
        run_id="tlc-aex-check",
        objective="repo mutation",
        branch_ref="refs/heads/main",
        emitted_at=created_at,
        repo_write_lineage={
            "request_id": request_id,
            "trace_id": trace_id,
            "admission_id": str(admission_result.build_admission_record["admission_id"]),
            "normalized_execution_request_ref": f"normalized_execution_request:{request_id}",
        },
    )
    return {
        "build_admission_record": deepcopy(admission_result.build_admission_record),
        "normalized_execution_request": deepcopy(admission_result.normalized_execution_request),
        "tlc_handoff_record": deepcopy(handoff),
    }
