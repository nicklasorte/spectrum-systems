from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load_cli_module():
    spec = importlib.util.spec_from_file_location("run_pqx_sequence_cli", Path("scripts/run_pqx_sequence.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _roadmap_slice(step_id: str = "CON-048") -> dict[str, object]:
    return {
        "step_id": step_id,
        "step_name": "Thin PQX CLI",
        "prompt": "Implement thin CLI",
        "requested_at": "2026-04-02T00:00:00Z",
        "pqx_output_text": f"output-{step_id}",
        "changed_paths": ["scripts/run_pqx_sequence.py"],
    }


def _wrapper(step_id: str = "CON-048") -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "artifact_type": "codex_pqx_task_wrapper",
        "wrapper_id": f"wrap-{step_id}",
        "task_identity": {"task_id": f"task-{step_id}", "run_id": "run-1", "step_id": step_id, "step_name": step_id},
        "task_source": {"source_type": "codex_prompt", "prompt": "Execute"},
        "execution_intent": {"execution_context": "pqx_governed", "mode": "governed"},
        "governance": {
            "classification": "governed_pqx_required",
            "pqx_required": True,
            "authority_state": "authoritative_governed_pqx",
            "authority_resolution": "authoritative",
            "authority_evidence_ref": "data/pqx_runs/auth.pqx_slice_execution_record.json",
            "contract_preflight_result_artifact_path": None,
        },
        "changed_paths": ["scripts/run_pqx_sequence.py"],
        "metadata": {
            "requested_at": "2026-04-02T00:00:00Z",
            "dependencies": [],
            "policy_version": "1.0.0",
            "authority_notes": None,
        },
        "pqx_execution_request": {
            "schema_version": "1.1.0",
            "run_id": "run-1",
            "step_id": step_id,
            "step_name": step_id,
            "dependencies": [],
            "requested_at": "2026-04-02T00:00:00Z",
            "prompt": "Execute",
            "roadmap_version": "docs/roadmaps/system_roadmap.md",
            "row_snapshot": {"row_index": 0, "step_id": step_id, "step_name": step_id, "dependencies": [], "status": "ready"},
        },
    }


def _trace(status: str) -> dict[str, object]:
    return {
        "artifact_type": "pqx_sequential_execution_trace",
        "schema_version": "1.0.0",
        "trace_id": "pqx-seq-test-001",
        "run_id": "run-1",
        "ordered_slice_ids": ["CON-048"],
        "slices": [
            {
                "slice_id": "CON-048",
                "input_ref": "roadmap:CON-048",
                "wrapper_ref": "codex_pqx_task_wrapper:wrap-CON-048",
                "pqx_execution_artifact_ref": "data/pqx_runs/r1.json",
                "slice_execution_record_ref": "data/pqx_runs/r1.pqx_slice_execution_record.json",
                "eval_result_ref": "evaluation_control_decision:d-1",
                "control_decision_ref": "evaluation_control_decision:d-1",
                "control_decision_summary": {"decision": "allow", "decision_id": "d-1"},
                "enforcement_result": {"final_status": status.lower(), "rationale": status.lower()},
                "final_slice_status": status,
                "status": "completed" if status == "ALLOW" else "stopped",
            }
        ],
        "authority_evidence_refs": ["data/pqx_runs/auth.pqx_slice_execution_record.json"],
        "final_status": status,
        "blocking_reason": None if status == "ALLOW" else f"{status.lower()}-reason",
        "stopping_slice_id": None if status == "ALLOW" else "CON-048",
    }


def test_cli_allow_writes_trace_and_returns_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    module = _load_cli_module()
    roadmap_path = tmp_path / "roadmap.json"
    output_path = tmp_path / "trace.json"
    roadmap_path.write_text(json.dumps({"slices": [_roadmap_slice()]}), encoding="utf-8")

    monkeypatch.setattr(module, "build_codex_pqx_task_wrapper", lambda _: type("R", (), {"wrapper": _wrapper()})())
    monkeypatch.setattr(module, "run_pqx_sequential", lambda **_: _trace("ALLOW"))
    monkeypatch.setattr(module, "validate_artifact", lambda *_: None)
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: module.argparse.Namespace(
            roadmap=roadmap_path,
            output=output_path,
            run_id="run-1",
            execution_context="pqx_governed",
            authority_evidence_ref="data/pqx_runs/auth.pqx_slice_execution_record.json",
            contract_preflight_result_artifact_path=None,
            initial_context=None,
            stage="sequence_execution",
            runtime_environment="cli",
            roadmap_path="docs/roadmaps/system_roadmap.md",
            state_path="data/pqx_state.json",
            runs_root="data/pqx_runs",
        ),
    )

    assert module.main() == 0
    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8"))["final_status"] == "ALLOW"
    stdout = capsys.readouterr().out
    assert '"trace_artifact_path":' in stdout
    assert '"final_run_status": "ALLOW"' in stdout


