from spectrum_systems.modules.runtime.execution_contracts import evaluate_execution_contracts


def test_execution_contracts_block_passive_runs() -> None:
    result = evaluate_execution_contracts(
        changed_files=[],
        commit_sha="",
        pr_number="",
        tests_passed=False,
    )
    assert result.status == "blocked"
    assert set(result.violations) == {
        "file_changes_required",
        "commit_required",
        "pr_required",
        "tests_required",
    }


def test_execution_contracts_pass_with_required_evidence() -> None:
    result = evaluate_execution_contracts(
        changed_files=["spectrum_systems/modules/runtime/changed_path_resolution.py"],
        commit_sha="abc123",
        pr_number="91",
        tests_passed=True,
    )
    assert result.status == "passed"
    assert result.violations == []
