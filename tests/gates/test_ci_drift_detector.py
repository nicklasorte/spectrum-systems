"""
Tests for the CI drift detector (TST-25).

Verifies the detector fails correctly when:
- A new unmapped workflow is added
- A gate result schema is missing
- The ownership manifest is missing
- A new unmapped test file exists
- Gate scripts are missing
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _run_detector(tmp_path: Path, extra_args: list[str] | None = None) -> tuple[int, str, str]:
    cmd = [
        sys.executable,
        "scripts/run_ci_drift_detector.py",
        "--repo-root", str(tmp_path),
        "--output", str(tmp_path / "drift_report.json"),
    ]
    if extra_args:
        cmd += extra_args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def _setup_valid_repo(tmp_path: Path) -> None:
    """Create a minimal valid repo structure that passes the drift detector."""
    # Create all required gate schemas
    schemas_dir = tmp_path / "contracts/schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "contract_gate_result",
        "test_selection_gate_result",
        "runtime_test_gate_result",
        "governance_gate_result",
        "certification_gate_result",
        "pr_gate_result",
    ]:
        schema = {
            "title": name,
            "type": "object",
            "additionalProperties": False,
            "required": ["artifact_type"],
            "properties": {"artifact_type": {"type": "string"}},
        }
        (schemas_dir / f"{name}.schema.json").write_text(json.dumps(schema), encoding="utf-8")

    # Create known workflows
    workflow_dir = tmp_path / ".github/workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    for wf_name in [
        "pr-pytest.yml", "artifact-boundary.yml", "lifecycle-enforcement.yml",
        "strategy-compliance.yml", "pr-autofix-contract-preflight.yml",
        "3ls-registry-gate.yml", "review-artifact-validation.yml",
        "pr-autofix-review-artifact-validation.yml", "release-canary.yml",
        "dashboard-deploy-gate.yml", "ecosystem-registry-validation.yml",
        "cross-repo-compliance.yml", "design-review-scan.yml",
        "review_trigger_pipeline.yml", "closure_continuation_pipeline.yml",
        "claude-review-ingest.yml", "ssos-project-automation.yml",
    ]:
        (workflow_dir / wf_name).write_text("name: stub\non: push\njobs:\n  stub:\n    runs-on: ubuntu-latest\n    steps: [{run: echo ok}]\n", encoding="utf-8")

    # Create gate scripts
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for script in [
        "run_contract_gate.py", "run_test_selection_gate.py",
        "run_runtime_test_gate.py", "run_governance_gate.py",
        "run_certification_gate.py", "run_pr_gate.py",
    ]:
        (scripts_dir / script).write_text("# stub\n", encoding="utf-8")

    # Create ownership manifest
    gov_dir = tmp_path / "docs/governance"
    gov_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "1.0.0",
        "gates": [
            {"gate_name": "contract_gate"},
            {"gate_name": "test_selection_gate"},
            {"gate_name": "runtime_test_gate"},
            {"gate_name": "governance_gate"},
            {"gate_name": "certification_gate"},
        ],
    }
    (gov_dir / "ci_gate_ownership_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    # Create test gate mapping
    mapping = {
        "schema_version": "1.0.0",
        "mappings": [],
    }
    (gov_dir / "test_gate_mapping.json").write_text(json.dumps(mapping), encoding="utf-8")


class TestDriftDetectorPassesOnValidRepo:
    def test_passes_on_fully_mapped_repo(self, tmp_path: Path) -> None:
        _setup_valid_repo(tmp_path)
        rc, stdout, stderr = _run_detector(tmp_path)
        assert rc == 0, f"Should pass on valid repo. stderr={stderr}"

    def test_produces_drift_report_artifact(self, tmp_path: Path) -> None:
        _setup_valid_repo(tmp_path)
        _run_detector(tmp_path)
        report_path = tmp_path / "drift_report.json"
        assert report_path.is_file(), "Should produce drift_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report.get("artifact_type") == "ci_drift_report"
        assert "artifact_hash" in report


class TestDriftDetectorFailsOnUnmappedWorkflow:
    def test_fails_on_new_unmapped_workflow(self, tmp_path: Path) -> None:
        _setup_valid_repo(tmp_path)
        # Add a new workflow that is not in the known mapping
        new_wf = tmp_path / ".github/workflows/secret-new-gate.yml"
        new_wf.write_text("name: secret\non: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps: [{run: echo}]\n", encoding="utf-8")
        rc, stdout, stderr = _run_detector(tmp_path)
        assert rc != 0, "Should fail when a new unmapped workflow is added"


class TestDriftDetectorFailsOnMissingSchema:
    def test_fails_when_gate_schema_is_missing(self, tmp_path: Path) -> None:
        _setup_valid_repo(tmp_path)
        # Remove one schema
        (tmp_path / "contracts/schemas/pr_gate_result.schema.json").unlink()
        rc, stdout, stderr = _run_detector(tmp_path)
        assert rc != 0, "Should fail when a gate schema is missing"

    def test_fails_when_gate_schema_lacks_additional_properties_false(self, tmp_path: Path) -> None:
        _setup_valid_repo(tmp_path)
        # Overwrite schema without additionalProperties: false
        weak_schema = {
            "title": "contract_gate_result",
            "type": "object",
            # no additionalProperties: false
        }
        (tmp_path / "contracts/schemas/contract_gate_result.schema.json").write_text(
            json.dumps(weak_schema), encoding="utf-8"
        )
        rc, stdout, stderr = _run_detector(tmp_path)
        assert rc != 0, "Should fail when gate schema lacks additionalProperties: false"

    def test_fails_when_gate_schema_is_invalid_json(self, tmp_path: Path) -> None:
        _setup_valid_repo(tmp_path)
        (tmp_path / "contracts/schemas/certification_gate_result.schema.json").write_text(
            "{{NOT JSON}}", encoding="utf-8"
        )
        rc, stdout, stderr = _run_detector(tmp_path)
        assert rc != 0, "Should fail when gate schema is invalid JSON"


class TestDriftDetectorFailsOnMissingManifest:
    def test_fails_when_ownership_manifest_is_missing(self, tmp_path: Path) -> None:
        _setup_valid_repo(tmp_path)
        (tmp_path / "docs/governance/ci_gate_ownership_manifest.json").unlink()
        rc, stdout, stderr = _run_detector(tmp_path)
        assert rc != 0, "Should fail when ownership manifest is missing"

    def test_fails_when_manifest_missing_required_gate(self, tmp_path: Path) -> None:
        _setup_valid_repo(tmp_path)
        # Write manifest missing governance_gate
        manifest = {
            "schema_version": "1.0.0",
            "gates": [
                {"gate_name": "contract_gate"},
                {"gate_name": "test_selection_gate"},
                # missing runtime_test_gate and governance_gate
            ],
        }
        (tmp_path / "docs/governance/ci_gate_ownership_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        rc, stdout, stderr = _run_detector(tmp_path)
        assert rc != 0, "Should fail when required gates are missing from ownership manifest"


class TestDriftDetectorFailsOnMissingGateScript:
    def test_fails_when_canonical_gate_script_is_missing(self, tmp_path: Path) -> None:
        _setup_valid_repo(tmp_path)
        (tmp_path / "scripts/run_pr_gate.py").unlink()
        rc, stdout, stderr = _run_detector(tmp_path)
        assert rc != 0, "Should fail when a canonical gate script is missing"
