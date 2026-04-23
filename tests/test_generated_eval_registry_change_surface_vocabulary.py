from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_AG07_FILES = (
    _REPO_ROOT / "contracts" / "schemas" / "generated_eval_registry_change_request_record.schema.json",
    _REPO_ROOT / "contracts" / "schemas" / "generated_eval_registry_change_review_record.schema.json",
    _REPO_ROOT / "contracts" / "schemas" / "generated_eval_registry_change_execution_record.schema.json",
    _REPO_ROOT / "contracts" / "schemas" / "generated_eval_registry_change_reversal_record.schema.json",
    _REPO_ROOT / "contracts" / "examples" / "generated_eval_registry_change_request_record.json",
    _REPO_ROOT / "contracts" / "examples" / "generated_eval_registry_change_review_record.json",
    _REPO_ROOT / "contracts" / "examples" / "generated_eval_registry_change_execution_record.json",
    _REPO_ROOT / "contracts" / "examples" / "generated_eval_registry_change_reversal_record.json",
    _REPO_ROOT / "docs" / "runtime" / "ag-07-generated-eval-registry-change.md",
)

_FORBIDDEN_TOKENS = (
    "approved",
    "rejected",
    "promote",
    "promoted",
    "accepted",
    "declined",
    "governance",
    "authority",
    "authorized",
    "rollback",
)


def test_ag07_surface_rejects_forbidden_vocabulary_tokens() -> None:
    for path in _AG07_FILES:
        payload = path.read_text(encoding="utf-8").lower()
        for forbidden in _FORBIDDEN_TOKENS:
            assert forbidden not in payload, f"forbidden AG-07 vocabulary '{forbidden}' found in {path}"


def test_ag07_runtime_literals_reject_forbidden_vocabulary_tokens() -> None:
    runtime_path = _REPO_ROOT / "spectrum_systems" / "modules" / "runtime" / "failure_eval_generation.py"
    lines = runtime_path.read_text(encoding="utf-8").splitlines()
    ag07_lines = [
        line.lower()
        for line in lines
        if "generated_eval_registry_change" in line
        or "replay_validation_" in line
        or "manual_registry_revert" in line
        or "registry_change_" in line
    ]
    payload = "\n".join(ag07_lines)
    for forbidden in _FORBIDDEN_TOKENS:
        assert forbidden not in payload, f"forbidden AG-07 vocabulary '{forbidden}' found in AG-07 runtime literals"
