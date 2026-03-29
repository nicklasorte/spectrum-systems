from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.pqx_backbone import (
    RoadmapRow,
    parse_system_roadmap,
    resolve_roadmap_authority,
    resolve_executable_row,
    schedule_next_bundle,
    run_pqx_backbone,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ROADMAP_PATH = REPO_ROOT / "docs" / "roadmap" / "system_roadmap.md"
ACTIVE_PATH = REPO_ROOT / "docs" / "roadmaps" / "system_roadmap.md"


class _FixedClock:
    def __init__(self) -> None:
        self._ticks = 0

    def __call__(self):
        from datetime import datetime, timedelta, timezone

        base = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)
        value = base + timedelta(seconds=self._ticks)
        self._ticks += 1
        return value


def test_roadmap_parser_extracts_rows_and_dependencies() -> None:
    rows = parse_system_roadmap(ROADMAP_PATH)
    assert rows, "Parser must extract roadmap rows"

    assert rows[0].row_index == 0
    assert rows[1].row_index == 1

    ai02 = next(row for row in rows if row.step_id == "AI-02")
    assert ai02.dependencies == ("AI-01",)
    assert ai02.status == "VALID"


def test_authority_resolution_selects_legacy_execution_mirror() -> None:
    resolution = resolve_roadmap_authority()
    assert resolution.execution_roadmap_path == ROADMAP_PATH
    assert resolution.execution_roadmap_ref == "docs/roadmap/system_roadmap.md"
    assert resolution.active_authority_path == ACTIVE_PATH
    assert resolution.active_authority_ref == "docs/roadmaps/system_roadmap.md"


def test_authority_resolution_fails_closed_on_missing_bridge_statement(tmp_path: Path) -> None:
    authority_path = tmp_path / "roadmap_authority.md"
    authority_path.write_text(
        "# Roadmap Authority\n- **Active editorial authority:** `docs/roadmaps/system_roadmap.md`\n",
        encoding="utf-8",
    )
    active_path = tmp_path / "active.md"
    active_path.write_text(
        "Compatibility transition rule: `docs/roadmap/system_roadmap.md` is a required parseable operational mirror",
        encoding="utf-8",
    )
    legacy_path = tmp_path / "legacy.md"
    legacy_path.write_text(
        "Active editorial roadmap authority: `docs/roadmaps/system_roadmap.md`\ndocs/roadmap/roadmap_step_contract.md",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="legacy compatibility mirror declaration"):
        resolve_roadmap_authority(
            authority_path=authority_path,
            active_path=active_path,
            legacy_execution_path=legacy_path,
        )


def test_dependency_resolver_blocks_incomplete_dependency() -> None:
    rows = parse_system_roadmap(ROADMAP_PATH)
    state = {
        "schema_version": "1.0.0",
        "rows": [
            {
                "step_id": "AI-01",
                "status": "not_started",
                "last_run": None,
                "dependencies_satisfied": False,
                "retries": 0,
            }
        ],
    }

    row, block = resolve_executable_row(rows, state, step_id="AI-02")
    assert row is None
    assert block is not None
    assert block["block_type"] == "DEPENDENCY_UNSATISFIED"
    assert block["blocking_dependencies"] == ["AI-01"]


def test_dependency_resolver_selects_lowest_row_index_with_satisfied_dependencies() -> None:
    rows = [
        RoadmapRow(row_index=0, step_id="STEP-20", step_name="A", dependencies=("STEP-30",), status="VALID"),
        RoadmapRow(row_index=1, step_id="STEP-30", step_name="B", dependencies=(), status="VALID"),
        RoadmapRow(row_index=2, step_id="STEP-10", step_name="C", dependencies=(), status="VALID"),
    ]
    state = {"schema_version": "1.0.0", "rows": []}

    row, block = resolve_executable_row(rows, state)
    assert block is None
    assert row is not None
    assert row.step_id == "STEP-30"


def test_runner_fail_closed_when_step_missing(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}), encoding="utf-8")

    result = run_pqx_backbone(
        selected_step_id="DOES-NOT-EXIST",
        pqx_output_text="synthetic-output",
        roadmap_path=ROADMAP_PATH,
        state_path=state_path,
        runs_root=tmp_path / "pqx_runs",
        clock=_FixedClock(),
    )

    assert result["status"] == "blocked"
    assert result["block_type"] == "INVALID_EXECUTION_ENTRYPOINT"


def test_runner_persists_artifacts_and_state_on_success(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}), encoding="utf-8")

    result = run_pqx_backbone(
        selected_step_id="AI-01",
        pqx_output_text="PQX completed AI-01.",
        roadmap_path=ROADMAP_PATH,
        state_path=state_path,
        runs_root=tmp_path / "pqx_runs",
        clock=_FixedClock(),
    )

    assert result["status"] == "complete"

    state = json.loads(state_path.read_text(encoding="utf-8"))
    ai01 = next(row for row in state["rows"] if row["step_id"] == "AI-01")
    assert ai01["status"] == "complete"
    assert ai01["dependencies_satisfied"] is True

    execution_record_path = Path(result["slice_execution_record"])
    assert execution_record_path.exists()
    execution_record = json.loads(execution_record_path.read_text(encoding="utf-8"))
    assert execution_record["status"] == "completed"

    request = json.loads(Path(result["request"]).read_text(encoding="utf-8"))
    assert request["roadmap_version"] == "docs/roadmap/system_roadmap.md"
    assert request["row_snapshot"]["step_id"] == "AI-01"


def test_schedule_next_bundle_blocks_ambiguous_candidates(tmp_path: Path) -> None:
    plan_path = tmp_path / "execution_bundles.md"
    plan_path.write_text(
        "\n".join(
            [
                "# test",
                "## EXECUTABLE BUNDLE TABLE",
                "| Bundle ID | Ordered Step IDs | Depends On |",
                "| --- | --- | --- |",
                "| BUNDLE-A | AI-01 | - |",
                "| BUNDLE-B | AI-02 | - |",
                "",
            ]
        ),
        encoding="utf-8",
    )
    decision = schedule_next_bundle(
        bundle_states={
            "BUNDLE-A": {"status": "pending", "readiness_approved": True, "unresolved_findings": [], "pending_fix_ids": []},
            "BUNDLE-B": {"status": "pending", "readiness_approved": True, "unresolved_findings": [], "pending_fix_ids": []},
        },
        run_id="run-sched-1",
        trace_id="trace-sched-1",
        bundle_plan_path=plan_path,
        clock=_FixedClock(),
    )
    assert decision["block_type"] == "AMBIGUOUS_RUNNABLE_BUNDLE"
