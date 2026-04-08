from __future__ import annotations

import ast
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact

REPO_ROOT = Path(__file__).resolve().parents[1]
APPROVED_REPO_WRITE_CALLERS = {
    "spectrum_systems/modules/runtime/top_level_conductor.py",
}


def test_build_admission_record_rejects_unknown_top_level_field() -> None:
    payload = {
        "artifact_type": "build_admission_record",
        "admission_id": "adm-1",
        "request_id": "req-1",
        "execution_type": "repo_write",
        "admission_status": "accepted",
        "normalized_execution_request_ref": "normalized_execution_request:req-1",
        "trace_id": "trace-1",
        "created_at": "2026-04-08T00:00:00Z",
        "produced_by": "AEXEngine",
        "reason_codes": [],
        "target_scope": {"repo": "spectrum-systems", "paths": ["x"]},
        "unexpected": "drift",
    }
    with pytest.raises(Exception):
        validate_artifact(payload, "build_admission_record")


def test_only_approved_callers_use_repo_write_execution_class_for_pqx() -> None:
    violations: list[str] = []
    for path in REPO_ROOT.rglob("*.py"):
        relative = str(path.relative_to(REPO_ROOT))
        if relative.startswith(".venv/") or relative.startswith("outputs/") or relative.startswith("tests/"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "execute_sequence_run":
                continue
            for keyword in node.keywords:
                if keyword.arg != "execution_class":
                    continue
                if isinstance(keyword.value, ast.Constant) and keyword.value.value == "repo_write":
                    if relative not in APPROVED_REPO_WRITE_CALLERS:
                        violations.append(relative)
    assert not violations, f"non-approved repo_write execute_sequence_run callers: {sorted(set(violations))}"
