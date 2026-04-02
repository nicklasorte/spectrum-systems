from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime import codex_to_pqx_task_wrapper as wrapper_module

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPO_ROOT / "scripts" / "run_codex_to_pqx_wrapper.py"


def _governed_input() -> dict[str, object]:
    return {
        "task_id": "con-038-task",
        "step_id": "AI-01",
        "step_name": "Implement wrapper",
        "prompt": "Implement CON-038 task wrapper",
        "execution_context": "pqx_governed",
        "requested_at": "2026-04-02T00:00:00Z",
        "dependencies": ["AI-00"],
        "changed_paths": [
            "contracts/schemas/pqx_execution_request.schema.json",
            "spectrum_systems/modules/runtime/pqx_slice_runner.py",
        ],
        "authority_context": {
            "authority_evidence_ref": "data/pqx_runs/AI-01/example.pqx_slice_execution_record.json",
            "contract_preflight_result_artifact_path": "outputs/contract_preflight/contract_preflight_result_artifact.json",
            "notes": "governed test input",
        },
        "roadmap_version": "docs/roadmaps/system_roadmap.md",
        "row_index": 0,
        "row_status": "ready",
    }


def test_valid_governed_codex_task_builds_valid_wrapper() -> None:
    built = wrapper_module.build_codex_pqx_task_wrapper(_governed_input())
    assert built.wrapper["governance"]["pqx_required"] is True
    assert built.wrapper["execution_intent"]["mode"] == "governed"
    validate_artifact(built.wrapper, "codex_pqx_task_wrapper")
    validate_artifact(built.wrapper["pqx_execution_request"], "pqx_execution_request")


def test_valid_exploration_task_builds_non_authoritative_wrapper() -> None:
    payload = _governed_input()
    payload["execution_context"] = "exploration"
    payload["changed_paths"] = ["docs/vision.md"]
    payload["authority_context"] = {}
    built = wrapper_module.build_codex_pqx_task_wrapper(payload)
    assert built.wrapper["governance"]["pqx_required"] is False
    assert built.wrapper["governance"]["authority_state"] == "non_authoritative_direct_run"
    assert built.wrapper["execution_intent"]["mode"] == "exploration_only"


def test_missing_required_governed_authority_input_fails_closed() -> None:
    payload = _governed_input()
    payload["authority_context"] = {}
    with pytest.raises(wrapper_module.CodexToPQXWrapperError, match="authority_context.authority_evidence_ref"):
        wrapper_module.build_codex_pqx_task_wrapper(payload)


def test_malformed_task_input_fails_closed() -> None:
    payload = _governed_input()
    payload["changed_paths"] = ["../outside.txt"]
    with pytest.raises(wrapper_module.CodexToPQXWrapperError, match="must not traverse parent directories"):
        wrapper_module.build_codex_pqx_task_wrapper(payload)


def test_wrapper_output_is_deterministic_for_identical_inputs() -> None:
    payload = _governed_input()
    wrapper_a = wrapper_module.build_codex_pqx_task_wrapper(payload).wrapper
    wrapper_b = wrapper_module.build_codex_pqx_task_wrapper(payload).wrapper
    assert wrapper_a == wrapper_b


def test_wrapper_to_pqx_compatibility_uses_expected_ingestion_seam(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def _fake_run_pqx_slice(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "complete", "run_id": "wrapper-run", "result": str(tmp_path / "result.json")}

    monkeypatch.setattr(wrapper_module, "run_pqx_slice", _fake_run_pqx_slice)

    wrapper = wrapper_module.build_codex_pqx_task_wrapper(_governed_input()).wrapper
    result = wrapper_module.run_wrapped_pqx_task(
        wrapper=wrapper,
        roadmap_path=tmp_path / "roadmap.md",
        state_path=tmp_path / "state.json",
        runs_root=tmp_path / "runs",
        pqx_output_text="pqx output",
    )

    assert result["status"] == "complete"
    assert captured["step_id"] == "AI-01"
    assert captured["changed_paths"] == wrapper["changed_paths"]


def test_cli_invalid_input_fails_closed(tmp_path: Path) -> None:
    process = subprocess.run(
        [
            sys.executable,
            str(CLI_PATH),
            "--task-id",
            "cli-governed-no-auth",
            "--step-id",
            "AI-01",
            "--step-name",
            "CLI invalid",
            "--prompt",
            "governed run",
            "--execution-context",
            "pqx_governed",
            "--changed-path",
            "contracts/schemas/pqx_execution_request.schema.json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 2
    payload = json.loads(process.stdout)
    assert payload["status"] == "blocked"


def test_cli_golden_path_writes_wrapper(tmp_path: Path) -> None:
    output_path = tmp_path / "wrapper.json"
    process = subprocess.run(
        [
            sys.executable,
            str(CLI_PATH),
            "--task-id",
            "cli-golden",
            "--step-id",
            "AI-01",
            "--step-name",
            "CLI golden",
            "--prompt",
            "exploration wrapper",
            "--execution-context",
            "exploration",
            "--requested-at",
            "2026-04-02T00:00:00Z",
            "--changed-path",
            "docs/vision.md",
            "--output-path",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0
    payload = json.loads(process.stdout)
    assert payload["status"] == "ok"
    wrapper = json.loads(output_path.read_text(encoding="utf-8"))
    validate_artifact(wrapper, "codex_pqx_task_wrapper")
