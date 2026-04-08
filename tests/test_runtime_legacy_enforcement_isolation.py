from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = REPO_ROOT / "spectrum_systems" / "modules" / "runtime"
ENFORCEMENT_ENGINE_PATH = RUNTIME_ROOT / "enforcement_engine.py"


def _find_legacy_seam_references(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "spectrum_systems.modules.runtime.enforcement_engine":
                for alias in node.names:
                    if alias.name == "enforce_budget_decision":
                        violations.append("import-from")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                if func.attr == "enforce_budget_decision":
                    value = func.value
                    if isinstance(value, ast.Name) and value.id == "enforcement_engine":
                        violations.append("module-attribute-call")

    return violations


def test_runtime_modules_do_not_reference_legacy_enforcement_seam() -> None:
    violating_paths: dict[str, list[str]] = {}

    for py_path in sorted(RUNTIME_ROOT.rglob("*.py")):
        if py_path == ENFORCEMENT_ENGINE_PATH:
            continue
        findings = _find_legacy_seam_references(py_path)
        if findings:
            violating_paths[str(py_path.relative_to(REPO_ROOT))] = findings

    assert violating_paths == {}
