from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from spectrum_systems.modules.runtime.pqx_slice_runner import run_pqx_slice


class FixedClock:
    def __init__(self) -> None:
        self._tick = 0

    def __call__(self):
        base = datetime(2026, 3, 29, 22, 0, 0, tzinfo=timezone.utc)
        value = base + timedelta(seconds=self._tick)
        self._tick += 1
        return value


def test_run_pqx_slice_valid_run_emits_required_artifacts(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="deterministic output",
        clock=FixedClock(),
    )

    assert result["status"] == "complete"
    record = json.loads(Path(result["slice_execution_record"]).read_text(encoding="utf-8"))
    assert record["artifact_type"] == "pqx_slice_execution_record"
    assert record["certification_status"] == "certified"
    assert record["artifacts_emitted"]

    bundle = json.loads(Path(result["pqx_slice_audit_bundle"]).read_text(encoding="utf-8"))
    assert bundle["trace_ref"]
    assert bundle["replay_result_ref"]
    assert bundle["control_decision_ref"]
    assert bundle["certification_result_ref"]


def test_run_pqx_slice_invalid_step_blocks_entrypoint(tmp_path: Path) -> None:
    result = run_pqx_slice(
        step_id="NOT-A-ROW",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=tmp_path / "state.json",
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        clock=FixedClock(),
    )
    assert result["status"] == "blocked"
    assert result["block_type"] == "INVALID_EXECUTION_ENTRYPOINT"


def test_run_pqx_slice_missing_roadmap_blocks_entrypoint(tmp_path: Path) -> None:
    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=tmp_path / "missing.md",
        state_path=tmp_path / "state.json",
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        clock=FixedClock(),
    )
    assert result["status"] == "blocked"
    assert result["block_type"] == "INVALID_EXECUTION_ENTRYPOINT"


def test_run_pqx_slice_bypass_attempt_without_artifact_emission_blocks(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        emit_artifacts=False,
        clock=FixedClock(),
    )
    assert result["status"] == "blocked"
    assert result["block_type"] == "ARTIFACT_EMISSION_BLOCKED"
