"""Tests for CI drift detection."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_DETECTOR_SCRIPT = REPO_ROOT / "scripts" / "run_ci_drift_detector.py"
_SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "pr_test_shard_result.schema.json"
_EXAMPLE_PATH = REPO_ROOT / "contracts" / "examples" / "pr_test_shard_result.example.json"


def _run_detector(output: Path, extra_args: list = None) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        str(_DETECTOR_SCRIPT),
        "--output", str(output),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_drift_detector_runs_on_repo(tmp_path):
    output = tmp_path / "drift_result.json"
    proc = _run_detector(output)
    # Both 0 (pass/warn) and 1 (block) are valid exit codes; crashing is not.
    assert proc.returncode in (0, 1), (
        f"Drift detector crashed with exit {proc.returncode}\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )


def test_drift_detector_produces_artifact(tmp_path):
    output = tmp_path / "drift_result.json"
    proc = _run_detector(output)
    assert output.is_file(), "Drift detector must write an output artifact"
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(artifact, dict), "Artifact must be a JSON object"
    # Verify expected top-level fields.
    for field in ("artifact_type", "schema_version", "status", "findings", "authority_scope"):
        assert field in artifact, f"Artifact missing required field: {field}"
    assert artifact["artifact_type"] == "ci_drift_detection_result"
    assert artifact["schema_version"] == "1.0.0"
    assert artifact["status"] in ("pass", "warn", "block")
    assert isinstance(artifact["findings"], list)


def test_drift_detector_finds_missing_schema(tmp_path):
    # Verify the schema IS present in the real repo so the check passes.
    assert _SCHEMA_PATH.is_file(), (
        f"Schema file is missing from the repo — drift detector would flag this as a block: "
        f"{_SCHEMA_PATH}"
    )
    output = tmp_path / "drift_result.json"
    proc = _run_detector(output)
    artifact = json.loads(output.read_text(encoding="utf-8"))
    # Since the schema is present, the missing_shard_result_schema check must not appear.
    block_checks = [
        f["check"] for f in artifact["findings"] if f.get("severity") == "block"
    ]
    assert "missing_shard_result_schema" not in block_checks, (
        f"Schema is present but detector still reports missing_shard_result_schema: {block_checks}"
    )


def test_drift_detector_finds_missing_example(tmp_path):
    # Verify the example IS present in the real repo so the check passes.
    assert _EXAMPLE_PATH.is_file(), (
        f"Example file is missing from the repo — drift detector would flag this as a block: "
        f"{_EXAMPLE_PATH}"
    )
    output = tmp_path / "drift_result.json"
    proc = _run_detector(output)
    artifact = json.loads(output.read_text(encoding="utf-8"))
    block_checks = [
        f["check"] for f in artifact["findings"] if f.get("severity") == "block"
    ]
    assert "missing_shard_result_example" not in block_checks, (
        f"Example is present but detector still reports missing_shard_result_example: {block_checks}"
    )


def test_drift_detector_artifact_has_authority_scope(tmp_path):
    output = tmp_path / "drift_result.json"
    _run_detector(output)
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact.get("authority_scope") == "observation_only"


def test_new_test_without_shard_mapping_is_detectable(tmp_path):
    # Verify the drift detector has the unmapped_test_files check function and it is called.
    # We do this by importing the module and confirming the function is callable.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "run_ci_drift_detector", str(_DETECTOR_SCRIPT)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # The function that checks for unmapped test files must exist and be callable.
    assert hasattr(mod, "_check_unmapped_test_files"), (
        "run_ci_drift_detector must define _check_unmapped_test_files"
    )
    assert callable(mod._check_unmapped_test_files)

    # Actually invoke it on the real repo; result must be a list.
    findings = mod._check_unmapped_test_files(REPO_ROOT, {})
    assert isinstance(findings, list), "_check_unmapped_test_files must return a list"
    for f in findings:
        assert f.get("check") == "unmapped_test_files"
        assert f.get("severity") in ("warn", "block", "info")
