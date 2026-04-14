from __future__ import annotations

import json
from pathlib import Path

from scripts import run_github_pr_autofix_contract_preflight as entry


def test_cli_returns_blocked_on_autofix_error(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setattr(
        entry,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "output_dir": str(tmp_path / "outputs" / "contract_preflight"),
                "base_ref": "base",
                "head_ref": "head",
                "event_name": "pull_request",
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": "outputs/contract_preflight/preflight_pqx_task_wrapper.json",
                "authority_evidence_ref": "artifact",
                "same_repo_write_allowed": True,
            },
        )(),
    )

    class _Err(entry.ContractPreflightAutofixError):
        pass

    def _raise(**_kwargs):
        raise entry.ContractPreflightAutofixError("boom")

    monkeypatch.setattr(entry, "run_preflight_block_autorepair", _raise)
    assert entry.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "blocked"
    assert "artifact_paths" in payload
    assert "recovery_outcome" in payload["artifact_paths"]


def test_cli_returns_passed_after_auto_repair_on_push(monkeypatch, capsys, tmp_path: Path) -> None:
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        entry,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "output_dir": str(tmp_path / "outputs" / "contract_preflight"),
                "base_ref": "deadbeef",
                "head_ref": "beadfeed",
                "event_name": "push",
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": "outputs/contract_preflight/preflight_pqx_task_wrapper.json",
                "authority_evidence_ref": "artifact",
                "same_repo_write_allowed": True,
            },
        )(),
    )

    def _runner(**kwargs):
        captured["base_ref"] = kwargs["base_ref"]
        captured["head_ref"] = kwargs["head_ref"]
        return {"recovery_outcome": {"final_decision": "passed_after_auto_repair"}}

    monkeypatch.setattr(entry, "run_preflight_block_autorepair", _runner)
    assert entry.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "passed"
    assert payload["result"]["recovery_outcome"]["final_decision"] == "passed_after_auto_repair"
    assert captured["base_ref"] == "deadbeef"
    assert captured["head_ref"] == "beadfeed"


def test_cli_normalizes_pull_request_refs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_BASE_SHA", "cafecafe")
    monkeypatch.setenv("GITHUB_HEAD_SHA", "feedfeed")
    monkeypatch.setattr(
        entry,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "output_dir": str(tmp_path / "outputs" / "contract_preflight"),
                "base_ref": "",
                "head_ref": "",
                "event_name": "pull_request",
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": "outputs/contract_preflight/preflight_pqx_task_wrapper.json",
                "authority_evidence_ref": "artifact",
                "same_repo_write_allowed": True,
            },
        )(),
    )
    captured: dict[str, str] = {}

    def _runner(**kwargs):
        captured["base_ref"] = kwargs["base_ref"]
        captured["head_ref"] = kwargs["head_ref"]
        return {"ok": True}

    monkeypatch.setattr(entry, "run_preflight_block_autorepair", _runner)
    assert entry.main() == 0
    assert captured == {"base_ref": "cafecafe", "head_ref": "feedfeed"}
