from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_SCHEMAS = [
    REPO_ROOT / "design-reviews" / "claude-review.schema.json",
    REPO_ROOT / "ecosystem" / "ecosystem-registry.schema.json",
    REPO_ROOT / "governance" / "compliance-scans" / "compliance-report.schema.json",
    REPO_ROOT / "governance" / "repo-compliance.schema.json",
]

OPTIONAL_SCHEMAS = [
    REPO_ROOT / "contracts" / "comment-resolution-matrix.schema.json",
]


@pytest.mark.parametrize("schema_path", REQUIRED_SCHEMAS)
def test_required_schema_files_exist(schema_path: Path) -> None:
    assert schema_path.is_file(), f"Missing required schema: {schema_path.relative_to(REPO_ROOT)}"


@pytest.mark.parametrize("schema_path", OPTIONAL_SCHEMAS)
def test_optional_schema_present_when_expected(schema_path: Path) -> None:
    if not schema_path.exists():
        pytest.skip(f"Optional schema absent: {schema_path.relative_to(REPO_ROOT)}")
    assert schema_path.is_file()
