from __future__ import annotations

import json
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]

_SCHEMA_FILES = [
    _REPO_ROOT / "contracts/schemas/generated_eval_registry_change_review_record.schema.json",
]
_EXAMPLE_FILES = [
    _REPO_ROOT / "contracts/examples/generated_eval_registry_change_request_record.json",
    _REPO_ROOT / "contracts/examples/generated_eval_registry_change_review_record.json",
    _REPO_ROOT / "contracts/examples/generated_eval_registry_change_execution_record.json",
    _REPO_ROOT / "contracts/examples/generated_eval_registry_change_reversal_record.json",
    _REPO_ROOT / "contracts/examples/tpa_contract_sync_check_record.json",
    _REPO_ROOT / "contracts/examples/tpa_contract_sync_repair_plan_record.json",
    _REPO_ROOT / "contracts/examples/tpa_contract_sync_repair_handoff_record.json",
]
_RUNTIME_FILES = [
    _REPO_ROOT / "spectrum_systems/modules/runtime/failure_eval_generation.py",
]
_DOC_FILES = [
    _REPO_ROOT / "docs/runtime/ag-07-controlled-generated-eval-promotion.md",
    _REPO_ROOT / "docs/runtime/tpa-contract-sync-autorepair.md",
]
_TEST_FILES = [
    _REPO_ROOT / "tests/test_failure_eval_generation.py",
    _REPO_ROOT / "tests/test_tpa_contract_sync_preflight.py",
]

_FORBIDDEN_TOKENS = {
    "accepted",
    "declined",
    "manual_governance_reversal",
    "manual governance reversal",
    "runtime-governance-reviewer",
    "runtime governance reviewer",
    "authorized repair owners",
    "controlled generated-eval promotion",
}


def _string_values(payload: object) -> list[str]:
    values: list[str] = []
    if isinstance(payload, str):
        values.append(payload)
    elif isinstance(payload, dict):
        for value in payload.values():
            values.extend(_string_values(value))
    elif isinstance(payload, list):
        for value in payload:
            values.extend(_string_values(value))
    return values


def _find_forbidden(value: str) -> str | None:
    normalized = value.casefold()
    for token in sorted(_FORBIDDEN_TOKENS):
        if token.casefold() in normalized:
            return token
    return None


def _schema_violations(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    artifact_type = str(payload.get("title") or "")
    violations: list[dict[str, str]] = []
    for value in _string_values(payload):
        offending = _find_forbidden(value)
        if offending:
            violations.append(
                {
                    "offending_token": offending,
                    "offending_file": str(path.relative_to(_REPO_ROOT)),
                    "surface_kind": "schema_enum",
                    "artifact_type": artifact_type,
                }
            )
    return violations


def _json_violations(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    artifact_type = str(payload.get("artifact_type") or "")
    violations: list[dict[str, str]] = []
    for value in _string_values(payload):
        offending = _find_forbidden(value)
        if offending:
            violations.append(
                {
                    "offending_token": offending,
                    "offending_file": str(path.relative_to(_REPO_ROOT)),
                    "surface_kind": "example_string",
                    "artifact_type": artifact_type,
                }
            )
    return violations


def _text_violations(path: Path, *, surface_kind: str) -> list[dict[str, str]]:
    contents = path.read_text(encoding="utf-8")
    artifact_type = path.stem
    violations: list[dict[str, str]] = []
    offending = _find_forbidden(contents)
    if offending:
        violations.append(
            {
                "offending_token": offending,
                "offending_file": str(path.relative_to(_REPO_ROOT)),
                "surface_kind": surface_kind,
                "artifact_type": artifact_type,
            }
        )
    return violations


def test_ag07_tpa_surfaces_avoid_forbidden_authority_vocabulary() -> None:
    violations: list[dict[str, str]] = []
    for path in _SCHEMA_FILES:
        violations.extend(_schema_violations(path))
    for path in _EXAMPLE_FILES:
        violations.extend(_json_violations(path))
    for path in _RUNTIME_FILES:
        violations.extend(_text_violations(path, surface_kind="runtime_literal"))
    for path in _DOC_FILES:
        violations.extend(_text_violations(path, surface_kind="docs_text"))
    for path in _TEST_FILES:
        violations.extend(_text_violations(path, surface_kind="test_literal"))

    assert violations == []


def test_forbidden_values_emit_token_level_diagnostics() -> None:
    sample = "review_outcome: accepted"
    offending = _find_forbidden(sample)
    diagnostic = {
        "offending_token": offending or "",
        "offending_file": "contracts/examples/generated_eval_registry_change_review_record.json",
        "surface_kind": "example_string",
        "artifact_type": "generated_eval_registry_change_review_record",
    }
    assert offending == "accepted"
    assert diagnostic["offending_file"].endswith(".json")
