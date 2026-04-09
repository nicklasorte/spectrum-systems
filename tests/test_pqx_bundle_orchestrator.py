from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from spectrum_systems.modules.pqx_backbone import parse_system_roadmap
from spectrum_systems.modules.runtime.pqx_bundle_orchestrator import (
    PQXBundleOrchestratorError,
    BundleDefinition,
    execute_bundle_run,
    load_bundle_plan,
    select_next_runnable_bundle,
    resolve_bundle_definition,
    validate_bundle_definition,
)
from spectrum_systems.modules.review_fix_execution_loop import compute_tpa_gate_provenance_token


class FixedClock:
    def __init__(self, stamps: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in stamps]

    def __call__(self):
        if self._values:
            return self._values.pop(0)
        return datetime(2026, 3, 29, 20, 0, 0, tzinfo=timezone.utc)


def _bundle_plan(
    tmp_path: Path,
    steps: str = "AI-01, AI-02, TRUST-01",
    review_table: str = "",
) -> Path:
    path = tmp_path / "execution_bundles.md"
    path.write_text(
        "\n".join(
            [
                "# Test",
                "## EXECUTABLE BUNDLE TABLE",
                "| Bundle ID | Ordered Step IDs | Depends On |",
                "| --- | --- | --- |",
                f"| BUNDLE-T1 | {steps} | - |",
                "",
                review_table,
            ]
        ),
        encoding="utf-8",
    )
    return path


def _review_table() -> str:
    return "\n".join(
        [
            "## REVIEW CHECKPOINT TABLE",
            "| Checkpoint ID | Bundle ID | Review Type | Scope | Step ID | Required | Blocking Before Continue |",
            "| --- | --- | --- | --- | --- | --- | --- |",
            "| BUNDLE-T1:checkpoint:AI-01 | BUNDLE-T1 | checkpoint_review | step | AI-01 | true | true |",
            "",
        ]
    )


def test_valid_bundle_resolution() -> None:
    plan = load_bundle_plan()
    definition = resolve_bundle_definition(plan, "BUNDLE-PQX-CORE")
    assert definition.ordered_step_ids[0] == "AI-01"


def test_invalid_missing_bundle_fails_closed(tmp_path: Path) -> None:
    path = _bundle_plan(tmp_path)
    plan = load_bundle_plan(path)
    with pytest.raises(PQXBundleOrchestratorError, match="bundle_id not found"):
        resolve_bundle_definition(plan, "BUNDLE-NOT-REAL")


def test_invalid_referenced_roadmap_step_fails_closed(tmp_path: Path) -> None:
    path = _bundle_plan(tmp_path, steps="AI-01, DOES-NOT-EXIST")
    definition = resolve_bundle_definition(load_bundle_plan(path), "BUNDLE-T1")
    with pytest.raises(PQXBundleOrchestratorError, match="unknown roadmap step IDs"):
        validate_bundle_definition(definition, parse_system_roadmap())


def test_bundle_blocks_when_required_review_missing(tmp_path: Path) -> None:
    plan_path = _bundle_plan(tmp_path, review_table=_review_table())
    result = execute_bundle_run(
        bundle_id="BUNDLE-T1",
        bundle_state_path=tmp_path / "state.json",
        output_dir=tmp_path / "out",
        run_id="run-b6-test-001",
        sequence_run_id="queue-run-b6-test-001",
        trace_id="trace-b6-test-001",
        bundle_plan_path=plan_path,
        execute_step=lambda _: {"execution_status": "success"},
        clock=FixedClock([f"2026-03-29T20:00:{i:02d}Z" for i in range(1, 30)]),
    )
    assert result["status"] == "blocked"
    record = json.loads((tmp_path / "out" / "BUNDLE-T1.bundle_execution_record.json").read_text(encoding="utf-8"))
    assert record["failure_classification"] == "REVIEW_REQUIRED"


