from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.failure_diagnosis_engine import (
    FailureDiagnosisError,
    build_failure_diagnosis_artifact,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "failure_diagnosis"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _build_from_fixture(name: str) -> dict:
    payload = _load_fixture(name)
    return build_failure_diagnosis_artifact(
        failure_source_type=payload["failure_source_type"],
        source_artifact_refs=payload["source_artifact_refs"],
        failure_payload=payload["failure_payload"],
        emitted_at="2026-04-05T00:00:00Z",
        run_id="run-fre-test",
        trace_id="trace-fre-test",
    )


def test_preflight_missing_surface_diagnosis() -> None:
    artifact = _build_from_fixture("preflight_missing_control_input")
    assert artifact["primary_root_cause"] == "contract_registration_missing"
    assert artifact["smallest_safe_fix_class"] == "align_contract_registration"


def test_manifest_registry_mismatch_diagnosis() -> None:
    artifact = _build_from_fixture("manifest_registry_mismatch")
    assert artifact["primary_root_cause"] == "contract_registration_missing"


def test_schema_example_drift_diagnosis() -> None:
    artifact = _build_from_fixture("schema_example_drift")
    assert artifact["primary_root_cause"] == "schema_mismatch"


def test_test_expectation_drift_diagnosis() -> None:
    artifact = _build_from_fixture("test_expectation_drift")
    assert artifact["primary_root_cause"] == "test_expectation_drift"


def test_invariant_violation_precedence_over_downstream_symptom() -> None:
    artifact = _build_from_fixture("invariant_violation")
    assert artifact["primary_root_cause"] == "branch_policy_violation"
    assert "schema_mismatch" in artifact["secondary_contributors"]


def test_deterministic_output_for_same_input() -> None:
    first = _build_from_fixture("manifest_registry_mismatch")
    second = _build_from_fixture("manifest_registry_mismatch")
    assert first == second


def test_fail_closed_when_required_evidence_missing() -> None:
    with pytest.raises(FailureDiagnosisError, match="missing required intake evidence"):
        build_failure_diagnosis_artifact(
            failure_source_type="contract_enforcement",
            source_artifact_refs=["contracts/standards-manifest.json"],
            failure_payload={"observed_failure_summary": "no machine-readable evidence"},
            emitted_at="2026-04-05T00:00:00Z",
        )


def test_artifact_schema_and_example_validate() -> None:
    schema = load_schema("failure_diagnosis_artifact")
    example = json.loads((_REPO_ROOT / "contracts" / "examples" / "failure_diagnosis_artifact.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(example)


def test_standards_manifest_registers_failure_diagnosis_contract() -> None:
    manifest = json.loads((_REPO_ROOT / "contracts" / "standards-manifest.json").read_text(encoding="utf-8"))
    entries = [entry for entry in manifest.get("contracts", []) if entry.get("artifact_type") == "failure_diagnosis_artifact"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["artifact_class"] == "coordination"
    assert entry["example_path"] == "contracts/examples/failure_diagnosis_artifact.json"


def test_cli_writes_artifact_and_exit_code() -> None:
    output_path = _REPO_ROOT / "outputs" / "failure_diagnosis" / "pytest-failure_diagnosis_artifact.json"
    if output_path.exists():
        output_path.unlink()

    cmd = [
        sys.executable,
        "scripts/build_failure_diagnosis_artifact.py",
        "--input",
        "tests/fixtures/failure_diagnosis/manifest_registry_mismatch.json",
        "--output",
        str(output_path),
        "--emitted-at",
        "2026-04-05T00:00:00Z",
        "--run-id",
        "run-fre-cli-test",
        "--trace-id",
        "trace-fre-cli-test",
    ]
    proc = subprocess.run(cmd, cwd=_REPO_ROOT, capture_output=True, text=True, check=False)
    assert proc.returncode == 2
    assert output_path.is_file()