def test_cli_block_and_require_review_return_non_zero_and_write_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_cli_module()
    roadmap_path = tmp_path / "roadmap.json"
    roadmap_path.write_text(json.dumps({"slices": [_roadmap_slice()]}), encoding="utf-8")
    monkeypatch.setattr(module, "build_codex_pqx_task_wrapper", lambda _: type("R", (), {"wrapper": _wrapper()})())
    monkeypatch.setattr(module, "validate_artifact", lambda *_: None)

    for final_status in ("BLOCK", "REQUIRE_REVIEW"):
        output_path = tmp_path / f"trace-{final_status}.json"
        monkeypatch.setattr(module, "run_pqx_sequential", lambda **_: _trace(final_status))
        monkeypatch.setattr(
            module,
            "parse_args",
            lambda final_status=final_status, output_path=output_path: module.argparse.Namespace(
                roadmap=roadmap_path,
                output=output_path,
                run_id="run-1",
                execution_context="pqx_governed",
                authority_evidence_ref="data/pqx_runs/auth.pqx_slice_execution_record.json",
                contract_preflight_result_artifact_path=None,
                initial_context=None,
                stage="sequence_execution",
                runtime_environment="cli",
                roadmap_path="docs/roadmaps/system_roadmap.md",
                state_path="data/pqx_state.json",
                runs_root="data/pqx_runs",
            ),
        )
        assert module.main() == 2
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["final_status"] == final_status
        assert payload["stopping_slice_id"] == "CON-048"


def test_cli_fail_closed_on_malformed_roadmap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    module = _load_cli_module()
    roadmap_path = tmp_path / "roadmap.json"
    output_path = tmp_path / "trace.json"
    roadmap_path.write_text(json.dumps({"slices": "not-a-list"}), encoding="utf-8")

    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: module.argparse.Namespace(
            roadmap=roadmap_path,
            output=output_path,
            run_id="run-1",
            execution_context="pqx_governed",
            authority_evidence_ref=None,
            contract_preflight_result_artifact_path=None,
            initial_context=None,
            stage="sequence_execution",
            runtime_environment="cli",
            roadmap_path="docs/roadmaps/system_roadmap.md",
            state_path="data/pqx_state.json",
            runs_root="data/pqx_runs",
        ),
    )

    assert module.main() == 2
    assert not output_path.exists()
    assert "non-empty 'slices' list" in capsys.readouterr().err


def test_cli_fail_closed_when_governed_slice_missing_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    module = _load_cli_module()
    roadmap_path = tmp_path / "roadmap.json"
    output_path = tmp_path / "trace.json"
    roadmap_path.write_text(json.dumps({"slices": [_roadmap_slice()]}), encoding="utf-8")

    wrapper = _wrapper()
    wrapper["governance"]["authority_evidence_ref"] = None
    monkeypatch.setattr(module, "build_codex_pqx_task_wrapper", lambda _: type("R", (), {"wrapper": wrapper})())
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: module.argparse.Namespace(
            roadmap=roadmap_path,
            output=output_path,
            run_id="run-1",
            execution_context="pqx_governed",
            authority_evidence_ref=None,
            contract_preflight_result_artifact_path=None,
            initial_context=None,
            stage="sequence_execution",
            runtime_environment="cli",
            roadmap_path="docs/roadmaps/system_roadmap.md",
            state_path="data/pqx_state.json",
            runs_root="data/pqx_runs",
        ),
    )

    assert module.main() == 2
    assert "governed slice missing authority evidence" in capsys.readouterr().err


def test_cli_deterministic_output_behavior_for_identical_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_cli_module()
    roadmap_path = tmp_path / "roadmap.json"
    output_a = tmp_path / "trace-a.json"
    output_b = tmp_path / "trace-b.json"
    roadmap_path.write_text(json.dumps({"slices": [_roadmap_slice()]}), encoding="utf-8")

    trace_payload = _trace("ALLOW")
    monkeypatch.setattr(module, "build_codex_pqx_task_wrapper", lambda _: type("R", (), {"wrapper": _wrapper()})())
    monkeypatch.setattr(module, "run_pqx_sequential", lambda **_: dict(trace_payload))
    monkeypatch.setattr(module, "validate_artifact", lambda *_: None)

    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: module.argparse.Namespace(
            roadmap=roadmap_path,
            output=output_a,
            run_id="run-1",
            execution_context="pqx_governed",
            authority_evidence_ref="data/pqx_runs/auth.pqx_slice_execution_record.json",
            contract_preflight_result_artifact_path=None,
            initial_context=None,
            stage="sequence_execution",
            runtime_environment="cli",
            roadmap_path="docs/roadmaps/system_roadmap.md",
            state_path="data/pqx_state.json",
            runs_root="data/pqx_runs",
        ),
    )
    assert module.main() == 0

    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: module.argparse.Namespace(
            roadmap=roadmap_path,
            output=output_b,
            run_id="run-1",
            execution_context="pqx_governed",
            authority_evidence_ref="data/pqx_runs/auth.pqx_slice_execution_record.json",
            contract_preflight_result_artifact_path=None,
            initial_context=None,
            stage="sequence_execution",
            runtime_environment="cli",
            roadmap_path="docs/roadmaps/system_roadmap.md",
            state_path="data/pqx_state.json",
            runs_root="data/pqx_runs",
        ),
    )
    assert module.main() == 0

    assert json.loads(output_a.read_text(encoding="utf-8")) == json.loads(output_b.read_text(encoding="utf-8"))
