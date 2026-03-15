from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OPERATING_MODEL_PATH = REPO_ROOT / "docs" / "spectrum-study-operating-model.md"
ECOSYSTEM_ARCH_PATH = REPO_ROOT / "docs" / "ecosystem-architecture.md"
README_PATH = REPO_ROOT / "README.md"


def test_operating_model_doc_exists() -> None:
    assert OPERATING_MODEL_PATH.exists(), "spectrum-study-operating-model.md must exist"


def test_ecosystem_architecture_references_operating_model() -> None:
    content = ECOSYSTEM_ARCH_PATH.read_text()
    assert "spectrum-study-operating-model.md" in content


def test_readme_references_operating_model() -> None:
    content = README_PATH.read_text()
    assert "spectrum-study-operating-model.md" in content


def test_operating_model_keywords_present() -> None:
    content = OPERATING_MODEL_PATH.read_text()
    for phrase in [
        "Coordination Loop",
        "Document Production Loop",
        "Engineering Tasks",
        "Engineering Outputs",
    ]:
        assert phrase in content, f"'{phrase}' missing from operating model document"
