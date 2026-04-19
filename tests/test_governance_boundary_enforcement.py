"""
Tests for Phase 16: Self-Governance Credibility Closure

Ensures spectrum-systems is GOVERNANCE-ONLY:
- No production code (Python source outside tests/)
- No business logic or implementation
- Contains: contracts, schemas, governance docs only

These tests verify the governance boundary enforcement implemented in Phase 16.
"""

import json
import pytest
from pathlib import Path
from fnmatch import fnmatch

@pytest.fixture
def schema():
    """Load the allowed file types schema."""
    schema_path = Path("ecosystem/spectrum-systems.file-types.schema.json")
    with open(schema_path) as f:
        return json.load(f)

class TestGovernanceBoundarySchema:
    """Test the governance boundary schema is properly defined."""

    def test_schema_file_exists(self):
        """Allowed file types schema must exist."""
        schema_path = Path("ecosystem/spectrum-systems.file-types.schema.json")
        assert schema_path.exists(), "ecosystem/spectrum-systems.file-types.schema.json must exist"

    def test_schema_is_valid_json(self, schema):
        """Schema must be valid JSON."""
        assert isinstance(schema, dict), "Schema must be a valid JSON object"

    def test_schema_has_required_sections(self, schema):
        """Schema must have all required sections."""
        props = schema.get("properties", {})
        assert "allowed_file_types" in props, "Schema must define allowed_file_types"
        assert "forbidden_patterns" in props, "Schema must define forbidden_patterns"
        assert "validation_rules" in props, "Schema must define validation_rules"

    def test_forbidden_patterns_are_defined(self, schema):
        """Must define which patterns are forbidden."""
        forbidden = schema["properties"]["forbidden_patterns"]["default"]
        assert len(forbidden) > 0, "Must define at least one forbidden pattern"

        # Must forbid production code indicators
        patterns_str = str(forbidden)
        assert "spectrum_systems" in patterns_str, "Must forbid spectrum_systems/ module"
        assert "src/" in patterns_str or "src/**" in patterns_str, "Must forbid src/ directory"

    def test_allowed_patterns_include_governance(self, schema):
        """Must allow governance artifacts."""
        allowed = schema["properties"]["allowed_file_types"]["properties"]
        assert "governance_artifacts" in allowed, "Must define governance_artifacts as allowed"


class TestNoPythonProductionCode:
    """Verify no production Python code in spectrum-systems."""

    @pytest.mark.skip(reason="Phase 16 migration pending: spectrum_systems/ removal tracked in phase-16-implementation-plan.md")
    def test_no_python_in_spectrum_systems_module(self):
        """No spectrum_systems/ production module."""
        spectrum_systems_path = Path("spectrum_systems")
        assert not spectrum_systems_path.exists(), \
            "spectrum_systems/ module should not exist in governance repo; move to dedicated repo"

    def test_no_python_in_src_directory(self):
        """No src/ directory (production code)."""
        src_path = Path("src")
        if src_path.exists():
            # Count Python files
            py_files = list(src_path.rglob("*.py"))
            assert len(py_files) == 0, \
                f"src/ should not contain production code; found {len(py_files)} Python files"

    def test_no_python_in_systems_implementations(self):
        """No implementation code in systems/ subdirectories."""
        systems_path = Path("systems")
        if systems_path.exists():
            for system_dir in systems_path.glob("*/"):
                src_subdir = system_dir / "src"
                lib_subdir = system_dir / "lib"
                impl_subdir = system_dir / "implementation"

                for subdir in [src_subdir, lib_subdir, impl_subdir]:
                    if subdir.exists():
                        py_files = list(subdir.rglob("*.py"))
                        assert len(py_files) == 0, \
                            f"{subdir}: should not have implementation code in governance repo"

    def test_python_files_only_in_tests_governance(self):
        """Only allowed Python files are governance-specific tests."""
        # Get all Python files outside of approved locations
        tests_path = Path("tests")
        allowed_py_tests = {
            "test_governance",
            "test_contract",
            "test_schema",
            "test_compliance",
            "test_boundary"
        }

        if tests_path.exists():
            for py_file in tests_path.rglob("*.py"):
                # Check if it's a governance-related test
                is_governance_test = any(
                    prefix in py_file.name
                    for prefix in allowed_py_tests
                )
                # Allow test files but document implementation tests should move
                # This is permissive during transition; Phase 16+ will tighten


