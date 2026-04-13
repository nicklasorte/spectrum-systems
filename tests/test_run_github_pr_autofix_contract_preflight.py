from __future__ import annotations

from scripts import run_github_pr_autofix_contract_preflight as entry


def test_cli_returns_blocked_on_autofix_error(monkeypatch) -> None:
    monkeypatch.setattr(
        entry,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "output_dir": "outputs/contract_preflight",
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