def test_ordered_execution_still_completes_when_no_review_required(tmp_path: Path) -> None:
    plan_path = _bundle_plan(tmp_path)
    calls: list[str] = []

    def _executor(payload: dict) -> dict:
        calls.append(payload["slice_id"])
        return {"execution_status": "success"}

    result = execute_bundle_run(
        bundle_id="BUNDLE-T1",
        bundle_state_path=tmp_path / "state.json",
        output_dir=tmp_path / "out",
        run_id="run-b6-test-002",
        sequence_run_id="queue-run-b6-test-002",
        trace_id="trace-b6-test-002",
        bundle_plan_path=plan_path,
        execute_step=_executor,
        clock=FixedClock([f"2026-03-29T20:10:{i:02d}Z" for i in range(1, 30)]),
    )

    assert result["status"] == "completed"
    assert calls == ["AI-01", "AI-02", "TRUST-01"]


def test_build_triggers_review(tmp_path: Path) -> None:
    plan_path = _bundle_plan(tmp_path)
    result = execute_bundle_run(
        bundle_id="BUNDLE-T1",
        bundle_state_path=tmp_path / "state.json",
        output_dir=tmp_path / "out",
        run_id="run-bundle-rqx-001",
        sequence_run_id="queue-run-bundle-rqx-001",
        trace_id="trace-bundle-rqx-001",
        bundle_plan_path=plan_path,
        execute_step=lambda _: {"execution_status": "success"},
        clock=FixedClock([f"2026-03-29T20:30:{i:02d}Z" for i in range(1, 30)]),
    )
    assert result["status"] == "completed"
    assert Path(tmp_path / "out" / "BUNDLE-T1.review_request_artifact.json").exists()
    assert Path(tmp_path / "out" / result["review_result_artifact"]).exists()


def test_pqx_execution_triggers_rqx_review_for_bundle_record(tmp_path: Path) -> None:
    test_build_triggers_review(tmp_path)


def test_block_on_first_failure(tmp_path: Path) -> None:
    plan_path = _bundle_plan(tmp_path)

    def _executor(payload: dict) -> dict:
        if payload["slice_id"] == "AI-02":
            return {"execution_status": "failed", "error": "step failed"}
        return {"execution_status": "success"}

    result = execute_bundle_run(
        bundle_id="BUNDLE-T1",
        bundle_state_path=tmp_path / "state.json",
        output_dir=tmp_path / "out",
        run_id="run-b6-test-003",
        sequence_run_id="queue-run-b6-test-003",
        trace_id="trace-b6-test-003",
        bundle_plan_path=plan_path,
        execute_step=_executor,
        clock=FixedClock([f"2026-03-29T20:20:{i:02d}Z" for i in range(1, 30)]),
    )

    record = json.loads((tmp_path / "out" / "BUNDLE-T1.bundle_execution_record.json").read_text(encoding="utf-8"))
    assert result["status"] == "blocked"
    assert record["blocked_step_id"] == "AI-02"


