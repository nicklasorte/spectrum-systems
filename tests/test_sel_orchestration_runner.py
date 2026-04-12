from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.runtime.sel_orchestration_runner import (
    SELOrchestrationRunnerError,
    run_sel_orchestration,
    run_sel_replay_gate,
    validate_sel_artifact_chain,
)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _seed_cde_bundle(bundle_dir: Path, *, trace_id: str = "trace-sel-run-001") -> None:
    decision = load_example("continuation_decision_record")
    decision["trace_id"] = trace_id
    decision["decision_outcome"] = "continue_repair_bounded"

    decision_bundle = load_example("decision_bundle")
    decision_bundle["trace_id"] = trace_id
    evidence = load_example("decision_evidence_pack")
    evidence["trace_id"] = trace_id

    _write(bundle_dir / "continuation_decision_record.json", decision)
    _write(bundle_dir / "decision_bundle.json", decision_bundle)
    _write(bundle_dir / "decision_evidence_pack.json", evidence)


def test_sel_runner_emits_full_chain_and_replay_gate(tmp_path: Path) -> None:
    input_dir = tmp_path / "cde"
    output_dir = tmp_path / "sel"
    _seed_cde_bundle(input_dir)

    result = run_sel_orchestration(
        cde_bundle_dir=input_dir,
        output_dir=output_dir,
        observed_outcome="improved",
        observed_outcome_ref="outcome:sel-001",
    )

    assert result["status"] == "completed"
    for artifact in (
        "enforcement_action_record",
        "enforcement_eval_result",
        "enforcement_readiness_record",
        "enforcement_result_record",
        "enforcement_bundle",
        "enforcement_effectiveness_record",
    ):
        assert (output_dir / f"{artifact}.json").exists()

    action = json.loads((output_dir / "enforcement_action_record.json").read_text(encoding="utf-8"))
    decision = json.loads((input_dir / "continuation_decision_record.json").read_text(encoding="utf-8"))
    replay = run_sel_replay_gate(output_dir=output_dir, decision_record=decision, action_record=action)
    assert replay["result"] == "pass"


def test_sel_runner_fails_closed_on_missing_inputs(tmp_path: Path) -> None:
    input_dir = tmp_path / "missing"
    output_dir = tmp_path / "sel"
    input_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(SELOrchestrationRunnerError, match="missing required CDE input"):
        run_sel_orchestration(cde_bundle_dir=input_dir, output_dir=output_dir)


def test_sel_chain_validation_blocks_on_broken_lineage(tmp_path: Path) -> None:
    input_dir = tmp_path / "cde"
    output_dir = tmp_path / "sel"
    _seed_cde_bundle(input_dir)
    run_sel_orchestration(cde_bundle_dir=input_dir, output_dir=output_dir)

    result_record = json.loads((output_dir / "enforcement_result_record.json").read_text(encoding="utf-8"))
    result_record["enforcement_action_record_ref"] = "enforcement_action_record:tampered"
    _write(output_dir / "enforcement_result_record.json", result_record)

    chain = validate_sel_artifact_chain(output_dir=output_dir, trace_id="trace-sel-run-001")
    assert chain["status"] == "failed"
    assert "lineage_broken:result_action_ref" in (chain["failure_summary"] or "")
