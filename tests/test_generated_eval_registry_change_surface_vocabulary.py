from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_AG07_FILES = [
    _REPO_ROOT / "spectrum_systems/modules/runtime/failure_eval_generation.py",
    _REPO_ROOT / "docs/runtime/ag-07-controlled-generated-eval-promotion.md",
    _REPO_ROOT / "contracts/schemas/generated_eval_registry_change_request_record.schema.json",
    _REPO_ROOT / "contracts/schemas/generated_eval_registry_change_review_record.schema.json",
    _REPO_ROOT / "contracts/schemas/generated_eval_registry_change_execution_record.schema.json",
    _REPO_ROOT / "contracts/schemas/generated_eval_registry_change_reversal_record.schema.json",
    _REPO_ROOT / "contracts/examples/generated_eval_registry_change_request_record.json",
    _REPO_ROOT / "contracts/examples/generated_eval_registry_change_review_record.json",
    _REPO_ROOT / "contracts/examples/generated_eval_registry_change_execution_record.json",
    _REPO_ROOT / "contracts/examples/generated_eval_registry_change_reversal_record.json",
    _REPO_ROOT / "tests/test_failure_eval_generation.py",
]

_FORBIDDEN_TOKENS = [
    "promotion_request_record",
    "promotion_decision_record",
    "promotion_result_record",
    "promotion_rollback_record",
    '"decision"',
    '"promoted"',
    '"rolled_back"',
]


def test_ag07_registry_change_surface_avoids_forbidden_promotion_vocabulary() -> None:
    violations: list[str] = []
    for path in _AG07_FILES:
        contents = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN_TOKENS:
            if token in contents:
                violations.append(f"{path.relative_to(_REPO_ROOT)} contains forbidden token: {token}")

    assert violations == []
