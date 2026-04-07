from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.pre_pr_governance_closure import (
    PrePRGovernanceClosureError,
    run_local_pre_pr_governance_closure,
)


class _Result:
    def __init__(self, returncode: int = 0):
        self.returncode = returncode
        self.stdout = ""
        self.stderr = ""


def test_block_after_repair_remains_blocked(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "outputs" / "pre_pr_governance").mkdir(parents=True)
    report_path = tmp_path / "outputs" / "pre_pr_governance" / "contract_preflight_report.json"
    artifact_path = tmp_path / "outputs" / "pre_pr_governance" / "contract_preflight_result_artifact.json"
    report_path.write_text(json.dumps({"missing_required_surface": []}), encoding="utf-8")
    artifact_path.write_text(json.dumps({"control_signal": {"strategy_gate_decision": "BLOCK"}}), encoding="utf-8")

    def runner(command: list[str], cwd: Path):
        return _Result(2 if "run_contract_preflight.py" in " ".join(command) else 0)

    with pytest.raises(PrePRGovernanceClosureError, match="strategy gate BLOCK"):
        run_local_pre_pr_governance_closure(
            repo_root=tmp_path,
            changed_paths=["README.md"],
            targeted_tests=[],
            command_runner=runner,
        )


def test_missing_manifest_registration_auto_repair(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "outputs" / "pre_pr_governance").mkdir(parents=True)
    (tmp_path / "contracts" / "schemas").mkdir(parents=True)
    manifest = {
        "artifact_type": "standards_manifest",
        "artifact_id": "id",
        "artifact_version": "1",
        "schema_version": "1.0.0",
        "standards_version": "1.0.0",
        "record_id": "r",
        "run_id": "run",
        "created_at": "2026-04-07T00:00:00Z",
        "created_by": "test",
        "source_repo": "x",
        "source_repo_version": "y",
        "input_artifacts": [],
        "contracts": [],
    }
    (tmp_path / "contracts" / "standards-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "contracts" / "schemas" / "new_artifact.schema.json").write_text("{}", encoding="utf-8")

    report_path = tmp_path / "outputs" / "pre_pr_governance" / "contract_preflight_report.json"
    artifact_path = tmp_path / "outputs" / "pre_pr_governance" / "contract_preflight_result_artifact.json"
    report_path.write_text(json.dumps({"missing_required_surface": [{"path": "contracts/schemas/new_artifact.schema.json"}]}), encoding="utf-8")

    calls = {"preflight": 0}

    def runner(command: list[str], cwd: Path):
        cmd = " ".join(command)
        if "run_contract_preflight.py" in cmd:
            calls["preflight"] += 1
            decision = "BLOCK" if calls["preflight"] == 1 else "ALLOW"
            artifact_path.write_text(json.dumps({"control_signal": {"strategy_gate_decision": decision}}), encoding="utf-8")
            return _Result(2 if decision == "BLOCK" else 0)
        return _Result(0)

    result = run_local_pre_pr_governance_closure(
        repo_root=tmp_path,
        changed_paths=["contracts/schemas/new_artifact.schema.json"],
        targeted_tests=[],
        command_runner=runner,
    )
    assert result.gate_decision == "ALLOW"
    assert "missing_manifest_registration" in result.attempted_auto_repairs
