from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.pqx_sequence_runner import PQXSequenceRunnerError, execute_sequence_run


def _slice_requests() -> list[dict[str, str]]:
    return [{"slice_id": "fix-step:plan", "trace_id": "trace-repo-write"}]


def _lineage() -> dict[str, object]:
    return {
        "build_admission_record": {
            "artifact_type": "build_admission_record",
            "admission_id": "adm-1",
            "request_id": "req-1",
            "execution_type": "repo_write",
            "admission_status": "accepted",
            "normalized_execution_request_ref": "normalized_execution_request:req-1",
            "trace_id": "trace-repo-write",
            "created_at": "2026-04-08T00:00:00Z",
            "produced_by": "AEXEngine",
            "reason_codes": [],
            "target_scope": {"repo": "spectrum-systems", "paths": ["x"]},
        },
        "normalized_execution_request": {
            "artifact_type": "normalized_execution_request",
            "request_id": "req-1",
            "prompt_text": "modify repo",
            "execution_type": "repo_write",
            "repo_mutation_requested": True,
            "target_paths": ["x"],
            "requested_outputs": ["patch"],
            "source_prompt_kind": "codex_build_request",
            "trace_id": "trace-repo-write",
            "created_at": "2026-04-08T00:00:00Z",
            "produced_by": "AEXEngine",
        },
        "tlc_handoff_record": {
            "tlc_mediated": True,
            "trace_id": "trace-repo-write",
            "request_id": "req-1",
            "build_admission_record_ref": "build_admission_record:adm-1",
            "handoff_id": "tlc-handoff-1",
        },
    }


def test_pqx_rejects_repo_write_without_aex_tlc_lineage(tmp_path: Path) -> None:
    with pytest.raises(PQXSequenceRunnerError, match="direct_pqx_repo_write_forbidden"):
        execute_sequence_run(
            slice_requests=_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-1",
            run_id="run-1",
            trace_id="trace-repo-write",
            max_slices=1,
            execution_class="repo_write",
        )


def test_pqx_rejects_repo_write_missing_trace_id(tmp_path: Path) -> None:
    lineage = _lineage()
    lineage["build_admission_record"]["trace_id"] = ""

    with pytest.raises(PQXSequenceRunnerError, match="direct_pqx_repo_write_forbidden"):
        execute_sequence_run(
            slice_requests=_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-1",
            run_id="run-1",
            trace_id="trace-repo-write",
            max_slices=1,
            execution_class="repo_write",
            repo_write_lineage=lineage,
        )


def test_pqx_allows_valid_repo_write_lineage(tmp_path: Path) -> None:
    state = execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=tmp_path / "state.json",
        queue_run_id="queue-1",
        run_id="run-1",
        trace_id="trace-repo-write",
        max_slices=1,
        execution_class="repo_write",
        repo_write_lineage=_lineage(),
    )
    assert state["status"] in {"completed", "blocked", "failed"}
