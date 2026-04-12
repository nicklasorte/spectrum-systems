"""Execution contract enforcement for governed active execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExecutionContractResult:
    status: str
    violations: list[str]
    checks: dict[str, bool]


def evaluate_execution_contracts(
    *,
    changed_files: list[str],
    commit_sha: str | None,
    pr_number: str | None,
    tests_passed: bool,
) -> ExecutionContractResult:
    checks = {
        "file_changes_required": bool(changed_files),
        "commit_required": bool((commit_sha or "").strip()),
        "pr_required": bool((pr_number or "").strip()),
        "tests_required": bool(tests_passed),
    }
    violations = [name for name, ok in checks.items() if not ok]
    return ExecutionContractResult(
        status="blocked" if violations else "passed",
        violations=violations,
        checks=checks,
    )


def to_artifact(result: ExecutionContractResult) -> dict[str, Any]:
    return {
        "artifact_type": "execution_contract_enforcement_result",
        "status": result.status,
        "violations": list(result.violations),
        "checks": dict(result.checks),
    }


__all__ = ["ExecutionContractResult", "evaluate_execution_contracts", "to_artifact"]
