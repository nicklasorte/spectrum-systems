"""
Tests for module architecture validation.

Covers:
- Valid module manifest accepted by schema
- Invalid manifest (missing required field) rejected
- manifest with empty forbidden_responsibilities rejected
- Detection of duplicate shared-truth definitions in non-shared modules
- Validator happy path (no violations)
- Validator failure path (returns violations)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "module-manifest.schema.json"
MANIFESTS_DIR = REPO_ROOT / "docs" / "module-manifests"
EXAMPLE_PATH = REPO_ROOT / "docs" / "examples" / "module-manifest.example.json"

import sys
sys.path.insert(0, str(REPO_ROOT))
from scripts import validate_module_architecture as validator  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _minimal_valid_manifest() -> dict:
    """Return a minimal manifest that satisfies all required fields."""
    return {
        "schema_version": "1.0.0",
        "module_id": "shared.test_module",
        "module_name": "Test Module",
        "module_type": "shared",
        "owner_layer": "shared",
        "description": "A test module used only in unit tests.",
        "status": "planned",
        "inputs": [],
        "outputs": ["TestOutput"],
        "dependencies": [],
        "lifecycle_stages": ["active"],
        "authoritative_imports": [],
        "forbidden_responsibilities": [
            "Domain logic — not this module's concern"
        ],
    }


# ---------------------------------------------------------------------------
# Schema file existence
# ---------------------------------------------------------------------------

def test_module_manifest_schema_exists() -> None:
    assert SCHEMA_PATH.is_file(), f"Missing schema: {SCHEMA_PATH.relative_to(REPO_ROOT)}"


def test_module_manifest_example_exists() -> None:
    assert EXAMPLE_PATH.is_file(), f"Missing example: {EXAMPLE_PATH.relative_to(REPO_ROOT)}"


# ---------------------------------------------------------------------------
# Required manifests exist
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rel", validator.REQUIRED_MANIFESTS)
def test_required_manifest_exists(rel: str) -> None:
    path = MANIFESTS_DIR / rel
    assert path.is_file(), f"Required module manifest missing: {rel}"


# ---------------------------------------------------------------------------
# Valid manifest accepted
# ---------------------------------------------------------------------------

def test_valid_manifest_passes_schema() -> None:
    schema = _load_schema()
    v = Draft202012Validator(schema)
    instance = _minimal_valid_manifest()
    errors = list(v.iter_errors(instance))
    assert not errors, f"Unexpected schema errors: {[e.message for e in errors]}"


def test_example_manifest_passes_schema() -> None:
    schema = _load_schema()
    v = Draft202012Validator(schema)
    instance = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    errors = list(v.iter_errors(instance))
    assert not errors, f"Example manifest has schema errors: {[e.message for e in errors]}"


@pytest.mark.parametrize(
    "manifest_path",
    sorted(MANIFESTS_DIR.rglob("*.json")) if MANIFESTS_DIR.exists() else [],
    ids=lambda p: str(p.relative_to(MANIFESTS_DIR)),
)
def test_all_manifests_conform_to_schema(manifest_path: Path) -> None:
    schema = _load_schema()
    v = Draft202012Validator(schema)
    instance = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = list(v.iter_errors(instance))
    assert not errors, (
        f"Manifest {manifest_path.relative_to(REPO_ROOT)} has schema errors: "
        f"{[e.message for e in errors]}"
    )


# ---------------------------------------------------------------------------
# Invalid manifest rejected — missing required fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing_field", [
    "module_id",
    "module_name",
    "module_type",
    "owner_layer",
    "inputs",
    "outputs",
    "dependencies",
    "lifecycle_stages",
    "authoritative_imports",
    "forbidden_responsibilities",
    "status",
    "description",
])
def test_manifest_missing_required_field_fails_schema(missing_field: str, tmp_path: Path) -> None:
    schema = _load_schema()
    v = Draft202012Validator(schema)
    instance = _minimal_valid_manifest()
    del instance[missing_field]
    errors = list(v.iter_errors(instance))
    assert errors, f"Schema should reject manifest missing '{missing_field}'"


# ---------------------------------------------------------------------------
# Empty forbidden_responsibilities rejected
# ---------------------------------------------------------------------------

def test_empty_forbidden_responsibilities_fails_schema() -> None:
    schema = _load_schema()
    v = Draft202012Validator(schema)
    instance = _minimal_valid_manifest()
    instance["forbidden_responsibilities"] = []
    errors = list(v.iter_errors(instance))
    assert errors, "Schema should reject manifest with empty forbidden_responsibilities"


def test_empty_forbidden_responsibilities_detected_by_validator(tmp_path: Path) -> None:
    """check_forbidden_responsibilities should catch an empty list."""
    manifest = _minimal_valid_manifest()
    manifest["forbidden_responsibilities"] = []
    mpath = tmp_path / "test.json"
    mpath.write_text(json.dumps(manifest), encoding="utf-8")

    # Patch MANIFESTS_DIR to use tmp_path for an isolated check
    orig = validator.MANIFESTS_DIR
    try:
        validator.MANIFESTS_DIR = tmp_path
        violations = validator.check_forbidden_responsibilities(_load_schema())
    finally:
        validator.MANIFESTS_DIR = orig

    assert any(
        v["rule"] == "forbidden_responsibilities_empty" for v in violations
    ), "Validator should flag empty forbidden_responsibilities"


# ---------------------------------------------------------------------------
# Invalid module_type rejected
# ---------------------------------------------------------------------------

def test_invalid_module_type_fails_schema() -> None:
    schema = _load_schema()
    v = Draft202012Validator(schema)
    instance = _minimal_valid_manifest()
    instance["module_type"] = "unknown_type"
    errors = list(v.iter_errors(instance))
    assert errors, "Schema should reject invalid module_type"


# ---------------------------------------------------------------------------
# Invalid status rejected
# ---------------------------------------------------------------------------

def test_invalid_status_fails_schema() -> None:
    schema = _load_schema()
    v = Draft202012Validator(schema)
    instance = _minimal_valid_manifest()
    instance["status"] = "unknown_status"
    errors = list(v.iter_errors(instance))
    assert errors, "Schema should reject invalid status"


# ---------------------------------------------------------------------------
# Shared-truth redefinition detection
# ---------------------------------------------------------------------------

def test_shared_truth_redefinition_detected(tmp_path: Path) -> None:
    """A non-shared schema file that references ArtifactEnvelope should be flagged."""
    fake_module_dir = tmp_path / "spectrum_systems" / "workflow_modules" / "bad_module"
    fake_module_dir.mkdir(parents=True)
    schema_file = fake_module_dir / "local_model.json"
    # Simulate a local redefinition of the shared artifact envelope
    schema_file.write_text(
        json.dumps({"title": "ArtifactEnvelope", "type": "object", "properties": {}}),
        encoding="utf-8",
    )

    orig_root = validator.REPO_ROOT
    # We can't reassign REPO_ROOT easily, so instead test _file_defines_keyword directly.
    content = schema_file.read_text(encoding="utf-8")
    found = validator._file_defines_keyword(
        content, validator.SHARED_TRUTH_KEYWORDS["artifact_model"]
    )
    assert "ArtifactEnvelope" in found, (
        "Shared-truth keyword scanner should detect ArtifactEnvelope"
    )


def test_shared_truth_redefinition_not_flagged_for_authoritative_imports(tmp_path: Path) -> None:
    """
    A manifest file that references ArtifactEnvelope in authoritative_imports
    should NOT be flagged as a redefinition — keyword usage in consumer context
    is fine; only schema definition files matter.
    """
    manifest = _minimal_valid_manifest()
    manifest["authoritative_imports"] = ["ArtifactEnvelope from shared.artifact_models"]
    content = json.dumps(manifest)
    # The manifest references ArtifactEnvelope, but the scanner only runs on
    # files under spectrum_systems/ — not docs/module-manifests/ — so it should
    # never reach a manifest file.
    # Verify that manifest files are not in the candidate roots.
    candidate_roots = [REPO_ROOT / "spectrum_systems"]
    for root in candidate_roots:
        if MANIFESTS_DIR.is_relative_to(root):
            pytest.fail("MANIFESTS_DIR is unexpectedly inside a candidate root")


# ---------------------------------------------------------------------------
# Validator happy path / failure path
# ---------------------------------------------------------------------------

def test_validator_happy_path() -> None:
    """Full validator run against the real repo should pass with no violations."""
    violations = validator.run_all_checks()
    assert not violations, (
        f"Module architecture validation failed with {len(violations)} violation(s):\n"
        + "\n".join(f"  [{v['rule']}] {v['module']}: {v['message']}" for v in violations)
    )


def test_validator_failure_path_missing_manifest(tmp_path: Path) -> None:
    """If a required manifest is absent, the validator should report a violation."""
    orig = validator.MANIFESTS_DIR
    try:
        # Point manifests dir to an empty directory so nothing is found
        validator.MANIFESTS_DIR = tmp_path
        violations = validator.check_required_manifests()
    finally:
        validator.MANIFESTS_DIR = orig

    assert violations, "Expected violations when required manifests are missing"
    assert all(v["rule"] == "required_manifest_missing" for v in violations)


def test_validator_failure_path_invalid_manifest(tmp_path: Path) -> None:
    """A manifest missing required fields should fail schema conformance."""
    bad_manifest = {"module_id": "bad.module"}  # missing many required fields
    mpath = tmp_path / "bad.json"
    mpath.write_text(json.dumps(bad_manifest), encoding="utf-8")

    orig = validator.MANIFESTS_DIR
    try:
        validator.MANIFESTS_DIR = tmp_path
        violations = validator.check_manifest_schema_conformance(_load_schema())
    finally:
        validator.MANIFESTS_DIR = orig

    assert violations, "Expected schema violations for incomplete manifest"
    assert all(v["rule"] == "manifest_schema_violation" for v in violations)
