from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_INIT = REPO_ROOT / "spectrum_systems/modules/governance/__init__.py"
SRG_SCRIPT = REPO_ROOT / "scripts/run_system_registry_guard.py"


def _reset_governance_modules() -> None:
    for name in list(sys.modules):
        if name == "spectrum_systems.modules.governance" or name.startswith("spectrum_systems.modules.governance."):
            del sys.modules[name]


def test_governance_package_init_has_no_eager_submodule_imports() -> None:
    text = GOVERNANCE_INIT.read_text(encoding="utf-8")
    assert "from ." not in text
    assert "import spectrum_systems.modules.governance" not in text


def test_importing_system_registry_guard_does_not_side_load_done_certification() -> None:
    _reset_governance_modules()
    importlib.import_module("spectrum_systems.modules.governance.system_registry_guard")
    assert "spectrum_systems.modules.governance.done_certification" not in sys.modules


def test_system_registry_guard_help_does_not_require_jsonschema_side_effect() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONWARNINGS"] = "ignore"

    blocker = (
        "import builtins\n"
        "_orig_import = builtins.__import__\n"
        "def _guard(name, globals=None, locals=None, fromlist=(), level=0):\n"
        "    if name == 'jsonschema' or name.startswith('jsonschema.'):\n"
        "        raise ModuleNotFoundError(\"blocked jsonschema for isolation test\")\n"
        "    return _orig_import(name, globals, locals, fromlist, level)\n"
        "builtins.__import__ = _guard\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", f"{blocker}\nimport runpy\nrunpy.run_path(r'{SRG_SCRIPT}', run_name='__main__')", "--help"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        cwd=REPO_ROOT,
    )

    assert result.returncode == 0, (result.stdout + "\n" + result.stderr).strip()
    assert "Fail-closed system registry ownership guard" in result.stdout


def test_done_certification_module_import_still_available_when_dependencies_exist() -> None:
    module = importlib.import_module("spectrum_systems.modules.governance.done_certification")
    assert hasattr(module, "run_done_certification")
