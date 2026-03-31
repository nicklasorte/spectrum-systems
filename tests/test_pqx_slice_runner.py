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


def _impact_artifact(*, compatibility_class: str, blocking: bool, safe_to_execute: bool) -> dict:
    return {
        "artifact_type": "contract_impact_artifact",
        "schema_version": "1.0.0",
        "impact_id": "f11d5d12f47f7547d6119d91d4d5633c59dca95f3f899f1fdd0a4af11e0189ce",
        "generated_at": "2026-03-30T00:00:00Z",
        "analyzer_version": "1.0.0",
        "standards_manifest_path": "contracts/standards-manifest.json",
        "changed_contract_paths": ["contracts/schemas/pqx_execution_result.schema.json"],
        "changed_example_paths": ["contracts/examples/pqx_execution_result.json"],
        "impacted_consumer_paths": [],
        "impacted_test_paths": [],
        "impacted_runtime_paths": [],
        "impacted_script_paths": [],
        "compatibility_class": compatibility_class,
        "blocking": blocking,
        "blocking_reasons": ["test blocking reason"] if blocking else [],
        "required_remediations": ["test remediation"] if blocking else [],
        "safe_to_execute": safe_to_execute,
        "evidence_refs": ["contracts/standards-manifest.json"],
        "summary": "test",
    }


def test_run_pqx_slice_blocks_on_breaking_contract_impact(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    impact_path = tmp_path / "impact.json"
    impact_path.write_text(json.dumps(_impact_artifact(compatibility_class="breaking", blocking=True, safe_to_execute=False)))

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        contract_impact_artifact_path=impact_path,
        clock=FixedClock(),
    )
    assert result["status"] == "blocked"
    assert result["block_type"] == "CONTRACT_IMPACT_BLOCKED"


def test_run_pqx_slice_blocks_on_indeterminate_contract_impact(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    impact_path = tmp_path / "impact-indeterminate.json"
    impact_path.write_text(json.dumps(_impact_artifact(compatibility_class="indeterminate", blocking=True, safe_to_execute=False)))

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        contract_impact_artifact_path=impact_path,
        clock=FixedClock(),
    )
    assert result["status"] == "blocked"
    assert result["block_type"] == "CONTRACT_IMPACT_BLOCKED"


def test_run_pqx_slice_allows_compatible_contract_impact(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    impact_path = tmp_path / "impact-compatible.json"
    impact_path.write_text(json.dumps(_impact_artifact(compatibility_class="compatible", blocking=False, safe_to_execute=True)))

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        contract_impact_artifact_path=impact_path,
        clock=FixedClock(),
    )
    assert result["status"] == "complete"
