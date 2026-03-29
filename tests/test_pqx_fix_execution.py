from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.pqx_bundle_orchestrator import execute_bundle_run
from spectrum_systems.modules.runtime.pqx_bundle_state import (
    initialize_bundle_state,
    ingest_review_result,
    save_bundle_state,
)
from spectrum_systems.modules.runtime.pqx_fix_execution import (
    PQXFixExecutionError,
    determine_fix_insertion_point,
    execute_fix_step,
    normalize_fix_into_step,
    record_fix_result,
    update_bundle_state_with_fix,
    validate_fix_step,
)


def _bundle_plan(path: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                "# Test",
                "## EXECUTABLE BUNDLE TABLE",
                "| Bundle ID | Ordered Step IDs | Depends On |",
                "| --- | --- | --- |",
                "| BUNDLE-T1 | AI-01, AI-02 | - |",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _state_with_pending_fix(tmp_path: Path, execution_plan_ref: str) -> tuple[dict, list[dict]]:
    bundle_plan = [{"bundle_id": "BUNDLE-T1", "step_ids": ["AI-01", "AI-02"], "depends_on": []}]
    state = initialize_bundle_state(
        bundle_plan=bundle_plan,
        run_id="run-fix-001",
        sequence_run_id="queue-run-fix-001",
        roadmap_authority_ref="docs/roadmaps/system_roadmap.md",
        execution_plan_ref=execution_plan_ref,
        now="2026-03-29T12:00:00Z",
        review_requirements=[
            {
                "checkpoint_id": "BUNDLE-T1:checkpoint:AI-01",
                "bundle_id": "BUNDLE-T1",
                "review_type": "checkpoint_review",
                "scope": "step",
                "step_id": "AI-01",
                "required": True,
                "blocking_review_before_continue": True,
            }
        ],
    )
    review = {
        "schema_version": "1.0.0",
        "review_id": "REV-FIX-001",
        "checkpoint_id": "BUNDLE-T1:checkpoint:AI-01",
        "review_type": "checkpoint_review",
        "bundle_id": "BUNDLE-T1",
        "bundle_run_id": "queue-run-fix-001",
        "roadmap_authority_ref": "docs/roadmaps/system_roadmap.md",
        "execution_plan_ref": execution_plan_ref,
        "scope": {"scope_type": "step", "step_id": "AI-01"},
        "findings": [
            {
                "finding_id": "F-001",
                "severity": "high",
                "category": "architecture",
                "title": "fix it",
                "description": "needs deterministic patch",
                "affected_step_ids": ["AI-02"],
                "recommended_action": "patch runtime",
                "blocking": True,
                "source_refs": ["docs/reviews/REV-FIX-001.md#f1"],
            }
        ],
        "overall_disposition": "approved_with_findings",
        "created_at": "2026-03-29T12:01:00Z",
        "provenance_refs": ["trace:rev:fix:001"],
    }
    updated = ingest_review_result(
        state,
        bundle_plan,
        review_artifact=review,
        artifact_ref="docs/reviews/REV-FIX-001.json",
        now="2026-03-29T12:01:01Z",
    )
    save_bundle_state(updated, tmp_path / "bundle_state.json", bundle_plan=bundle_plan)
    return updated, bundle_plan


def test_fix_converts_to_step_correctly() -> None:
    fix = {
        "fix_id": "fix:REV:F-1",
        "affected_step_ids": ["AI-02"],
        "severity": "high",
        "notes": "patch runtime",
        "created_from_run_id": "run-fix-001",
    }
    step = normalize_fix_into_step(fix)
    assert step["fix_id"] == "fix:REV:F-1"
    assert step["source_step_id"] == "AI-02"
    assert step["action_type"] == "patch"
    assert step["target"] == "runtime"


def test_insertion_point_is_deterministic() -> None:
    step = {
        "fix_step_id": "fix-step:1",
        "fix_id": "fix:1",
        "source_step_id": "AI-02",
        "severity": "high",
        "action_type": "patch",
        "target": "runtime",
        "trace_id": "trace:1",
        "run_id": "run:1",
    }
    roadmap = ["AI-01", "AI-02", "TRUST-01"]
    insertion_a = determine_fix_insertion_point(step, roadmap)
    insertion_b = determine_fix_insertion_point(step, roadmap)
    assert insertion_a == insertion_b
    assert insertion_a["ordered_index"] == 2


def test_fix_execution_produces_artifacts() -> None:
    step = {
        "fix_step_id": "fix-step:2",
        "fix_id": "fix:2",
        "source_step_id": "AI-02",
        "severity": "high",
        "action_type": "patch",
        "target": "runtime",
        "trace_id": "trace:2",
        "run_id": "run:2",
    }

    result = execute_fix_step(
        step,
        lambda _: {"execution_status": "complete", "artifacts": ["out/fix-2.json"], "validation_result": "passed"},
    )
    assert result["artifacts"] == ["out/fix-2.json"]


def test_failed_fix_blocks_execution() -> None:
    step = {
        "fix_step_id": "fix-step:3",
        "fix_id": "fix:3",
        "source_step_id": "AI-02",
        "severity": "high",
        "action_type": "patch",
        "target": "runtime",
        "trace_id": "trace:3",
        "run_id": "run:3",
    }
    result = execute_fix_step(
        step,
        lambda _: {"execution_status": "failed", "artifacts": ["out/fix-3.json"], "validation_result": "failed"},
    )
    assert result["execution_status"] == "failed"


def test_conflicting_fixes_fail_closed() -> None:
    step = {
        "fix_step_id": "AI-02",
        "fix_id": "fix:4",
        "source_step_id": "AI-02",
        "severity": "high",
        "action_type": "patch",
        "target": "runtime",
        "trace_id": "trace:4",
        "run_id": "run:4",
    }
    with pytest.raises(PQXFixExecutionError, match="conflicts with existing roadmap step"):
        validate_fix_step(step, ["AI-01", "AI-02"])


def test_replay_produces_identical_results() -> None:
    step = {
        "fix_step_id": "fix-step:5",
        "fix_id": "fix:5",
        "source_step_id": "AI-02",
        "severity": "high",
        "action_type": "patch",
        "target": "runtime",
        "trace_id": "trace:5",
        "run_id": "run:5",
    }
    runner = lambda _: {"execution_status": "complete", "artifacts": ["out/fix-5.json"], "validation_result": "passed"}
    assert execute_fix_step(step, runner) == execute_fix_step(step, runner)


def test_bundle_resumes_correctly_after_fixes(tmp_path: Path) -> None:
    plan_path = _bundle_plan(tmp_path / "execution_bundles.md")
    state, bundle_plan = _state_with_pending_fix(tmp_path, str(plan_path))
    save_bundle_state(state, tmp_path / "bundle_state.json", bundle_plan=bundle_plan)

    result = execute_bundle_run(
        bundle_id="BUNDLE-T1",
        bundle_state_path=tmp_path / "bundle_state.json",
        output_dir=tmp_path / "out",
        run_id="run-fix-001",
        sequence_run_id="queue-run-fix-001",
        trace_id="trace-fix-001",
        bundle_plan_path=plan_path,
        execute_fixes=True,
    )

    assert result["status"] == "completed"
    persisted = json.loads((tmp_path / "bundle_state.json").read_text(encoding="utf-8"))
    assert "fix:REV-FIX-001:F-001" in persisted["executed_fixes"]
    assert persisted["pending_fix_ids"][0]["status"] == "complete"


def test_record_and_state_update_round_trip() -> None:
    bundle_state = {
        "completed_step_ids": ["AI-01", "AI-02"],
        "pending_fix_ids": [{"fix_id": "fix:6", "affected_step_ids": ["AI-02"], "status": "open"}],
        "executed_fixes": [],
        "failed_fixes": [],
        "fix_artifacts": {},
        "reinsertion_points": {},
    }
    fix_step = {
        "fix_step_id": "fix-step:6",
        "fix_id": "fix:6",
        "source_step_id": "AI-02",
        "severity": "high",
        "action_type": "patch",
        "target": "runtime",
        "trace_id": "trace:6",
        "run_id": "run:6",
    }
    result = {"execution_status": "complete", "artifacts": ["out/fix-6.json"], "validation_result": "passed"}
    record = record_fix_result(bundle_state, fix_step, result)
    updated = update_bundle_state_with_fix(bundle_state, record)
    assert updated["executed_fixes"] == ["fix:6"]
