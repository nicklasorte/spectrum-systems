from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.control_surface_manifest import (
    ControlSurfaceManifestError,
    build_control_surface_manifest,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_manifest_build_is_deterministic_and_schema_valid() -> None:
    first = build_control_surface_manifest()
    second = build_control_surface_manifest()

    assert first == second
    assert first["artifact_type"] == "control_surface_manifest"
    assert first["summary"]["total_surfaces"] == len(first["surfaces"])

    from jsonschema import Draft202012Validator

    Draft202012Validator(load_schema("control_surface_manifest")).validate(first)


def test_manifest_fails_closed_when_owning_module_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from spectrum_systems.modules.runtime import control_surface_manifest as module

    original = module._surface_catalog

    def _broken_catalog() -> list[dict]:
        surfaces = original()
        surfaces[0]["owning_module"] = "spectrum_systems.modules.runtime.this_module_does_not_exist"
        return surfaces

    monkeypatch.setattr(module, "_surface_catalog", _broken_catalog)
    with pytest.raises(ControlSurfaceManifestError, match="owning_module file not found"):
        module.build_control_surface_manifest()


def test_cli_build_writes_manifest(tmp_path: Path) -> None:
    cmd = [
        sys.executable,
        "scripts/build_control_surface_manifest.py",
        "--output-dir",
        str(tmp_path),
    ]
    proc = subprocess.run(cmd, cwd=_REPO_ROOT, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr

    output_path = tmp_path / "control_surface_manifest.json"
    assert output_path.is_file()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "control_surface_manifest"
