from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.lineage_authenticity import issue_authenticity
from spectrum_systems.modules.runtime.pqx_sequence_runner import PQXSequenceRunnerError, execute_sequence_run
from spectrum_systems.modules.runtime.top_level_conductor import TopLevelConductorError, run_top_level_conductor


def _base_request(tmp_path: Path) -> dict[str, object]:
    review_path = tmp_path / "review.md"
    action_path = tmp_path / "actions.md"
    review_path.write_text(
        "---\nmodule: tpa\nreview_date: 2026-04-08\n---\n# Review\n\n## Overall Assessment\n**Overall Verdict: CONDITIONAL PASS**\n",
        encoding="utf-8",
    )
    action_path.write_text(
        "# Action Tracker\n\n## Critical Items\n| ID | Risk | Severity | Recommended Action | Status | Notes |\n| --- | --- | --- | --- | --- | --- |\n| CR-1 | Blocking risk | Critical | Fix | Closed | fixed |\n",
        encoding="utf-8",
    )
    request = {
        "objective": "repo mutating run",
        "branch_ref": "refs/heads/main",
        "run_id": "tlc-handoff-flow",
        "retry_budget": 0,
        "require_review": False,
        "require_recovery": False,
        "runtime_dir": str(tmp_path / "runtime"),
        "emitted_at": "2026-04-08T00:00:00Z",
        "review_path": str(review_path),
        "action_tracker_path": str(action_path),
        "repo_mutation_requested": True,
        "build_admission_record": {
            "artifact_type": "build_admission_record",
            "admission_id": "adm-flow-1",
            "request_id": "req-flow-1",
            "execution_type": "repo_write",
            "admission_status": "accepted",
            "normalized_execution_request_ref": "normalized_execution_request:req-flow-1",
            "trace_id": "trace-tlc-handoff-flow",
            "created_at": "2026-04-08T00:00:00Z",
            "produced_by": "AEXEngine",
            "reason_codes": [],
            "target_scope": {"repo": "spectrum-systems", "paths": ["x"]},
        },
        "normalized_execution_request": {
            "artifact_type": "normalized_execution_request",
            "request_id": "req-flow-1",
            "prompt_text": "Modify file",
            "execution_type": "repo_write",
            "repo_mutation_requested": True,
            "target_paths": ["x"],
            "requested_outputs": ["patch"],
            "source_prompt_kind": "codex_build_request",
            "trace_id": "trace-tlc-handoff-flow",
            "created_at": "2026-04-08T00:00:00Z",
            "produced_by": "AEXEngine",
        },
    }
    request["build_admission_record"]["authenticity"] = issue_authenticity(
        artifact=request["build_admission_record"], issuer="AEX"
    )
    request["normalized_execution_request"]["authenticity"] = issue_authenticity(
        artifact=request["normalized_execution_request"], issuer="AEX"
    )
    return request


def test_valid_repo_write_path_uses_tlc_handoff_record(tmp_path: Path) -> None:
    captured_payload: dict[str, object] = {}

    def _pqx_spy(payload: dict[str, object]) -> dict[str, object]:
        captured_payload.update(payload)
        return {
            "entry_valid": True,
            "validation_passed": True,
            "artifact_refs": ["pqx_execution_record:1"],
            "trace_refs": [str(payload.get("trace_id"))],
            "lineage": {"lineage_id": "lineage:pqx:1", "parent_refs": []},
            "request_artifact": {
                "schema_version": "1.1.0",
                "run_id": str(payload.get("run_id")),
                "step_id": "TLC-EXECUTE",
                "step_name": "Execute bounded TLC request",
                "dependencies": [],
                "requested_at": "2026-04-08T00:00:00Z",
                "prompt": "Apply admitted repo write request.",
                "roadmap_version": None,
                "row_snapshot": None,
            },
            "execution_artifact": {
                "schema_version": "1.0.0",
                "run_id": str(payload.get("run_id")),
                "step_id": "TLC-EXECUTE",
                "execution_status": "success",
                "started_at": "2026-04-08T00:00:00Z",
                "completed_at": "2026-04-08T00:00:00Z",
                "output_text": "ok",
                "error": None,
            },
        }

    request = _base_request(tmp_path)
    request["subsystems"] = {"pqx": _pqx_spy}
    result = run_top_level_conductor(request)

    handoff = ((captured_payload.get("repo_write_lineage") or {}) if isinstance(captured_payload, dict) else {}).get("tlc_handoff_record")
    assert isinstance(handoff, dict)
    assert handoff["artifact_type"] == "tlc_handoff_record"
    assert handoff["trace_id"] == "trace-tlc-handoff-flow"
    assert handoff["lineage"]["upstream_refs"] == [
        "build_admission_record:adm-flow-1",
        "normalized_execution_request:req-flow-1",
    ]
    assert handoff["lineage"]["intended_path"] == ["TLC", "TPA", "PQX"]
    assert "trace-tlc-handoff-flow" in result["trace_refs"]


def test_repo_write_path_fails_closed_when_handoff_missing(tmp_path: Path) -> None:
    base = _base_request(tmp_path)
    with pytest.raises(PQXSequenceRunnerError, match="direct_pqx_repo_write_forbidden"):
        execute_sequence_run(
            slice_requests=[{"slice_id": "fix-step:plan", "trace_id": "trace-repo-write"}],
            state_path=tmp_path / "state.json",
            queue_run_id="queue-1",
            run_id="run-1",
            trace_id="trace-repo-write",
            max_slices=1,
            execution_class="repo_write",
            repo_write_lineage={
                "build_admission_record": base["build_admission_record"],
                "normalized_execution_request": base["normalized_execution_request"],
            },
        )


def test_no_regression_direct_pqx_repo_write_path_still_rejected(tmp_path: Path) -> None:
    request = _base_request(tmp_path)

    def _bad_pqx(_payload: dict[str, object]) -> dict[str, object]:
        raise TopLevelConductorError("direct_pqx_repo_write_forbidden")

    request["subsystems"] = {"pqx": _bad_pqx}

    with pytest.raises(TopLevelConductorError, match="direct_pqx_repo_write_forbidden"):
        run_top_level_conductor(request)
