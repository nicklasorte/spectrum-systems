from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ROADMAP_STEP_CONTRACT = REPO_ROOT / "docs" / "roadmap" / "roadmap_step_contract.md"
SLICE_TEMPLATE = REPO_ROOT / "docs" / "roadmap" / "slices" / "_TEMPLATE.md"
SYSTEM_ROADMAP = REPO_ROOT / "docs" / "roadmap" / "system_roadmap.md"


def test_roadmap_step_contract_docs_exist() -> None:
    assert ROADMAP_STEP_CONTRACT.is_file(), "docs/roadmap/roadmap_step_contract.md is missing"
    assert SLICE_TEMPLATE.is_file(), "docs/roadmap/slices/_TEMPLATE.md is missing"


def test_system_roadmap_references_contract_standard() -> None:
    content = SYSTEM_ROADMAP.read_text(encoding="utf-8")
    assert "docs/roadmap/roadmap_step_contract.md" in content
    assert "docs/roadmap/slices/" in content
