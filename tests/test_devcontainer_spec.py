from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEVCONTAINER_DIR = REPO_ROOT / "devcontainer-spec"


def test_devcontainer_directory_exists() -> None:
    assert DEVCONTAINER_DIR.is_dir(), "Missing devcontainer-spec directory"


def test_devcontainer_files_exist() -> None:
    required_files = [
        DEVCONTAINER_DIR / "devcontainer.json",
        DEVCONTAINER_DIR / "Dockerfile",
        DEVCONTAINER_DIR / "requirements-base.txt",
    ]
    missing = [f for f in required_files if not f.is_file()]
    assert not missing, f"Missing devcontainer spec files: {[str(m.relative_to(REPO_ROOT)) for m in missing]}"
