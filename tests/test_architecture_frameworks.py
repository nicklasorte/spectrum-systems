from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HORIZONS_PATH = REPO_ROOT / "docs" / "architecture-horizons.md"
INFLECTIONS_PATH = REPO_ROOT / "docs" / "platform-inflection-points.md"
CLAUDE_PROTOCOL_PATH = REPO_ROOT / "CLAUDE_REVIEW_PROTOCOL.md"
PLAYBOOK_PATH = REPO_ROOT / "docs" / "level-0-to-20-playbook.md"


def test_horizons_doc_exists() -> None:
    assert HORIZONS_PATH.exists(), "Three Horizons architecture model must be documented"


def test_inflections_doc_exists() -> None:
    assert INFLECTIONS_PATH.exists(), "Platform inflection points must be documented"


def test_claude_protocol_references_frameworks() -> None:
    content = CLAUDE_PROTOCOL_PATH.read_text()
    assert "architecture-horizons.md" in content
    assert "platform-inflection-points.md" in content


def test_playbook_references_inflection_points() -> None:
    content = PLAYBOOK_PATH.read_text()
    assert "platform-inflection-points" in content.lower()