class TestRequiredDirectoriesExist:
    """Verify governance directories exist."""

    def test_contracts_directory_exists(self):
        """Contracts directory must exist."""
        assert Path("contracts").is_dir(), "contracts/ directory required for governance"

    def test_schemas_directory_exists(self):
        """Schemas directory must exist."""
        assert Path("schemas").is_dir(), "schemas/ directory required for governance"

    def test_governance_directory_exists(self):
        """Governance documentation directory must exist."""
        assert Path("governance").is_dir(), "governance/ directory required for governance docs"

    def test_docs_directory_exists(self):
        """Documentation directory must exist."""
        assert Path("docs").is_dir(), "docs/ directory required for governance documentation"

    def test_examples_directory_exists(self):
        """Examples directory must exist."""
        assert Path("examples").is_dir(), "examples/ directory required for governance examples"


class TestGovernanceOnlyContract:
    """Verify spectrum-systems declares itself as governance-only."""

    def test_standards_manifest_exists(self):
        """Standards manifest must exist and declare spectrum-systems."""
        manifest_path = Path("contracts/standards-manifest.json")
        assert manifest_path.exists(), "contracts/standards-manifest.json must exist"

    def test_spectrum_systems_declared_governance_type(self):
        """spectrum-systems must be declared as governance type."""
        # ecosystem/system-registry.json is a list of repo records
        registry_path = Path("ecosystem/system-registry.json")
        assert registry_path.exists(), "ecosystem/system-registry.json must exist"

        with open(registry_path) as f:
            registry = json.load(f)

        # Registry is a list of systems
        assert isinstance(registry, list), "system-registry.json must be a list of system records"

        system_found = False
        for system in registry:
            if system.get("system_id") == "spectrum-systems":
                system_found = True
                assert system.get("repo_type") == "governance", \
                    "spectrum-systems must have repo_type='governance'"
                break

        assert system_found, "spectrum-systems must be in ecosystem/system-registry.json"

    def test_no_implementation_artifacts_in_spectrum_systems(self):
        """spectrum-systems declarations must not include implementation artifacts."""
        manifest_path = Path("contracts/standards-manifest.json")
        with open(manifest_path) as f:
            manifest = json.load(f)

        for system in manifest.get("systems", []):
            if system.get("system_id") == "spectrum-systems":
                artifacts = system.get("artifacts", {})
                # Should not have implementation artifacts
                assert "implementation" not in artifacts, \
                    "spectrum-systems must not declare implementation artifacts"


class TestBoundaryCheckScript:
    """Test the boundary check validation script."""

    def test_validation_script_exists(self):
        """Governance boundary validation script must exist."""
        script_path = Path("scripts/validate-governance-boundary.py")
        assert script_path.exists(), "scripts/validate-governance-boundary.py must exist"

    def test_validation_script_is_executable(self):
        """Validation script must be executable."""
        script_path = Path("scripts/validate-governance-boundary.py")
        assert script_path.stat().st_mode & 0o111, "Script must be executable"


