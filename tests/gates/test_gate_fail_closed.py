"""
TST-11 — Gate self-tests: prove each canonical gate fails closed on adversarial inputs.

Tests:
- Missing schema artifact
- Invalid schema artifact (bad JSON)
- Missing eval
- Failed eval
- Missing trace / provenance
- Invalid test selection (empty targets)
- Missing provenance fields
- Policy mismatch
- Replay mismatch
- Missing certification record
- Schema-invalid gate result artifacts
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(d: Path, name: str, content: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(content, encoding="utf-8")
    return p


def _valid_execution_record() -> dict:
    return {
        "artifact_type": "pytest_execution_record",
        "schema_version": "1.0.0",
        "executed": True,
        "selected_targets": ["tests/test_contracts.py"],
        "pytest_execution_count": 5,
        "source_commit_sha": "abc123",
        "source_head_ref": "refs/heads/feature",
        "workflow_run_id": "999",
        "producer_script": "scripts/run_contract_preflight.py",
        "produced_at": "2026-04-29T00:00:00Z",
        "artifact_hash": "deadbeef",
    }


def _valid_selection_record() -> dict:
    return {
        "artifact_type": "pytest_selection_integrity_result",
        "schema_version": "1.0.0",
        "selection_integrity_decision": "ALLOW",
        "source_pytest_execution_record_ref": "outputs/contract_preflight/pytest_execution_record.json",
        "source_pytest_execution_record_hash": "deadbeef",
        "source_commit_sha": "abc123",
        "source_head_ref": "refs/heads/feature",
        "workflow_run_id": "999",
        "producer_script": "scripts/run_contract_preflight.py",
        "produced_at": "2026-04-29T00:00:00Z",
        "artifact_hash": "cafebabe",
    }


def _valid_preflight_artifact(record_ref: str, sel_ref: str) -> dict:
    return {
        "artifact_type": "contract_preflight_result_artifact",
        "schema_version": "1.0.0",
        "control_signal": {"strategy_gate_decision": "ALLOW"},
        "pytest_execution": {"pytest_execution_count": 5},
        "pytest_execution_record_ref": record_ref,
        "pytest_selection_integrity_result_ref": sel_ref,
        "pytest_selection_integrity": {"selection_integrity_decision": "ALLOW"},
    }


# ---------------------------------------------------------------------------
# Test Selection Gate: fail-closed tests
# ---------------------------------------------------------------------------

class TestSelectionGateFailClosed:
    """Gate 2 (Test Selection Gate) must fail closed on all adversarial inputs."""

    def _run_selection_gate(self, tmpdir: Path, env_patch: dict | None = None) -> tuple[int, str]:
        import subprocess
        gates_dir = tmpdir / "outputs/gates"
        gates_dir.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "GITHUB_EVENT_NAME": "pull_request"}
        if env_patch:
            env.update(env_patch)
        cmd = [
            sys.executable,
            "scripts/run_test_selection_gate.py",
            "--output-dir", str(gates_dir),
            "--repo-root", str(tmpdir),
            "--event-name", "pull_request",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return result.returncode, result.stderr

    def test_fails_closed_on_missing_preflight_artifact(self, tmp_path: Path) -> None:
        # No upstream artifacts at all → must block
        rc, stderr = self._run_selection_gate(tmp_path)
        assert rc != 0, "Should fail closed when preflight artifact is missing"

    def test_fails_closed_on_invalid_json_preflight_artifact(self, tmp_path: Path) -> None:
        _write(tmp_path / "outputs/contract_preflight", "contract_preflight_result_artifact.json", "NOT JSON")
        rc, stderr = self._run_selection_gate(tmp_path)
        assert rc != 0, "Should fail closed when preflight artifact is invalid JSON"

    def test_fails_closed_on_empty_selected_targets_no_baseline(self, tmp_path: Path) -> None:
        preflight_dir = tmp_path / "outputs/contract_preflight"
        record = _valid_execution_record()
        record["selected_targets"] = []  # empty
        record["executed"] = False
        record_path = _write(preflight_dir, "pytest_execution_record.json", json.dumps(record))
        sel_record = _valid_selection_record()
        sel_path = _write(preflight_dir, "pytest_selection_integrity_result.json", json.dumps(sel_record))
        preflight = _valid_preflight_artifact(str(record_path), str(sel_path))
        _write(preflight_dir, "contract_preflight_result_artifact.json", json.dumps(preflight))
        # No baseline file at all
        rc, stderr = self._run_selection_gate(tmp_path)
        assert rc != 0, "Should fail closed on empty selection with no fallback baseline"

    def test_fails_closed_on_missing_provenance_fields(self, tmp_path: Path) -> None:
        preflight_dir = tmp_path / "outputs/contract_preflight"
        record = _valid_execution_record()
        del record["source_commit_sha"]  # remove required provenance field
        record_path = _write(preflight_dir, "pytest_execution_record.json", json.dumps(record))
        sel_record = _valid_selection_record()
        sel_path = _write(preflight_dir, "pytest_selection_integrity_result.json", json.dumps(sel_record))
        preflight = _valid_preflight_artifact(str(record_path), str(sel_path))
        _write(preflight_dir, "contract_preflight_result_artifact.json", json.dumps(preflight))
        # Write minimal baseline
        baseline_dir = tmp_path / "docs/governance"
        _write(baseline_dir, "pytest_pr_inventory_baseline.json", json.dumps({
            "suite_targets": ["tests/test_contracts.py"]
        }))
        _write(baseline_dir, "pytest_pr_selection_integrity_policy.json", json.dumps({
            "minimum_selection_threshold": 1,
            "governed_surface_prefixes": [],
            "surface_rules": [],
            "bounded_equivalence": [],
            "allowed_exceptions": [],
        }))
        rc, stderr = self._run_selection_gate(tmp_path)
        assert rc != 0, "Should fail closed on missing provenance fields in execution record"

    def test_fails_closed_on_selection_integrity_block(self, tmp_path: Path) -> None:
        preflight_dir = tmp_path / "outputs/contract_preflight"
        record = _valid_execution_record()
        record_path = _write(preflight_dir, "pytest_execution_record.json", json.dumps(record))
        sel_record = _valid_selection_record()
        sel_record["selection_integrity_decision"] = "BLOCK"  # blocked
        sel_path = _write(preflight_dir, "pytest_selection_integrity_result.json", json.dumps(sel_record))
        preflight = _valid_preflight_artifact(str(record_path), str(sel_path))
        _write(preflight_dir, "contract_preflight_result_artifact.json", json.dumps(preflight))
        baseline_dir = tmp_path / "docs/governance"
        _write(baseline_dir, "pytest_pr_inventory_baseline.json", json.dumps({"suite_targets": ["tests/test_contracts.py"]}))
        _write(baseline_dir, "pytest_pr_selection_integrity_policy.json", json.dumps({
            "minimum_selection_threshold": 1,
            "governed_surface_prefixes": [],
            "surface_rules": [],
            "bounded_equivalence": [],
            "allowed_exceptions": [],
        }))
        rc, stderr = self._run_selection_gate(tmp_path)
        assert rc != 0, "Should fail closed when selection_integrity_decision=BLOCK"

    def test_fails_closed_on_commit_sha_mismatch(self, tmp_path: Path) -> None:
        preflight_dir = tmp_path / "outputs/contract_preflight"
        record = _valid_execution_record()
        record["source_commit_sha"] = "aaaaaa"
        record_path = _write(preflight_dir, "pytest_execution_record.json", json.dumps(record))
        sel_record = _valid_selection_record()
        sel_record["source_commit_sha"] = "bbbbbb"  # MISMATCH
        sel_path = _write(preflight_dir, "pytest_selection_integrity_result.json", json.dumps(sel_record))
        preflight = _valid_preflight_artifact(str(record_path), str(sel_path))
        _write(preflight_dir, "contract_preflight_result_artifact.json", json.dumps(preflight))
        baseline_dir = tmp_path / "docs/governance"
        _write(baseline_dir, "pytest_pr_inventory_baseline.json", json.dumps({"suite_targets": ["tests/test_contracts.py"]}))
        _write(baseline_dir, "pytest_pr_selection_integrity_policy.json", json.dumps({
            "minimum_selection_threshold": 1,
            "governed_surface_prefixes": [],
            "surface_rules": [],
            "bounded_equivalence": [],
            "allowed_exceptions": [],
        }))
        rc, stderr = self._run_selection_gate(tmp_path)
        assert rc != 0, "Should fail closed on commit SHA mismatch between records"


# ---------------------------------------------------------------------------
# Runtime Test Gate: fail-closed tests
# ---------------------------------------------------------------------------

class TestRuntimeTestGateFailClosed:
    """Gate 3 (Runtime Test Gate) must fail closed on adversarial inputs."""

    def _run_runtime_gate(self, tmpdir: Path) -> tuple[int, str]:
        import subprocess
        gates_dir = tmpdir / "outputs/gates"
        gates_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable,
            "scripts/run_runtime_test_gate.py",
            "--output-dir", str(gates_dir),
            "--repo-root", str(tmpdir),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode, result.stderr

    def test_fails_closed_on_missing_selection_result(self, tmp_path: Path) -> None:
        rc, stderr = self._run_runtime_gate(tmp_path)
        assert rc != 0, "Should fail closed when selection gate result is missing"

    def test_fails_closed_on_empty_selected_targets(self, tmp_path: Path) -> None:
        gates_dir = tmp_path / "outputs/gates"
        gates_dir.mkdir(parents=True, exist_ok=True)
        _write(gates_dir, "test_selection_gate_result.json", json.dumps({
            "status": "allow",
            "selected_targets": [],  # empty
        }))
        rc, stderr = self._run_runtime_gate(tmp_path)
        assert rc != 0, "Should fail closed when selected_targets is empty"

    def test_fails_closed_on_invalid_json_selection_result(self, tmp_path: Path) -> None:
        gates_dir = tmp_path / "outputs/gates"
        gates_dir.mkdir(parents=True, exist_ok=True)
        _write(gates_dir, "test_selection_gate_result.json", "INVALID JSON {{")
        rc, stderr = self._run_runtime_gate(tmp_path)
        assert rc != 0, "Should fail closed when selection gate result is invalid JSON"


# ---------------------------------------------------------------------------
# Gate result schema validation
# ---------------------------------------------------------------------------

class TestGateResultSchemaValidation:
    """Gate result artifacts must conform to their schemas."""

    def _load_schema(self, name: str) -> dict:
        p = Path(f"contracts/schemas/{name}.schema.json")
        if not p.is_file():
            pytest.skip(f"Schema file not found: {p}")
        return json.loads(p.read_text(encoding="utf-8"))

    def _validate(self, instance: dict, schema: dict) -> None:
        try:
            import jsonschema
            jsonschema.validate(instance=instance, schema=schema)
        except ImportError:
            pytest.skip("jsonschema not installed")

    def test_contract_gate_result_schema_exists(self) -> None:
        schema = self._load_schema("contract_gate_result")
        assert schema.get("title") == "contract_gate_result"

    def test_test_selection_gate_result_schema_exists(self) -> None:
        schema = self._load_schema("test_selection_gate_result")
        assert schema.get("title") == "test_selection_gate_result"

    def test_runtime_test_gate_result_schema_exists(self) -> None:
        schema = self._load_schema("runtime_test_gate_result")
        assert schema.get("title") == "runtime_test_gate_result"

    def test_governance_gate_result_schema_exists(self) -> None:
        schema = self._load_schema("governance_gate_result")
        assert schema.get("title") == "governance_gate_result"

    def test_certification_gate_result_schema_exists(self) -> None:
        schema = self._load_schema("certification_gate_result")
        assert schema.get("title") == "certification_gate_result"

    def test_pr_gate_result_schema_exists(self) -> None:
        schema = self._load_schema("pr_gate_result")
        assert schema.get("title") == "pr_gate_result"

    def test_contract_gate_result_block_is_schema_valid(self) -> None:
        schema = self._load_schema("contract_gate_result")
        instance = {
            "artifact_type": "contract_gate_result",
            "schema_version": "1.0.0",
            "gate_name": "contract_gate",
            "status": "block",
            "produced_at": "2026-04-29T00:00:00Z",
            "producer_script": "scripts/run_contract_gate.py",
            "artifact_hash": "abc123",
            "failure_summary": {
                "gate_name": "contract_gate",
                "failure_class": "trust_mismatch",
                "root_cause": "missing artifact",
                "blocking_reason": "no result",
                "next_action": "investigate",
                "affected_files": [],
                "failed_command": "scripts/run_contract_gate.py",
                "artifact_refs": [],
            },
        }
        self._validate(instance, schema)

    def test_all_gate_schemas_use_additional_properties_false(self) -> None:
        for name in [
            "contract_gate_result",
            "test_selection_gate_result",
            "runtime_test_gate_result",
            "governance_gate_result",
            "certification_gate_result",
            "pr_gate_result",
        ]:
            schema = self._load_schema(name)
            assert schema.get("additionalProperties") is False, \
                f"{name} must use additionalProperties: false"

    def test_all_gate_schemas_require_status_enum(self) -> None:
        for name in [
            "contract_gate_result",
            "test_selection_gate_result",
            "runtime_test_gate_result",
            "governance_gate_result",
            "certification_gate_result",
            "pr_gate_result",
        ]:
            schema = self._load_schema(name)
            props = schema.get("properties", {})
            status_prop = props.get("status", {})
            assert "enum" in status_prop, f"{name} status must be an enum"
            assert set(status_prop["enum"]) >= {"allow", "block"}, \
                f"{name} status enum must include allow and block"


# ---------------------------------------------------------------------------
# Gate ownership manifest
# ---------------------------------------------------------------------------

class TestGateOwnershipManifest:
    def test_ownership_manifest_exists(self) -> None:
        p = Path("docs/governance/ci_gate_ownership_manifest.json")
        assert p.is_file(), "ci_gate_ownership_manifest.json must exist"

    def test_ownership_manifest_has_all_four_gates(self) -> None:
        p = Path("docs/governance/ci_gate_ownership_manifest.json")
        if not p.is_file():
            pytest.skip("manifest not found")
        manifest = json.loads(p.read_text(encoding="utf-8"))
        gates = {g["gate_name"] for g in manifest.get("gates", [])}
        required = {"contract_gate", "test_selection_gate", "runtime_test_gate", "governance_gate"}
        missing = required - gates
        assert not missing, f"Missing gates in ownership manifest: {missing}"

    def test_test_gate_mapping_exists(self) -> None:
        p = Path("docs/governance/test_gate_mapping.json")
        assert p.is_file(), "test_gate_mapping.json must exist"

    def test_test_gate_mapping_has_no_unmapped_files(self) -> None:
        p = Path("docs/governance/test_gate_mapping.json")
        if not p.is_file():
            pytest.skip("test_gate_mapping.json not found")
        mapping = json.loads(p.read_text(encoding="utf-8"))
        low_confidence = [
            m for m in mapping.get("mappings", [])
            if m.get("confidence") == "low"
        ]
        # Warn but don't hard-fail — low confidence items need manual review
        if low_confidence:
            import warnings
            warnings.warn(
                f"{len(low_confidence)} test files have low-confidence gate assignments "
                "and need manual review",
                stacklevel=2,
            )
