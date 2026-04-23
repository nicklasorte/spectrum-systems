from __future__ import annotations

from pathlib import Path

from scripts import validate_system_registry as validator


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "docs" / "architecture" / "system_registry.md"


def _base_registry() -> str:
    return """# System Registry (Canonical)
## Active executable systems
### AEX
- **Status:** active
- **Purpose:** admission
- **Failure Prevented:** bad intake
- **Signal Improved:** admission clarity
- **Canonical Artifacts Owned:** `a`
- **Primary Code Paths:** `scripts/validate_system_registry.py`
## Merged or demoted systems
| System | Status | Merged/Demoted Into | Rationale |
| --- | --- | --- | --- |
## Future / placeholder systems
| System | Status | Rationale |
| --- | --- | --- |
## Artifact families and supporting capabilities (non-authority)
"""


def test_live_registry_passes() -> None:
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    errors = validator.validate_registry(text)
    assert not errors, f"Expected no errors, got: {errors}"


def test_duplicate_acronym_detection() -> None:
    text = _base_registry().replace(
        "## Merged or demoted systems",
        "### AEX\n- **Status:** active\n- **Purpose:** x\n- **Failure Prevented:** y\n"
        "- **Signal Improved:** z\n- **Canonical Artifacts Owned:** `a`\n"
        "- **Primary Code Paths:** `scripts/validate_system_registry.py`\n## Merged or demoted systems",
    )
    errors = validator.validate_registry(text)
    assert any("Duplicate active acronym: AEX" in e for e in errors)


def test_missing_metadata_detection() -> None:
    text = _base_registry().replace("- **Purpose:** admission\n", "")
    errors = validator.validate_registry(text)
    assert any("AEX missing required fields" in e for e in errors)


def test_missing_code_path_detection() -> None:
    text = _base_registry().replace(
        "`scripts/validate_system_registry.py`", "`scripts/does_not_exist.py`"
    )
    errors = validator.validate_registry(text)
    assert any("path does not exist" in e for e in errors)


def test_placeholder_vs_runtime_contradiction_detection() -> None:
    text = _base_registry().replace(
        "| --- | --- | --- |\n",
        "| --- | --- | --- |\n| PQX | future | test contradiction |\n",
    )
    errors = validator.validate_registry(text)
    assert any("PQX is marked future but has runtime implementation evidence" in e for e in errors)


def test_runtime_drift_detection() -> None:
    text = _base_registry()
    errors = validator.validate_registry(text)
    assert any(e.startswith("Runtime drift: PQX") for e in errors)
