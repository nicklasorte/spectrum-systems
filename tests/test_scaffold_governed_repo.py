"""
Tests for scripts/scaffold_governed_repo.py

Verifies that the governed scaffolding:
- produces all required files
- generates valid .spectrum-governance.json (conforms to governance schema)
- generates governance-declaration.json with all required fields
- pins contracts to versions that match contracts/standards-manifest.json
- varies output correctly by repo type
- is deterministic for a given set of inputs
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


from scripts import scaffold_governed_repo as scaffolder

REPO_ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "spectrum-governance.schema.json"
STANDARDS_MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"

# Required top-level fields in a governance declaration
DECLARATION_REQUIRED_FIELDS = [
    "governance_declaration_version",
    "architecture_source",
    "standards_manifest_version",
    "system_id",
    "implementation_repo",
    "declared_at",
    "contract_pins",
    "schema_pins",
    "evaluation_manifest_path",
    "external_storage_policy",
]

# All repo types that must be supported
ALL_REPO_TYPES = ["governance", "factory", "operational_engine", "advisory", "pipeline"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scaffold(tmp_path: Path, repo_type: str = "operational_engine", **kwargs) -> dict:
    """Run the scaffold helper and return the summary dict."""
    return scaffolder.scaffold_governed_repo(
        repo_name=kwargs.get("repo_name", "test-engine"),
        repo_type=repo_type,
        system_id=kwargs.get("system_id", "test-engine"),
        owner=kwargs.get("owner", "nicklasorte"),
        output_dir=tmp_path / kwargs.get("repo_name", "test-engine"),
        declared_at="2026-01-01",
    )


# ---------------------------------------------------------------------------
# File presence tests
# ---------------------------------------------------------------------------


def test_governance_manifest_is_generated(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    assert (tmp_path / "test-engine" / ".spectrum-governance.json").is_file()


def test_governance_declaration_is_generated(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    assert (
        tmp_path / "test-engine" / "governance" / "governance-declaration.json"
    ).is_file()


def test_ci_workflow_is_generated(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    assert (
        tmp_path / "test-engine" / ".github" / "workflows" / "validate-governance.yml"
    ).is_file()


def test_readme_is_generated(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    assert (tmp_path / "test-engine" / "README.md").is_file()


def test_registry_entry_is_generated(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    assert (tmp_path / "test-engine" / "registry-entry.json").is_file()


def test_summary_lists_all_written_files(tmp_path: Path) -> None:
    summary = _scaffold(tmp_path)
    expected = {
        ".spectrum-governance.json",
        "governance/governance-declaration.json",
        ".github/workflows/validate-governance.yml",
        "README.md",
        "registry-entry.json",
    }
    assert set(summary["files_written"]) == expected


# ---------------------------------------------------------------------------
# .spectrum-governance.json content tests
# ---------------------------------------------------------------------------


def test_governance_manifest_conforms_to_schema(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    schema = json.loads(GOVERNANCE_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    manifest = json.loads(
        (tmp_path / "test-engine" / ".spectrum-governance.json").read_text(encoding="utf-8")
    )
    errors = list(validator.iter_errors(manifest))
    assert not errors, f"Schema violations: {[e.message for e in errors]}"


def test_governance_manifest_repo_type_matches_input(tmp_path: Path) -> None:
    _scaffold(tmp_path, repo_type="advisory")
    manifest = json.loads(
        (tmp_path / "test-engine" / ".spectrum-governance.json").read_text(encoding="utf-8")
    )
    assert manifest["repo_type"] == "advisory"


def test_governance_manifest_repo_name_matches_input(tmp_path: Path) -> None:
    _scaffold(tmp_path, repo_name="custom-repo")
    manifest = json.loads(
        (tmp_path / "custom-repo" / ".spectrum-governance.json").read_text(encoding="utf-8")
    )
    assert manifest["repo_name"] == "custom-repo"


def test_governance_manifest_governance_repo_is_spectrum_systems(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    manifest = json.loads(
        (tmp_path / "test-engine" / ".spectrum-governance.json").read_text(encoding="utf-8")
    )
    assert manifest["governance_repo"] == "spectrum-systems"


# ---------------------------------------------------------------------------
# Contract pinning tests
# ---------------------------------------------------------------------------


def test_contract_pins_versions_match_standards_manifest(tmp_path: Path) -> None:
    """All pinned versions must exactly match contracts/standards-manifest.json."""
    standards = json.loads(STANDARDS_MANIFEST_PATH.read_text(encoding="utf-8"))
    expected_versions = {
        c["artifact_type"]: c["schema_version"] for c in standards.get("contracts", [])
    }

    _scaffold(tmp_path, repo_type="factory")
    manifest = json.loads(
        (tmp_path / "test-engine" / ".spectrum-governance.json").read_text(encoding="utf-8")
    )
    for contract_name, pinned_version in manifest["contracts"].items():
        assert contract_name in expected_versions, (
            f"Contract '{contract_name}' not found in standards manifest"
        )
        assert pinned_version == expected_versions[contract_name], (
            f"Contract '{contract_name}' pinned to '{pinned_version}' "
            f"but standards manifest declares '{expected_versions[contract_name]}'"
        )


def test_operational_engine_has_provenance_contract(tmp_path: Path) -> None:
    _scaffold(tmp_path, repo_type="operational_engine")
    manifest = json.loads(
        (tmp_path / "test-engine" / ".spectrum-governance.json").read_text(encoding="utf-8")
    )
    assert "provenance_record" in manifest["contracts"]


def test_pipeline_type_has_expected_contracts(tmp_path: Path) -> None:
    _scaffold(tmp_path, repo_type="pipeline")
    manifest = json.loads(
        (tmp_path / "test-engine" / ".spectrum-governance.json").read_text(encoding="utf-8")
    )
    pipeline_contracts = manifest["contracts"]
    # Pipeline should include orchestration contracts
    assert "meeting_agenda_contract" in pipeline_contracts
    assert "provenance_record" in pipeline_contracts
    assert "study_readiness_assessment" in pipeline_contracts


def test_advisory_type_has_expected_contracts(tmp_path: Path) -> None:
    _scaffold(tmp_path, repo_type="advisory")
    manifest = json.loads(
        (tmp_path / "test-engine" / ".spectrum-governance.json").read_text(encoding="utf-8")
    )
    advisory_contracts = manifest["contracts"]
    assert "program_brief" in advisory_contracts
    assert "risk_register" in advisory_contracts
    assert "decision_log" in advisory_contracts


def test_factory_type_has_all_common_contracts(tmp_path: Path) -> None:
    _scaffold(tmp_path, repo_type="factory")
    manifest = json.loads(
        (tmp_path / "test-engine" / ".spectrum-governance.json").read_text(encoding="utf-8")
    )
    factory_contracts = manifest["contracts"]
    # Factory should include a broad set of contracts
    assert "standards_manifest" in factory_contracts
    assert "provenance_record" in factory_contracts
    assert "working_paper_input" in factory_contracts
    assert len(factory_contracts) >= 10


def test_governance_type_has_standards_manifest_contract(tmp_path: Path) -> None:
    _scaffold(tmp_path, repo_type="governance")
    manifest = json.loads(
        (tmp_path / "test-engine" / ".spectrum-governance.json").read_text(encoding="utf-8")
    )
    assert "standards_manifest" in manifest["contracts"]


# ---------------------------------------------------------------------------
# Governance declaration tests
# ---------------------------------------------------------------------------


def test_governance_declaration_has_required_fields(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    decl = json.loads(
        (
            tmp_path / "test-engine" / "governance" / "governance-declaration.json"
        ).read_text(encoding="utf-8")
    )
    for field in DECLARATION_REQUIRED_FIELDS:
        assert field in decl, f"Missing required field '{field}' in governance-declaration.json"


def test_governance_declaration_architecture_source(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    decl = json.loads(
        (
            tmp_path / "test-engine" / "governance" / "governance-declaration.json"
        ).read_text(encoding="utf-8")
    )
    assert decl["architecture_source"] == "nicklasorte/spectrum-systems"


def test_governance_declaration_implementation_repo(tmp_path: Path) -> None:
    _scaffold(tmp_path, owner="myorg", repo_name="my-engine")
    decl = json.loads(
        (
            tmp_path / "my-engine" / "governance" / "governance-declaration.json"
        ).read_text(encoding="utf-8")
    )
    assert decl["implementation_repo"] == "myorg/my-engine"


def test_governance_declaration_system_id(tmp_path: Path) -> None:
    _scaffold(tmp_path, system_id="my-engine", repo_name="my-engine")
    decl = json.loads(
        (
            tmp_path / "my-engine" / "governance" / "governance-declaration.json"
        ).read_text(encoding="utf-8")
    )
    assert decl["system_id"] == "my-engine"


def test_governance_declaration_contract_pins_match_manifest(tmp_path: Path) -> None:
    """contract_pins in the declaration must match .spectrum-governance.json contracts."""
    _scaffold(tmp_path)
    manifest = json.loads(
        (tmp_path / "test-engine" / ".spectrum-governance.json").read_text(encoding="utf-8")
    )
    decl = json.loads(
        (
            tmp_path / "test-engine" / "governance" / "governance-declaration.json"
        ).read_text(encoding="utf-8")
    )
    assert decl["contract_pins"] == manifest["contracts"], (
        "contract_pins in governance-declaration.json must match contracts in "
        ".spectrum-governance.json"
    )


def test_governance_declaration_has_schema_pins(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    decl = json.loads(
        (
            tmp_path / "test-engine" / "governance" / "governance-declaration.json"
        ).read_text(encoding="utf-8")
    )
    assert isinstance(decl["schema_pins"], dict)


def test_governance_declaration_standards_manifest_version(tmp_path: Path) -> None:
    """standards_manifest_version must match the version in contracts/standards-manifest.json."""
    standards = json.loads(STANDARDS_MANIFEST_PATH.read_text(encoding="utf-8"))
    expected_version = standards.get("standards_version", "")
    _scaffold(tmp_path)
    decl = json.loads(
        (
            tmp_path / "test-engine" / "governance" / "governance-declaration.json"
        ).read_text(encoding="utf-8")
    )
    assert decl["standards_manifest_version"] == expected_version


# ---------------------------------------------------------------------------
# Registry entry tests
# ---------------------------------------------------------------------------


def test_registry_entry_has_required_fields(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    entry = json.loads(
        (tmp_path / "test-engine" / "registry-entry.json").read_text(encoding="utf-8")
    )
    for field in ("repo_name", "repo_url", "repo_type", "layer", "system_id", "contracts"):
        assert field in entry, f"Missing required field '{field}' in registry-entry.json"


def test_registry_entry_repo_url_structure(tmp_path: Path) -> None:
    _scaffold(tmp_path, owner="myorg", repo_name="my-engine")
    entry = json.loads(
        (tmp_path / "my-engine" / "registry-entry.json").read_text(encoding="utf-8")
    )
    assert entry["repo_url"] == "https://github.com/myorg/my-engine"


def test_registry_entry_layer_matches_repo_type(tmp_path: Path) -> None:
    expected_layers = {
        "governance": "Layer 2",
        "factory": "Layer 1",
        "operational_engine": "Layer 3",
        "pipeline": "Layer 4",
        "advisory": "Layer 5",
    }
    for repo_type, expected_layer in expected_layers.items():
        _scaffold(tmp_path, repo_type=repo_type)
        entry = json.loads(
            (tmp_path / "test-engine" / "registry-entry.json").read_text(encoding="utf-8")
        )
        assert entry["layer"] == expected_layer, (
            f"repo_type '{repo_type}' should yield layer '{expected_layer}', "
            f"got '{entry['layer']}'"
        )


# ---------------------------------------------------------------------------
# Repo-type variation tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_type", ALL_REPO_TYPES)
def test_all_repo_types_scaffold_successfully(tmp_path: Path, repo_type: str) -> None:
    """Every supported repo_type must produce all required output files."""
    out = tmp_path / repo_type
    scaffolder.scaffold_governed_repo(
        repo_name="scaffold-test",
        repo_type=repo_type,
        system_id="scaffold-test",
        owner="nicklasorte",
        output_dir=out,
        declared_at="2026-01-01",
    )
    assert (out / ".spectrum-governance.json").is_file()
    assert (out / "governance" / "governance-declaration.json").is_file()
    assert (out / ".github" / "workflows" / "validate-governance.yml").is_file()
    assert (out / "README.md").is_file()
    assert (out / "registry-entry.json").is_file()


@pytest.mark.parametrize("repo_type", ALL_REPO_TYPES)
def test_all_repo_types_produce_valid_governance_manifest(
    tmp_path: Path, repo_type: str
) -> None:
    """Every repo_type must produce a .spectrum-governance.json conforming to the schema."""
    schema = json.loads(GOVERNANCE_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    out = tmp_path / repo_type
    scaffolder.scaffold_governed_repo(
        repo_name="scaffold-test",
        repo_type=repo_type,
        system_id="scaffold-test",
        owner="nicklasorte",
        output_dir=out,
        declared_at="2026-01-01",
    )
    manifest = json.loads((out / ".spectrum-governance.json").read_text(encoding="utf-8"))
    errors = list(validator.iter_errors(manifest))
    assert not errors, (
        f"repo_type '{repo_type}' produced invalid manifest: "
        f"{[e.message for e in errors]}"
    )


# ---------------------------------------------------------------------------
# Determinism test
# ---------------------------------------------------------------------------


def test_scaffold_output_is_deterministic(tmp_path: Path) -> None:
    """Running the scaffold twice with the same inputs must produce identical output."""
    kwargs = dict(
        repo_name="det-engine",
        repo_type="operational_engine",
        system_id="det-engine",
        owner="nicklasorte",
        declared_at="2026-01-01",
    )
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"

    scaffolder.scaffold_governed_repo(output_dir=out1, **kwargs)
    scaffolder.scaffold_governed_repo(output_dir=out2, **kwargs)

    for rel in [
        ".spectrum-governance.json",
        "governance/governance-declaration.json",
        "README.md",
        "registry-entry.json",
    ]:
        content1 = (out1 / rel).read_text(encoding="utf-8")
        content2 = (out2 / rel).read_text(encoding="utf-8")
        assert content1 == content2, f"Non-deterministic output in {rel}"


# ---------------------------------------------------------------------------
# Invalid input tests
# ---------------------------------------------------------------------------


def test_invalid_repo_type_raises_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Invalid repo_type"):
        scaffolder.scaffold_governed_repo(
            repo_name="bad-repo",
            repo_type="invalid_type",
            system_id="bad-repo",
            owner="nicklasorte",
            output_dir=tmp_path / "bad-repo",
            declared_at="2026-01-01",
        )
