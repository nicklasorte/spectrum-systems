from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from spectrum_systems.modules.pqx_backbone import parse_system_roadmap
from spectrum_systems.modules.runtime.pqx_bundle_orchestrator import (
    PQXBundleOrchestratorError,
    execute_bundle_run,
    load_bundle_plan,
    resolve_bundle_definition,
    validate_bundle_definition,
)


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