def test_authority_plan_mismatch_on_resume_fails_closed(tmp_path: Path) -> None:
    plan_path = _bundle_plan(tmp_path, steps="AI-01")
    execute_bundle_run(
        bundle_id="BUNDLE-T1",
        bundle_state_path=tmp_path / "state.json",
        output_dir=tmp_path / "out",
        run_id="run-b6-test-004",
        sequence_run_id="queue-run-b6-test-004",
        trace_id="trace-b6-test-004",
        bundle_plan_path=plan_path,
        execute_step=lambda _: {"execution_status": "success"},
    )

    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    state["execution_plan_ref"] = "docs/roadmaps/other.md"
    (tmp_path / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(PQXBundleOrchestratorError, match="execution_plan_ref mismatch"):
        execute_bundle_run(
            bundle_id="BUNDLE-T1",
            bundle_state_path=tmp_path / "state.json",
            output_dir=tmp_path / "out",
            run_id="run-b6-test-004",
            sequence_run_id="queue-run-b6-test-004",
            trace_id="trace-b6-test-004",
            bundle_plan_path=plan_path,
            execute_step=lambda _: {"execution_status": "success"},
        )


def test_execute_fixes_records_fix_gate_before_step_progression(tmp_path: Path) -> None:
    plan_path = _bundle_plan(tmp_path, steps="AI-01, AI-02")
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "1.3.0",
                "roadmap_authority_ref": "docs/roadmaps/system_roadmap.md",
                "execution_plan_ref": str(plan_path),
                "run_id": "run-gate-block-001",
                "sequence_run_id": "queue-run-gate-block-001",
                "active_bundle_id": "BUNDLE-T1",
                "completed_bundle_ids": [],
                "completed_step_ids": [],
                "blocked_step_ids": [],
                "pending_fix_ids": [
                    {
                        "fix_id": "fix:REV-BLOCK:F-001",
                        "source_review_id": "REV-BLOCK",
                        "source_finding_id": "F-001",
                        "severity": "high",
                        "priority": "P1",
                        "affected_step_ids": ["AI-01"],
                        "status": "open",
                        "blocking": True,
                        "created_from_bundle_id": "BUNDLE-T1",
                        "created_from_run_id": "run-gate-block-001",
                        "notes": "patch runtime",
                        "artifact_refs": ["docs/reviews/REV-BLOCK.md#f1"],
                    }
                ],
                "executed_fixes": [],
                "failed_fixes": [],
                "fix_artifacts": {},
                "reinsertion_points": {},
                "fix_gate_results": {},
                "resolved_fixes": [],
                "unresolved_fixes": [],
                "last_fix_gate_status": None,
                "review_artifact_refs": [],
                "review_requirements": [],
                "satisfied_review_checkpoint_ids": [],
                "artifact_index": {},
                "resume_position": {
                    "bundle_id": "BUNDLE-T1",
                    "next_step_id": "AI-01",
                    "resume_token": "resume:queue-run-gate-block-001:BUNDLE-T1:0",
                },
                "created_at": "2026-03-29T12:00:00Z",
                "updated_at": "2026-03-29T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    tpa_artifact = {
        "artifact_type": "tpa_slice_artifact",
        "schema_version": "1.2.0",
        "artifact_id": "tpa:fix:rev-block:f-001:gate",
        "run_id": "run-gate-block-001",
        "trace_id": "trace-gate-block-001",
        "slice_id": "AI-01-G",
        "step_id": "AI-01",
        "phase": "gate",
        "produced_at": "2026-04-09T00:00:00Z",
        "artifact": {
            "artifact_kind": "gate",
            "promotion_ready": True,
            "high_risk_unmitigated": False,
            "fail_closed_reason": None,
            "review_signal_refs": ["review_result_artifact:REV-BLOCK"],
            "selection_inputs": {"comparison_inputs_present": True},
            "complexity_regression_gate": {"decision": "allow"},
            "simplicity_review": {"decision": "allow"},
        },
    }
    authority_path = tmp_path / "artifacts/tpa_authority" / f"{tpa_artifact['artifact_id']}.json"
    authority_path.parent.mkdir(parents=True, exist_ok=True)
    stored = dict(tpa_artifact)
    stored["authoritative_integrity_token"] = compute_tpa_gate_provenance_token(tpa_artifact)
    authority_path.write_text(json.dumps(stored, indent=2) + "\n", encoding="utf-8")

    result = execute_bundle_run(
        bundle_id="BUNDLE-T1",
        bundle_state_path=state_path,
        output_dir=tmp_path / "out",
        run_id="run-gate-block-001",
        sequence_run_id="queue-run-gate-block-001",
        trace_id="trace-gate-block-001",
        bundle_plan_path=plan_path,
        execute_step=lambda _: {"execution_status": "success"},
        execute_fixes=True,
        tpa_gate_artifacts_by_fix_id={
            "fix:REV-BLOCK:F-001": {
                "request_artifact": {
                    "source_review_result_ref": "review_result_artifact:REV-BLOCK",
                    "fix_slices": [{"review_result_ref": "review_result_artifact:REV-BLOCK"}],
                    "tpa_slice_artifact": tpa_artifact,
                }
            }
        },
    )
    assert result["status"] == "completed"
    assert result["failure_classification"] is None
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["last_fix_gate_status"] == "passed"
    assert state["resolved_fixes"] == ["fix:REV-BLOCK:F-001"]


