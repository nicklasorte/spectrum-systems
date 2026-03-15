from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MATURITY_MODEL_PATH = REPO_ROOT / "docs" / "system-maturity-model.md"
README_PATH = REPO_ROOT / "README.md"


def test_maturity_model_doc_exists() -> None:
    assert MATURITY_MODEL_PATH.exists(), "system-maturity-model.md must exist"


def test_readme_references_maturity_model() -> None:
    content = README_PATH.read_text()
    assert "system-maturity-model.md" in content


def test_maturity_model_contains_level_markers() -> None:
    content = MATURITY_MODEL_PATH.read_text()
    for marker in ["Level 0", "Level 25"]:
        assert marker in content, f"'{marker}' missing from system maturity model document"
