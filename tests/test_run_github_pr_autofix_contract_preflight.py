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
