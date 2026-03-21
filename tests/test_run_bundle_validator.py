from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from spectrum_systems.modules.runtime.run_bundle_validator import validate_and_emit_decision


def _write_manifest(bundle_dir: Path, manifest: dict) -> None:
    (bundle_dir / "run_bundle_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _base_manifest() -> dict:
    return {
        "run_id": "run-001",
        "matlab_release": "R2024b",
        "runtime_version_required": "R2024b",
        "platform": "linux-x86_64",
        "worker_entrypoint": "bin/run.sh",
        "inputs": [
            {"path": "inputs/cases.json", "required": True}
        ],
        "expected_outputs": [
            {"path": "outputs/results_summary.json", "required": True},
            {"path": "outputs/provenance.json", "required": True},
        ],
    }


def _build_bundle(tmp_path: Path, manifest: dict) -> Path:
    bundle = tmp_path / "bundle"
    (bundle / "inputs").mkdir(parents=True)
    (bundle / "outputs").mkdir(parents=True)
    (bundle / "logs").mkdir(parents=True)
    (bundle / "inputs" / "cases.json").write_text("{}", encoding="utf-8")
    _write_manifest(bundle, manifest)
    return bundle


def test_valid_bundle_allow(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path, _base_manifest())
    decision = validate_and_emit_decision(bundle)
    assert decision["status"] == "valid"
    assert decision["system_response"] == "allow"


def test_missing_manifest_field_block(tmp_path: Path) -> None:
    manifest = _base_manifest()
    manifest.pop("platform")
    bundle = _build_bundle(tmp_path, manifest)
    decision = validate_and_emit_decision(bundle)
    assert decision["status"] == "invalid"
    assert decision["system_response"] == "block"
    assert "platform" in decision["invalid_fields"]


def test_missing_input_file_block(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path, _base_manifest())
    (bundle / "inputs" / "cases.json").unlink()
    decision = validate_and_emit_decision(bundle)
    assert decision["status"] == "invalid"
    assert decision["system_response"] == "block"
    assert "inputs/cases.json" in decision["missing_artifacts"]


def test_missing_expected_output_declaration_block(tmp_path: Path) -> None:
    manifest = _base_manifest()
    manifest["expected_outputs"] = [{"path": "outputs/results_summary.json", "required": True}]
    bundle = _build_bundle(tmp_path, manifest)
    decision = validate_and_emit_decision(bundle)
    assert decision["status"] == "invalid"
    assert decision["system_response"] == "block"


def test_missing_output_dir_require_rebuild(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path, _base_manifest())
    (bundle / "outputs").rmdir()
    decision = validate_and_emit_decision(bundle)
    assert decision["status"] == "invalid"
    assert decision["system_response"] == "require_rebuild"


def test_extra_manifest_field_block(tmp_path: Path) -> None:
    manifest = _base_manifest()
    manifest["extra"] = "not-allowed"
    bundle = _build_bundle(tmp_path, manifest)
    decision = validate_and_emit_decision(bundle)
    assert decision["status"] == "invalid"
    assert decision["system_response"] == "block"
    assert "extra" in decision["invalid_fields"]


def test_cli_exit_codes(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_bundle_validation.py"

    valid_bundle = _build_bundle(tmp_path / "valid", _base_manifest())
    valid_proc = subprocess.run([sys.executable, str(script), "--bundle", str(valid_bundle)], check=False)
    assert valid_proc.returncode == 0

    invalid_manifest = _base_manifest()
    invalid_manifest.pop("platform")
    block_bundle = _build_bundle(tmp_path / "block", invalid_manifest)
    block_proc = subprocess.run([sys.executable, str(script), "--bundle", str(block_bundle)], check=False)
    assert block_proc.returncode == 2

    rebuild_bundle = _build_bundle(tmp_path / "rebuild", _base_manifest())
    (rebuild_bundle / "outputs").rmdir()
    rebuild_proc = subprocess.run([sys.executable, str(script), "--bundle", str(rebuild_bundle)], check=False)
    assert rebuild_proc.returncode == 1