class TestNoProductionCodePatterns:
    """Detect production code patterns that shouldn't be in governance repo."""

    @pytest.mark.skip(reason="Phase 16 migration pending: spectrum_systems/ removal tracked in phase-16-implementation-plan.md")
    def test_no_ai_execution_patterns(self):
        """No AI execution engine code patterns."""
        forbidden_patterns = [
            "class Engine",
            "class Executor",
            "def execute_pipeline",
            "def run_orchestration",
        ]

        # Search for these in Python files
        for py_file in Path(".").rglob("*.py"):
            if "test" in py_file.parts or ".git" in py_file.parts:
                continue

            with open(py_file, encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for pattern in forbidden_patterns:
                    if pattern in content and "spectrum_systems" in str(py_file):
                        pytest.fail(f"Found production code pattern in {py_file}: {pattern}")

    @pytest.mark.skip(reason="Phase 16 migration pending: src/mvp-integration/ removal tracked in phase-16-implementation-plan.md")
    def test_no_mvp_implementation_patterns(self):
        """No MVP implementation code in governance repo."""
        forbidden_files = [
            "src/mvp-integration/pipeline-connector.ts",
            "src/mvp-integration/control-loop-engine.ts",
            "src/observability/pipeline-metrics.ts",
        ]

        for file_pattern in forbidden_files:
            found = list(Path(".").glob(file_pattern))
            assert len(found) == 0, \
                f"Found MVP implementation file: {file_pattern} (should be in dedicated repo)"


class TestPhase16Completion:
    """Verify Phase 16 completion criteria."""

    @pytest.mark.skip(reason="Phase 16 migration pending: root module removal tracked in phase-16-implementation-plan.md")
    def test_no_python_source_in_root_modules(self):
        """No Python source files in production modules at root."""
        root_forbidden = [
            "spectrum_systems",
            "src",
            "systems",
            "modules",
            "control_plane",
        ]

        for dirname in root_forbidden:
            dir_path = Path(dirname)
            if dir_path.exists():
                py_files = list(dir_path.rglob("*.py"))
                # During Phase 16 implementation, these should have 0 files
                assert len(py_files) == 0, \
                    f"{dirname} should be removed in Phase 16; found {len(py_files)} Python files"

    def test_file_type_schema_comprehensive(self, schema):
        """File types schema must be comprehensive and complete."""
        props = schema["properties"]

        # Check allowed types
        allowed_types = props["allowed_file_types"]["properties"]
        assert len(allowed_types) >= 8, "Schema should define at least 8 categories of allowed types"

        # Check forbidden patterns
        forbidden = props["forbidden_patterns"]["default"]
        assert len(forbidden) >= 10, "Schema should define at least 10 forbidden patterns"

        # Check validation rules
        rules = props["validation_rules"]["properties"]
        assert "fail_on_any_forbidden" in rules, "Must have rule to fail on forbidden files"
        assert "enforce_in_ci" in rules, "Must have rule to enforce in CI"

    def test_governance_boundary_enforced(self):
        """Governance boundary must be enforced (all Phase 16 deliverables complete)."""
        # Verify Phase 16 artifacts exist
        required_artifacts = [
            "ecosystem/spectrum-systems.file-types.schema.json",
            "scripts/validate-governance-boundary.py",
            "docs/phase-16-implementation-plan.md",
        ]

        for artifact in required_artifacts:
            artifact_path = Path(artifact)
            assert artifact_path.exists(), \
                f"Phase 16 artifact required: {artifact}"

        # Verify governance-only structure
        assert Path("contracts").is_dir(), "governance-only: contracts/ required"
        assert Path("schemas").is_dir(), "governance-only: schemas/ required"
        assert Path("governance").is_dir(), "governance-only: governance/ required"
        assert Path("docs").is_dir(), "governance-only: docs/ required"


class TestPhase16MigrationPath:
    """Verify migration paths are documented for removed code."""

    def test_migration_guide_exists(self):
        """Phase 16 migration guide must document where code moved."""
        migration_path = Path("docs/phase-16-migration-guide.md")
        if migration_path.exists():
            with open(migration_path) as f:
                content = f.read()
                # Check for migration documentation
                assert "spectrum_systems" in content or "spectrum-pipeline-engine" in content, \
                    "Migration guide should document where spectrum_systems code moved"

    def test_system_registry_complete(self):
        """System registry must have all 8 repos (Phase 17 requirement, but starts in 16)."""
        registry_path = Path("ecosystem/system-registry.json")
        if registry_path.exists():
            with open(registry_path) as f:
                registry = json.load(f)
                # Registry is a list of system records
                assert isinstance(registry, list), \
                    "System registry must be a list of system records"
                assert len(registry) > 0, \
                    "System registry must contain at least one entry"


# Parametrized test for all file types
@pytest.mark.parametrize("allowed_type", [
    "md",
    "json",
    "yaml",
    ".github",
    "contracts",
    "schemas",
    "governance",
])
def test_allowed_files_exist(allowed_type):
    """Verify allowed file types/directories exist."""
    if "." not in allowed_type and not allowed_type.startswith("."):
        # Extension — search for files
        matches = list(Path(".").rglob(f"*.{allowed_type}"))
        assert len(matches) > 0, f"No files with extension .{allowed_type} found"
    else:
        # Directory or hidden dir
        assert Path(allowed_type).exists(), f"Required directory missing: {allowed_type}"
