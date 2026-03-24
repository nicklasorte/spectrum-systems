from __future__ import annotations

import ast
from pathlib import Path

SCRIPTS = (
    "run_release_canary.py",
    "run_eval_coverage_report.py",
    "run_eval_ci_gate.py",
)


def _imports_script_module(source: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("scripts."):
                return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("scripts."):
                    return True
    return False


def test_targeted_scripts_do_not_import_other_scripts() -> None:
    root = Path(__file__).resolve().parents[1] / "scripts"
    offenders: list[str] = []
    for script_name in SCRIPTS:
        src = (root / script_name).read_text(encoding="utf-8")
        if _imports_script_module(src):
            offenders.append(script_name)

    assert offenders == []