def test_emit_triage_plan_on_blocked_review_findings(tmp_path: Path) -> None:
    plan_path = _bundle_plan(tmp_path, review_table=_review_table())
    state_path = tmp_path / "state.json"
    out_dir = tmp_path / "out"
    execute_bundle_run(
        bundle_id="BUNDLE-T1",
        bundle_state_path=state_path,
        output_dir=out_dir,
        run_id="run-b10-orch-001",
        sequence_run_id="queue-run-b10-orch-001",
        trace_id="trace-b10-orch-001",
        bundle_plan_path=plan_path,
        execute_step=lambda _: {"execution_status": "success"},
    )
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "review_id": "REV-B10-001",
                "checkpoint_id": "BUNDLE-T1:checkpoint:AI-01",
                "review_type": "checkpoint_review",
                "bundle_id": "BUNDLE-T1",
                "bundle_run_id": "queue-run-b10-orch-001",
                "roadmap_authority_ref": "docs/roadmaps/system_roadmap.md",
                "execution_plan_ref": str(plan_path),
                "scope": {"scope_type": "step", "step_id": "AI-01"},
                "findings": [
                    {
                        "finding_id": "F-100",
                        "severity": "high",
                        "category": "runtime",
                        "title": "gap",
                        "description": "gap",
                        "affected_step_ids": ["AI-01"],
                        "recommended_action": "fix",
                        "blocking": True,
                        "source_refs": ["docs/review-actions/REV-B10-001.md#F-100"],
                    }
                ],
                "overall_disposition": "approved_with_findings",
                "created_at": "2026-03-29T12:00:00Z",
                "provenance_refs": ["trace:b10:1"],
            }
        ),
        encoding="utf-8",
    )
    from spectrum_systems.modules.runtime.pqx_bundle_state import ingest_review_result, load_bundle_state, save_bundle_state

    definition = resolve_bundle_definition(load_bundle_plan(plan_path), "BUNDLE-T1")
    bundle_plan = [{"bundle_id": definition.bundle_id, "step_ids": list(definition.ordered_step_ids), "depends_on": []}]
    state = load_bundle_state(state_path, bundle_plan=bundle_plan)
    updated = ingest_review_result(
        state,
        bundle_plan,
        review_artifact=json.loads(review_path.read_text(encoding="utf-8")),
        artifact_ref=str(review_path),
        now="2026-03-29T12:01:00Z",
    )
    save_bundle_state(updated, state_path, bundle_plan=bundle_plan)

    result = execute_bundle_run(
        bundle_id="BUNDLE-T1",
        bundle_state_path=state_path,
        output_dir=out_dir,
        run_id="run-b10-orch-001",
        sequence_run_id="queue-run-b10-orch-001",
        trace_id="trace-b10-orch-001",
        bundle_plan_path=plan_path,
        execute_step=lambda _: {"execution_status": "success"},
        emit_triage_plan=True,
    )
    assert result["triage_plan_record"] is not None
    triage = json.loads((out_dir / "BUNDLE-T1.triage_plan_record.json").read_text(encoding="utf-8"))
    assert triage["summary_counts"]["findings_total"] >= 1


def test_bundle_orchestrator_default_executor_routes_to_canonical_slice_runner(tmp_path: Path) -> None:
    plan_path = _bundle_plan(tmp_path, steps="AI-01")
    result = execute_bundle_run(
        bundle_id="BUNDLE-T1",
        bundle_state_path=tmp_path / "state.json",
        output_dir=tmp_path / "out",
        run_id="run-default-bundle-001",
        sequence_run_id="queue-run-default-bundle-001",
        trace_id="trace-default-bundle-001",
        bundle_plan_path=plan_path,
        clock=FixedClock([f"2026-03-29T23:00:{i:02d}Z" for i in range(1, 40)]),
    )
    assert result["status"] == "completed"
    assert result["judgment_record_refs"]


def test_scheduler_prefers_dependency_valid_bundle_and_blocks_unready_candidates() -> None:
    decision = select_next_runnable_bundle(
        bundle_plan=[
            BundleDefinition(bundle_id="BUNDLE-A", ordered_step_ids=("AI-01",), depends_on=()),
            BundleDefinition(bundle_id="BUNDLE-B", ordered_step_ids=("AI-02",), depends_on=("BUNDLE-A",)),
        ],
        bundle_states={
            "BUNDLE-A": {"status": "pending", "readiness_approved": True, "unresolved_findings": [], "pending_fix_ids": []},
            "BUNDLE-B": {"status": "pending", "readiness_approved": False, "unresolved_findings": [], "pending_fix_ids": []},
        },
        run_id="run-scheduler-bundle-test",
        trace_id="trace-scheduler-bundle-test",
        now="2026-03-29T00:00:00Z",
    )
    assert decision["selected_bundle_id"] == "BUNDLE-A"
