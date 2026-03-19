"""Tests for BD run-bundle contract + manifest hardening (Prompt BD).

Covers:
- valid manifest passes all validators
- missing required input detection
- missing required outputs (results_summary_json, provenance_json, log_file)
- no paper_relevant outputs
- missing provenance fields (source_case_ids, manifest_author, creation_context, rng)
- missing idempotency declaration
- schema validation negative cases (structural failures)
- CLI behaviour (valid, invalid, file-not-found, directory resolution)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict
import copy

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.run_bundle import (  # noqa: E402
    RunBundleManifest,
    classify_bundle_failure,
    derive_bundle_summary,
    load_run_bundle_manifest,
    normalize_run_bundle_manifest,
    validate_bundle_contract,
    validate_expected_outputs,
    validate_input_paths,
    validate_provenance_fields,
    validate_run_bundle_manifest,
)

_FIXTURE_PATH = _REPO_ROOT / "tests" / "fixtures" / "example_run_bundle_manifest.json"
_SCHEMA_PATH = _REPO_ROOT / "contracts" / "schemas" / "run_bundle_manifest.schema.json"
_DECISION_SCHEMA_PATH = (
    _REPO_ROOT / "contracts" / "schemas" / "run_bundle_validation_decision.schema.json"
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _valid_raw() -> Dict[str, Any]:
    """Return a minimal but fully valid raw manifest dict."""
    return {
        "bundle_version": "1.0.0",
        "run_id": "run-test-001",
        "matlab_release": "R2024b",
        "runtime_version_required": "R2024b",
        "platform": "linux-x86_64",
        "worker_entrypoint": "bin/run.sh",
        "component_cache": {
            "mcr_cache_root": "/tmp/mcr_cache",
            "mcr_cache_size": "2GB",
        },
        "startup_options": {
            "logfile": "logs/worker.log",
        },
        "inputs": [
            {"path": "inputs/cases.json", "type": "case_definition", "required": True},
        ],
        "expected_outputs": [
            {
                "path": "outputs/results_summary.json",
                "type": "results_summary_json",
                "required": True,
                "paper_relevant": True,
            },
            {
                "path": "outputs/provenance.json",
                "type": "provenance_json",
                "required": True,
                "paper_relevant": False,
            },
            {
                "path": "logs/worker.log",
                "type": "log_file",
                "required": True,
                "paper_relevant": False,
            },
        ],
        "provenance": {
            "source_artifact_ids": ["artifact-001"],
            "source_case_ids": ["case-001"],
            "rng_seed": 42,
            "manifest_author": "test-agent",
            "creation_context": "Unit test run.",
        },
        "execution_policy": {
            "idempotency_mode": "safe_rerun",
            "retry_allowed": False,
            "max_retries": 0,
            "stale_claim_timeout_hours": 1.0,
        },
        "created_at": "2024-01-01T00:00:00Z",
    }


def _manifest(**overrides) -> RunBundleManifest:
    raw = _valid_raw()
    raw.update(overrides)
    return RunBundleManifest(raw)


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------


def test_schema_files_exist():
    assert _SCHEMA_PATH.exists(), f"Schema not found: {_SCHEMA_PATH}"
    assert _DECISION_SCHEMA_PATH.exists(), f"Decision schema not found: {_DECISION_SCHEMA_PATH}"


def test_schema_is_valid_json():
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema.get("$schema") is not None
    assert schema.get("type") == "object"


# ---------------------------------------------------------------------------
# validate_run_bundle_manifest — JSON Schema structural checks
# ---------------------------------------------------------------------------


def test_schema_validation_passes_for_valid_manifest():
    manifest = RunBundleManifest(_valid_raw())
    errors = validate_run_bundle_manifest(manifest)
    assert errors == [], f"Unexpected errors: {errors}"


@pytest.mark.parametrize(
    "field",
    [
        "bundle_version",
        "run_id",
        "matlab_release",
        "runtime_version_required",
        "platform",
        "worker_entrypoint",
        "component_cache",
        "startup_options",
        "inputs",
        "expected_outputs",
        "provenance",
        "execution_policy",
        "created_at",
    ],
)
def test_schema_validation_fails_for_missing_required_field(field):
    raw = _valid_raw()
    del raw[field]
    manifest = RunBundleManifest(raw)
    errors = validate_run_bundle_manifest(manifest)
    assert any(field in e or "manifest_invalid" in e for e in errors)


def test_schema_validation_fails_for_invalid_platform():
    raw = _valid_raw()
    raw["platform"] = "macos-arm64"  # not in enum
    manifest = RunBundleManifest(raw)
    errors = validate_run_bundle_manifest(manifest)
    assert any("manifest_invalid" in e for e in errors)


def test_schema_validation_fails_for_invalid_bundle_version():
    raw = _valid_raw()
    raw["bundle_version"] = "not-semver"
    manifest = RunBundleManifest(raw)
    errors = validate_run_bundle_manifest(manifest)
    assert any("manifest_invalid" in e for e in errors)


def test_schema_validation_fails_for_invalid_output_type():
    raw = _valid_raw()
    raw["expected_outputs"][0]["type"] = "unsupported_type"
    manifest = RunBundleManifest(raw)
    errors = validate_run_bundle_manifest(manifest)
    assert any("manifest_invalid" in e for e in errors)


def test_schema_validation_fails_for_invalid_idempotency_mode():
    raw = _valid_raw()
    raw["execution_policy"]["idempotency_mode"] = "maybe_rerun"
    manifest = RunBundleManifest(raw)
    errors = validate_run_bundle_manifest(manifest)
    assert any("manifest_invalid" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_expected_outputs
# ---------------------------------------------------------------------------


def test_expected_outputs_passes_for_valid_manifest():
    manifest = RunBundleManifest(_valid_raw())
    errors = validate_expected_outputs(manifest)
    assert errors == []


@pytest.mark.parametrize("missing_type", ["results_summary_json", "provenance_json", "log_file"])
def test_expected_outputs_fails_when_required_type_missing(missing_type):
    raw = _valid_raw()
    raw["expected_outputs"] = [
        o for o in raw["expected_outputs"] if o["type"] != missing_type
    ]
    manifest = RunBundleManifest(raw)
    errors = validate_expected_outputs(manifest)
    assert any("output_contract_invalid" in e for e in errors)
    assert any(missing_type in e for e in errors)


def test_expected_outputs_fails_when_no_paper_relevant():
    raw = _valid_raw()
    for o in raw["expected_outputs"]:
        o["paper_relevant"] = False
    manifest = RunBundleManifest(raw)
    errors = validate_expected_outputs(manifest)
    assert any("paper_relevant" in e for e in errors)


def test_expected_outputs_passes_when_paper_relevant_present():
    raw = _valid_raw()
    raw["expected_outputs"][0]["paper_relevant"] = True
    manifest = RunBundleManifest(raw)
    errors = validate_expected_outputs(manifest)
    # other checks may still pass — just confirm no paper_relevant error
    assert not any("paper_relevant" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_input_paths
# ---------------------------------------------------------------------------


def test_input_paths_passes_without_bundle_root():
    manifest = RunBundleManifest(_valid_raw())
    errors = validate_input_paths(manifest, bundle_root=None)
    assert errors == []


def test_input_paths_fails_when_required_input_missing_on_disk(tmp_path):
    raw = _valid_raw()
    raw["inputs"] = [{"path": "inputs/missing_file.json", "type": "case_definition", "required": True}]
    manifest = RunBundleManifest(raw)
    errors = validate_input_paths(manifest, bundle_root=tmp_path)
    assert any("missing_required_input" in e for e in errors)
    assert any("missing_file.json" in e for e in errors)


def test_input_paths_passes_when_required_input_exists_on_disk(tmp_path):
    input_file = tmp_path / "inputs" / "cases.json"
    input_file.parent.mkdir(parents=True)
    input_file.write_text("{}", encoding="utf-8")

    raw = _valid_raw()
    raw["inputs"] = [{"path": "inputs/cases.json", "type": "case_definition", "required": True}]
    manifest = RunBundleManifest(raw)
    errors = validate_input_paths(manifest, bundle_root=tmp_path)
    assert errors == []


def test_input_paths_skips_optional_inputs_on_disk(tmp_path):
    raw = _valid_raw()
    raw["inputs"] = [
        {"path": "inputs/optional.json", "type": "optional_data", "required": False}
    ]
    manifest = RunBundleManifest(raw)
    errors = validate_input_paths(manifest, bundle_root=tmp_path)
    assert errors == []


# ---------------------------------------------------------------------------
# validate_provenance_fields
# ---------------------------------------------------------------------------


def test_provenance_passes_with_rng_seed():
    manifest = RunBundleManifest(_valid_raw())
    errors = validate_provenance_fields(manifest)
    assert errors == []


def test_provenance_passes_with_rng_state_ref():
    raw = _valid_raw()
    del raw["provenance"]["rng_seed"]
    raw["provenance"]["rng_state_ref"] = "provenance/rng_state.json"
    manifest = RunBundleManifest(raw)
    errors = validate_provenance_fields(manifest)
    assert errors == []


def test_provenance_fails_when_source_case_ids_empty():
    raw = _valid_raw()
    raw["provenance"]["source_case_ids"] = []
    manifest = RunBundleManifest(raw)
    errors = validate_provenance_fields(manifest)
    assert any("source_case_ids" in e for e in errors)


def test_provenance_fails_when_manifest_author_missing():
    raw = _valid_raw()
    del raw["provenance"]["manifest_author"]
    manifest = RunBundleManifest(raw)
    errors = validate_provenance_fields(manifest)
    assert any("manifest_author" in e for e in errors)


def test_provenance_fails_when_creation_context_missing():
    raw = _valid_raw()
    del raw["provenance"]["creation_context"]
    manifest = RunBundleManifest(raw)
    errors = validate_provenance_fields(manifest)
    assert any("creation_context" in e for e in errors)


def test_provenance_fails_when_no_rng():
    raw = _valid_raw()
    del raw["provenance"]["rng_seed"]
    # make sure rng_state_ref is also absent
    raw["provenance"].pop("rng_state_ref", None)
    manifest = RunBundleManifest(raw)
    errors = validate_provenance_fields(manifest)
    assert any("rng_seed" in e or "rng_state_ref" in e for e in errors)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_idempotency_passes_when_mode_set():
    manifest = RunBundleManifest(_valid_raw())
    decision = validate_bundle_contract(manifest)
    assert not any("idempotency_undefined" in c for c in decision["triggering_conditions"])


def test_idempotency_fails_when_mode_missing():
    raw = _valid_raw()
    del raw["execution_policy"]["idempotency_mode"]
    manifest = RunBundleManifest(raw)
    decision = validate_bundle_contract(manifest)
    assert any("idempotency_undefined" in c for c in decision["triggering_conditions"])


# ---------------------------------------------------------------------------
# validate_bundle_contract (top-level)
# ---------------------------------------------------------------------------


def test_valid_bundle_contract_produces_valid_true():
    manifest = RunBundleManifest(_valid_raw())
    decision = validate_bundle_contract(manifest)
    assert decision["valid"] is True
    assert decision["failure_type"] is None
    assert decision["triggering_conditions"] == []


def test_invalid_bundle_produces_valid_false():
    raw = _valid_raw()
    del raw["provenance"]["manifest_author"]
    manifest = RunBundleManifest(raw)
    decision = validate_bundle_contract(manifest)
    assert decision["valid"] is False
    assert decision["failure_type"] is not None


def test_decision_has_all_required_fields():
    manifest = RunBundleManifest(_valid_raw())
    decision = validate_bundle_contract(manifest)
    required_fields = [
        "decision_id", "run_id", "created_at", "valid", "failure_type",
        "triggering_conditions", "required_actions", "bundle_summary", "notes",
    ]
    for field in required_fields:
        assert field in decision, f"Missing field: {field}"


def test_decision_conforms_to_schema():
    """Validate decision artifact against the decision schema required fields."""
    schema = json.loads(_DECISION_SCHEMA_PATH.read_text(encoding="utf-8"))
    manifest = RunBundleManifest(_valid_raw())
    decision = validate_bundle_contract(manifest)
    for field in schema.get("required", []):
        assert field in decision


# ---------------------------------------------------------------------------
# classify_bundle_failure
# ---------------------------------------------------------------------------


def test_classify_bundle_failure_returns_none_for_no_conditions():
    assert classify_bundle_failure([]) is None


def test_classify_bundle_failure_returns_highest_priority():
    conditions = [
        "provenance_incomplete: missing author",
        "manifest_invalid: missing field",
    ]
    assert classify_bundle_failure(conditions) == "manifest_invalid"


# ---------------------------------------------------------------------------
# derive_bundle_summary
# ---------------------------------------------------------------------------


def test_derive_bundle_summary_contains_expected_keys():
    manifest = RunBundleManifest(_valid_raw())
    summary = derive_bundle_summary(manifest)
    assert summary["run_id"] == "run-test-001"
    assert summary["platform"] == "linux-x86_64"
    assert isinstance(summary["paper_relevant_outputs"], list)


# ---------------------------------------------------------------------------
# load / normalize
# ---------------------------------------------------------------------------


def test_load_run_bundle_manifest_from_fixture():
    manifest = load_run_bundle_manifest(_FIXTURE_PATH)
    assert manifest.run_id == "run-matlab-spectral-analysis-2024b-001"


def test_load_run_bundle_manifest_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_run_bundle_manifest(bad)


def test_normalize_strips_whitespace():
    raw = _valid_raw()
    raw["run_id"] = "  run-test-001  "
    manifest = RunBundleManifest(raw)
    normalized = normalize_run_bundle_manifest(manifest)
    assert normalized.run_id == "run-test-001"


def test_normalize_does_not_mutate_original():
    raw = _valid_raw()
    raw["run_id"] = "  run-test-001  "
    manifest = RunBundleManifest(raw)
    normalize_run_bundle_manifest(manifest)
    assert manifest.run_id == "  run-test-001  "


# ---------------------------------------------------------------------------
# Fixture-based integration test
# ---------------------------------------------------------------------------


def test_fixture_manifest_passes_full_validation():
    manifest = load_run_bundle_manifest(_FIXTURE_PATH)
    manifest = normalize_run_bundle_manifest(manifest)
    decision = validate_bundle_contract(manifest)
    assert decision["valid"] is True, f"Fixture failed: {decision['triggering_conditions']}"


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_cli_valid_manifest(tmp_path):
    from scripts.run_bundle_validation import main

    # Write valid manifest to tmp dir
    manifest_file = tmp_path / "run_bundle_manifest.json"
    manifest_file.write_text(json.dumps(_valid_raw()), encoding="utf-8")

    exit_code = main([str(manifest_file)])
    assert exit_code == 0


def test_cli_invalid_manifest_returns_1(tmp_path):
    from scripts.run_bundle_validation import main

    raw = _valid_raw()
    del raw["provenance"]["manifest_author"]
    manifest_file = tmp_path / "run_bundle_manifest.json"
    manifest_file.write_text(json.dumps(raw), encoding="utf-8")

    exit_code = main([str(manifest_file)])
    assert exit_code == 1


def test_cli_missing_file_returns_2():
    from scripts.run_bundle_validation import main

    exit_code = main(["/tmp/does_not_exist_xyz.json"])
    assert exit_code == 2


def test_cli_directory_with_manifest(tmp_path):
    from scripts.run_bundle_validation import main

    # Create the required input file so on-disk checks pass
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    (input_dir / "cases.json").write_text("{}", encoding="utf-8")

    manifest_file = tmp_path / "run_bundle_manifest.json"
    manifest_file.write_text(json.dumps(_valid_raw()), encoding="utf-8")

    exit_code = main([str(tmp_path)])
    assert exit_code == 0


def test_cli_directory_without_manifest_returns_2(tmp_path):
    from scripts.run_bundle_validation import main

    exit_code = main([str(tmp_path)])
    assert exit_code == 2


def test_cli_writes_output_file(tmp_path, monkeypatch):
    from scripts import run_bundle_validation as rbc

    manifest_file = tmp_path / "run_bundle_manifest.json"
    manifest_file.write_text(json.dumps(_valid_raw()), encoding="utf-8")

    output_path = tmp_path / "decision.json"
    archive_dir = tmp_path / "archive"

    monkeypatch.setattr(rbc, "_DEFAULT_OUTPUT_PATH", output_path)
    monkeypatch.setattr(rbc, "_ARCHIVE_DIR", archive_dir)

    exit_code = rbc.main([str(manifest_file)])
    assert exit_code == 0
    assert output_path.exists()
    decision = json.loads(output_path.read_text())
    assert decision["valid"] is True


def test_cli_archives_decision(tmp_path, monkeypatch):
    from scripts import run_bundle_validation as rbc

    manifest_file = tmp_path / "run_bundle_manifest.json"
    manifest_file.write_text(json.dumps(_valid_raw()), encoding="utf-8")

    output_path = tmp_path / "decision.json"
    archive_dir = tmp_path / "archive"

    monkeypatch.setattr(rbc, "_DEFAULT_OUTPUT_PATH", output_path)
    monkeypatch.setattr(rbc, "_ARCHIVE_DIR", archive_dir)

    rbc.main([str(manifest_file)])
    archived = list(archive_dir.glob("*.json"))
    assert len(archived) == 1
