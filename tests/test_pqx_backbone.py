from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.modules.pqx_backbone import (
    RoadmapRow,
    parse_system_roadmap,
    resolve_executable_row,
    run_pqx_backbone,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ROADMAP_PATH = REPO_ROOT / "docs" / "roadmap" / "system_roadmap.md"


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
    assert "block_record" in result
    block = json.loads(Path(result["block_record"]).read_text(encoding="utf-8"))
    assert block["block_type"] == "MISSING_ROW"
    assert block["blocking_dependencies"] == []


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

    summary_path = Path(result["summary"])
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["final_status"] == "complete"

    request = json.loads(Path(result["request"]).read_text(encoding="utf-8"))
    assert request["roadmap_version"] == "docs/roadmap/system_roadmap.md"
    assert request["row_snapshot"]["step_id"] == "AI-01"
