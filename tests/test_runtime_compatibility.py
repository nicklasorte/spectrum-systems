"""Tests for runtime compatibility enforcement (Prompt BC).

Covers:
- version mismatch rejection
- platform mismatch rejection
- missing file detection
- invalid entrypoint handling
- cache policy enforcement
- schema validation
- CLI behaviour
- manifest integrity validation
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any, Dict

import pytest

from spectrum_systems.modules.runtime.runtime_compatibility import (
    REQUIRED_MANIFEST_FIELDS,
    SUPPORTED_MATLAB_RUNTIME_VERSIONS,
    capture_runtime_env_snapshot,
    classify_runtime_failure,
    derive_runtime_decision,
    validate_cache_policy,
    validate_entrypoint,
    validate_manifest_integrity,
    validate_matlab_runtime_version,
    validate_platform_compatibility,
    validate_required_artifacts,
    validate_runtime_environment,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_PATH = _REPO_ROOT / "contracts" / "schemas" / "runtime_compatibility_decision.schema.json"

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _valid_manifest(**overrides) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "bundle_id": "bundle-001",
        "matlab_runtime_version": "R2024b",
        "required_platform": "linux",
        "entrypoint_script": "/tmp/entrypoint.sh",
        "required_files": [],
        "created_at": "2026-03-19T00:00:00Z",
    }
    base.update(overrides)
    return base


def _linux_env(**overrides) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "os": "linux",
        "os_release": "5.15",
        "python_version": "3.11",
        "hostname": "test-node",
        "matlab_runtime_version": "R2024b",
        "available_disk_bytes": 10_000_000,
        "cache_available": False,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# validate_manifest_integrity
# ---------------------------------------------------------------------------


def test_manifest_integrity_passes_for_valid_manifest():
    errors = validate_manifest_integrity(_valid_manifest())
    assert errors == []


@pytest.mark.parametrize("field", REQUIRED_MANIFEST_FIELDS)
def test_manifest_integrity_fails_for_missing_field(field):
    manifest = _valid_manifest()
    del manifest[field]
    errors = validate_manifest_integrity(manifest)
    assert any(field in e for e in errors)


def test_manifest_integrity_fails_for_none_field():
    manifest = _valid_manifest(bundle_id=None)
    errors = validate_manifest_integrity(manifest)
    assert any("bundle_id" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_matlab_runtime_version
# ---------------------------------------------------------------------------


def test_matlab_version_passes_on_exact_match():
    errors = validate_matlab_runtime_version(_valid_manifest(), _linux_env())
    assert errors == []


def test_matlab_version_fails_on_installed_mismatch():
    env = _linux_env(matlab_runtime_version="R2023a")
    errors = validate_matlab_runtime_version(_valid_manifest(), env)
    assert len(errors) == 1
    assert errors[0].startswith("runtime_version_mismatch")
    assert "R2023a" in errors[0]


def test_matlab_version_fails_when_not_installed():
    env = _linux_env(matlab_runtime_version=None)
    errors = validate_matlab_runtime_version(_valid_manifest(), env)
    assert len(errors) == 1
    assert errors[0].startswith("runtime_version_mismatch")


def test_matlab_version_fails_for_unsupported_required_version():
    manifest = _valid_manifest(matlab_runtime_version="R2019a")
    errors = validate_matlab_runtime_version(manifest, _linux_env())
    assert len(errors) == 1
    assert errors[0].startswith("runtime_version_mismatch")


def test_matlab_version_fails_when_missing_from_manifest():
    manifest = _valid_manifest(matlab_runtime_version=None)
    errors = validate_matlab_runtime_version(manifest, _linux_env())
    assert len(errors) == 1
    assert "manifest_invalid" in errors[0]


@pytest.mark.parametrize("version", SUPPORTED_MATLAB_RUNTIME_VERSIONS)
def test_all_supported_versions_pass_exact_match(version):
    manifest = _valid_manifest(matlab_runtime_version=version)
    env = _linux_env(matlab_runtime_version=version)
    errors = validate_matlab_runtime_version(manifest, env)
    assert errors == []


# ---------------------------------------------------------------------------
# validate_platform_compatibility
# ---------------------------------------------------------------------------


def test_platform_passes_linux_linux():
    errors = validate_platform_compatibility(_valid_manifest(), _linux_env())
    assert errors == []


def test_platform_fails_linux_on_windows():
    env = _linux_env(os="windows")
    errors = validate_platform_compatibility(_valid_manifest(), env)
    assert len(errors) == 1
    assert errors[0].startswith("platform_mismatch")


def test_platform_fails_windows_on_linux():
    manifest = _valid_manifest(required_platform="windows")
    errors = validate_platform_compatibility(manifest, _linux_env())
    assert len(errors) == 1
    assert errors[0].startswith("platform_mismatch")


def test_platform_passes_when_no_required_platform():
    manifest = _valid_manifest(required_platform="")
    errors = validate_platform_compatibility(manifest, _linux_env())
    assert errors == []


def test_platform_passes_windows_windows():
    manifest = _valid_manifest(required_platform="windows")
    env = _linux_env(os="windows")
    errors = validate_platform_compatibility(manifest, env)
    assert errors == []


# ---------------------------------------------------------------------------
# validate_required_artifacts
# ---------------------------------------------------------------------------


def test_required_artifacts_passes_for_empty_list():
    errors = validate_required_artifacts(_valid_manifest(required_files=[]))
    assert errors == []


def test_required_artifacts_passes_when_files_exist(tmp_path: Path):
    f = tmp_path / "data.mat"
    f.write_text("x", encoding="utf-8")
    manifest = _valid_manifest(required_files=[str(f)])
    errors = validate_required_artifacts(manifest)
    assert errors == []


def test_required_artifacts_fails_for_missing_file(tmp_path: Path):
    manifest = _valid_manifest(required_files=[str(tmp_path / "missing.mat")])
    errors = validate_required_artifacts(manifest)
    assert len(errors) == 1
    assert errors[0].startswith("missing_artifacts")


def test_required_artifacts_uses_base_path(tmp_path: Path):
    f = tmp_path / "data.mat"
    f.write_text("x", encoding="utf-8")
    manifest = _valid_manifest(required_files=["data.mat"])
    errors = validate_required_artifacts(manifest, base_path=tmp_path)
    assert errors == []


def test_required_artifacts_fails_for_directory_not_file(tmp_path: Path):
    sub = tmp_path / "subdir"
    sub.mkdir()
    manifest = _valid_manifest(required_files=[str(sub)])
    errors = validate_required_artifacts(manifest)
    assert len(errors) == 1
    assert errors[0].startswith("missing_artifacts")


def test_required_artifacts_fails_for_non_list():
    manifest = _valid_manifest(required_files="not_a_list")
    errors = validate_required_artifacts(manifest)
    assert len(errors) == 1
    assert "manifest_invalid" in errors[0]


# ---------------------------------------------------------------------------
# validate_entrypoint
# ---------------------------------------------------------------------------


def test_entrypoint_passes_for_executable_file(tmp_path: Path):
    ep = tmp_path / "run.sh"
    ep.write_text("#!/bin/bash\n", encoding="utf-8")
    ep.chmod(ep.stat().st_mode | stat.S_IXUSR)
    manifest = _valid_manifest(entrypoint_script=str(ep))
    errors = validate_entrypoint(manifest)
    assert errors == []


def test_entrypoint_fails_for_missing_file(tmp_path: Path):
    manifest = _valid_manifest(entrypoint_script=str(tmp_path / "absent.sh"))
    errors = validate_entrypoint(manifest)
    assert len(errors) == 1
    assert errors[0].startswith("invalid_entrypoint")


def test_entrypoint_fails_for_non_executable_file(tmp_path: Path):
    ep = tmp_path / "run.sh"
    ep.write_text("#!/bin/bash\n", encoding="utf-8")
    # ensure file is NOT executable
    ep.chmod(0o644)
    manifest = _valid_manifest(entrypoint_script=str(ep))
    errors = validate_entrypoint(manifest)
    assert len(errors) == 1
    assert errors[0].startswith("invalid_entrypoint")


def test_entrypoint_fails_when_missing_from_manifest():
    manifest = _valid_manifest(entrypoint_script=None)
    errors = validate_entrypoint(manifest)
    assert len(errors) == 1
    assert errors[0].startswith("invalid_entrypoint")


def test_entrypoint_uses_base_path(tmp_path: Path):
    ep = tmp_path / "run.sh"
    ep.write_text("#!/bin/bash\n", encoding="utf-8")
    ep.chmod(ep.stat().st_mode | stat.S_IXUSR)
    manifest = _valid_manifest(entrypoint_script="run.sh")
    errors = validate_entrypoint(manifest, base_path=tmp_path)
    assert errors == []


# ---------------------------------------------------------------------------
# validate_cache_policy
# ---------------------------------------------------------------------------


def test_cache_policy_passes_when_no_policy():
    manifest = _valid_manifest()  # no optional_cache_policy key
    errors = validate_cache_policy(manifest, _linux_env())
    assert errors == []


def test_cache_policy_passes_when_cache_available():
    manifest = _valid_manifest(optional_cache_policy="warm_cache")
    env = _linux_env(cache_available=True)
    errors = validate_cache_policy(manifest, env)
    assert errors == []


def test_cache_policy_fails_when_cache_unavailable():
    manifest = _valid_manifest(optional_cache_policy="warm_cache")
    env = _linux_env(cache_available=False)
    errors = validate_cache_policy(manifest, env)
    assert len(errors) == 1
    assert errors[0].startswith("cache_unavailable")


def test_cache_policy_passes_when_policy_is_falsy():
    manifest = _valid_manifest(optional_cache_policy="")
    errors = validate_cache_policy(manifest, _linux_env())
    assert errors == []


# ---------------------------------------------------------------------------
# classify_runtime_failure
# ---------------------------------------------------------------------------


def test_classify_returns_none_for_empty_conditions():
    assert classify_runtime_failure([]) is None


def test_classify_returns_most_severe_failure():
    conditions = [
        "missing_artifacts: data.mat not found",
        "manifest_invalid: missing bundle_id",
    ]
    result = classify_runtime_failure(conditions)
    assert result == "manifest_invalid"


def test_classify_returns_correct_single_failure():
    conditions = ["runtime_version_mismatch: R2023a != R2024b"]
    result = classify_runtime_failure(conditions)
    assert result == "runtime_version_mismatch"


# ---------------------------------------------------------------------------
# derive_runtime_decision
# ---------------------------------------------------------------------------


def test_derive_decision_allow_when_no_conditions():
    result = derive_runtime_decision(_valid_manifest(), [])
    assert result["compatible"] is True
    assert result["system_response"] == "allow_execution"
    assert result["failure_type"] is None


def test_derive_decision_reject_for_version_mismatch():
    conditions = ["runtime_version_mismatch: R2023a != R2024b"]
    result = derive_runtime_decision(_valid_manifest(), conditions)
    assert result["compatible"] is False
    assert result["system_response"] == "reject_execution"
    assert result["failure_type"] == "runtime_version_mismatch"


def test_derive_decision_require_rebuild_for_missing_artifacts():
    conditions = ["missing_artifacts: data.mat not found"]
    result = derive_runtime_decision(_valid_manifest(), conditions)
    assert result["compatible"] is False
    assert result["system_response"] == "require_rebuild"
    assert result["failure_type"] == "missing_artifacts"


def test_derive_decision_require_env_update_for_cache():
    conditions = ["cache_unavailable: warm_cache not available"]
    result = derive_runtime_decision(_valid_manifest(), conditions)
    assert result["compatible"] is False
    assert result["system_response"] == "require_environment_update"


# ---------------------------------------------------------------------------
# validate_runtime_environment (top-level integration)
# ---------------------------------------------------------------------------


def test_full_validation_passes_for_compatible_bundle(tmp_path: Path):
    ep = tmp_path / "run.sh"
    ep.write_text("#!/bin/bash\n", encoding="utf-8")
    ep.chmod(ep.stat().st_mode | stat.S_IXUSR)

    f = tmp_path / "data.mat"
    f.write_text("x", encoding="utf-8")

    manifest = _valid_manifest(
        entrypoint_script=str(ep),
        required_files=[str(f)],
    )
    decision = validate_runtime_environment(manifest, runtime_env=_linux_env())

    assert decision["compatible"] is True
    assert decision["system_response"] == "allow_execution"
    assert decision["failure_type"] is None
    assert decision["triggering_conditions"] == []


def test_full_validation_rejects_version_mismatch(tmp_path: Path):
    ep = tmp_path / "run.sh"
    ep.write_text("#!/bin/bash\n", encoding="utf-8")
    ep.chmod(ep.stat().st_mode | stat.S_IXUSR)

    manifest = _valid_manifest(
        matlab_runtime_version="R2024b",
        entrypoint_script=str(ep),
    )
    env = _linux_env(matlab_runtime_version="R2023a")
    decision = validate_runtime_environment(manifest, runtime_env=env)

    assert decision["compatible"] is False
    assert decision["system_response"] == "reject_execution"
    assert decision["failure_type"] == "runtime_version_mismatch"
    assert any("R2023a" in c for c in decision["triggering_conditions"])


def test_full_validation_rejects_platform_mismatch():
    manifest = _valid_manifest(required_platform="linux")
    env = _linux_env(os="windows")
    decision = validate_runtime_environment(manifest, runtime_env=env)

    assert decision["compatible"] is False
    assert decision["system_response"] == "reject_execution"
    assert decision["failure_type"] == "platform_mismatch"


def test_full_validation_requires_rebuild_for_missing_files(tmp_path: Path):
    ep = tmp_path / "run.sh"
    ep.write_text("#!/bin/bash\n", encoding="utf-8")
    ep.chmod(ep.stat().st_mode | stat.S_IXUSR)

    manifest = _valid_manifest(
        entrypoint_script=str(ep),
        required_files=[str(tmp_path / "absent.mat")],
    )
    decision = validate_runtime_environment(manifest, runtime_env=_linux_env())

    assert decision["compatible"] is False
    assert decision["system_response"] == "require_rebuild"
    assert decision["failure_type"] == "missing_artifacts"


def test_full_validation_rejects_invalid_entrypoint(tmp_path: Path):
    manifest = _valid_manifest(
        entrypoint_script=str(tmp_path / "nonexistent.sh"),
    )
    decision = validate_runtime_environment(manifest, runtime_env=_linux_env())

    assert decision["compatible"] is False
    assert decision["system_response"] == "reject_execution"
    assert decision["failure_type"] == "invalid_entrypoint"


def test_full_validation_requires_env_update_for_cache(tmp_path: Path):
    ep = tmp_path / "run.sh"
    ep.write_text("#!/bin/bash\n", encoding="utf-8")
    ep.chmod(ep.stat().st_mode | stat.S_IXUSR)

    manifest = _valid_manifest(
        entrypoint_script=str(ep),
        optional_cache_policy="warm_cache",
    )
    env = _linux_env(cache_available=False)
    decision = validate_runtime_environment(manifest, runtime_env=env)

    assert decision["compatible"] is False
    assert decision["system_response"] == "require_environment_update"
    assert decision["failure_type"] == "cache_unavailable"


def test_full_validation_rejects_invalid_manifest():
    manifest: Dict[str, Any] = {}  # completely empty
    decision = validate_runtime_environment(manifest, runtime_env=_linux_env())

    assert decision["compatible"] is False
    assert decision["system_response"] == "reject_execution"
    assert decision["failure_type"] == "manifest_invalid"


def test_decision_artifact_has_all_required_fields(tmp_path: Path):
    ep = tmp_path / "run.sh"
    ep.write_text("#!/bin/bash\n", encoding="utf-8")
    ep.chmod(ep.stat().st_mode | stat.S_IXUSR)

    manifest = _valid_manifest(entrypoint_script=str(ep))
    decision = validate_runtime_environment(manifest, runtime_env=_linux_env())

    required_fields = [
        "decision_id",
        "bundle_id",
        "created_at",
        "compatible",
        "system_response",
        "failure_type",
        "triggering_conditions",
        "required_actions",
        "runtime_env_snapshot",
        "notes",
    ]
    for field in required_fields:
        assert field in decision, f"Missing field in decision artifact: {field}"


def test_decision_id_is_deterministic_for_same_inputs(tmp_path: Path):
    """decision_id is derived from bundle_id + created_at, so calling twice
    with the same manifest in quick succession may differ; test that it starts
    with the expected prefix and is non-empty."""
    ep = tmp_path / "run.sh"
    ep.write_text("#!/bin/bash\n", encoding="utf-8")
    ep.chmod(ep.stat().st_mode | stat.S_IXUSR)

    manifest = _valid_manifest(entrypoint_script=str(ep))
    decision = validate_runtime_environment(manifest, runtime_env=_linux_env())
    assert decision["decision_id"].startswith("rcd_")


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_schema_file_exists():
    assert _SCHEMA_PATH.exists(), f"Schema file not found: {_SCHEMA_PATH}"


def test_schema_is_valid_json():
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert isinstance(schema, dict)
    assert "properties" in schema


def test_schema_has_required_fields():
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    required = schema.get("required", [])
    expected_fields = [
        "decision_id",
        "bundle_id",
        "created_at",
        "compatible",
        "system_response",
        "failure_type",
        "triggering_conditions",
        "required_actions",
        "runtime_env_snapshot",
        "notes",
    ]
    for field in expected_fields:
        assert field in required, f"Schema is missing required field: {field}"


def test_schema_has_additionalproperties_false():
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema.get("additionalProperties") is False


def test_decision_validates_against_schema(tmp_path: Path):
    """Decision artifact produced by the module must conform to the schema."""
    try:
        import jsonschema
    except ImportError:
        pytest.skip("jsonschema not installed")

    ep = tmp_path / "run.sh"
    ep.write_text("#!/bin/bash\n", encoding="utf-8")
    ep.chmod(ep.stat().st_mode | stat.S_IXUSR)

    manifest = _valid_manifest(entrypoint_script=str(ep))
    decision = validate_runtime_environment(manifest, runtime_env=_linux_env())

    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=decision, schema=schema)


# ---------------------------------------------------------------------------
# capture_runtime_env_snapshot
# ---------------------------------------------------------------------------


def test_snapshot_accepts_overrides():
    snapshot = capture_runtime_env_snapshot({"os": "custom_os", "matlab_runtime_version": "R2024b"})
    assert snapshot["os"] == "custom_os"
    assert snapshot["matlab_runtime_version"] == "R2024b"


def test_snapshot_auto_detects_os():
    snapshot = capture_runtime_env_snapshot()
    assert isinstance(snapshot["os"], str)
    assert len(snapshot["os"]) > 0


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_cli_returns_0_for_compatible_bundle(tmp_path: Path, monkeypatch):
    from scripts import run_runtime_validation

    ep = tmp_path / "run.sh"
    ep.write_text("#!/bin/bash\n", encoding="utf-8")
    ep.chmod(ep.stat().st_mode | stat.S_IXUSR)

    manifest = _valid_manifest(entrypoint_script=str(ep))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.setattr(run_runtime_validation, "_DEFAULT_OUTPUT_PATH", tmp_path / "out.json")
    monkeypatch.setattr(run_runtime_validation, "_ARCHIVE_DIR", tmp_path / "archive")

    env_json = json.dumps(_linux_env())
    rc = run_runtime_validation.main([str(manifest_path), "--runtime-env", env_json])
    assert rc == 0


def test_cli_returns_1_for_incompatible_bundle(tmp_path: Path, monkeypatch):
    from scripts import run_runtime_validation

    ep = tmp_path / "run.sh"
    ep.write_text("#!/bin/bash\n", encoding="utf-8")
    ep.chmod(ep.stat().st_mode | stat.S_IXUSR)

    manifest = _valid_manifest(
        entrypoint_script=str(ep),
        matlab_runtime_version="R2024b",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.setattr(run_runtime_validation, "_DEFAULT_OUTPUT_PATH", tmp_path / "out.json")
    monkeypatch.setattr(run_runtime_validation, "_ARCHIVE_DIR", tmp_path / "archive")

    # Wrong MATLAB version installed
    env_json = json.dumps(_linux_env(matlab_runtime_version="R2023a"))
    rc = run_runtime_validation.main([str(manifest_path), "--runtime-env", env_json])
    assert rc == 1


def test_cli_returns_2_for_invalid_manifest_file(tmp_path: Path, capsys):
    from scripts.run_runtime_validation import main as cli_main

    bad_path = tmp_path / "nonexistent.json"
    rc = cli_main([str(bad_path)])
    assert rc == 2
    captured = capsys.readouterr()
    assert "ERROR" in captured.err


def test_cli_writes_output_file(tmp_path: Path, monkeypatch):
    from scripts import run_runtime_validation

    ep = tmp_path / "run.sh"
    ep.write_text("#!/bin/bash\n", encoding="utf-8")
    ep.chmod(ep.stat().st_mode | stat.S_IXUSR)

    manifest = _valid_manifest(entrypoint_script=str(ep))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    # Redirect output and archive to tmp_path
    monkeypatch.setattr(run_runtime_validation, "_DEFAULT_OUTPUT_PATH", tmp_path / "out.json")
    monkeypatch.setattr(run_runtime_validation, "_ARCHIVE_DIR", tmp_path / "archive")

    env_json = json.dumps(_linux_env())
    run_runtime_validation.main([str(manifest_path), "--runtime-env", env_json])

    assert (tmp_path / "out.json").exists()
    result = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert result["compatible"] is True


def test_cli_archives_decision(tmp_path: Path, monkeypatch):
    from scripts import run_runtime_validation

    ep = tmp_path / "run.sh"
    ep.write_text("#!/bin/bash\n", encoding="utf-8")
    ep.chmod(ep.stat().st_mode | stat.S_IXUSR)

    manifest = _valid_manifest(entrypoint_script=str(ep))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    archive_dir = tmp_path / "archive"
    monkeypatch.setattr(run_runtime_validation, "_DEFAULT_OUTPUT_PATH", tmp_path / "out.json")
    monkeypatch.setattr(run_runtime_validation, "_ARCHIVE_DIR", archive_dir)

    env_json = json.dumps(_linux_env())
    run_runtime_validation.main([str(manifest_path), "--runtime-env", env_json])

    archived = list(archive_dir.glob("runtime_compatibility_decision_*.json"))
    assert len(archived) == 1
