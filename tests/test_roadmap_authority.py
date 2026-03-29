from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_ROADMAP = REPO_ROOT / "docs" / "roadmaps" / "system_roadmap.md"
LEGACY_ROADMAP = REPO_ROOT / "docs" / "roadmap" / "system_roadmap.md"
ROADMAP_AUTHORITY = REPO_ROOT / "docs" / "roadmaps" / "roadmap_authority.md"
README = REPO_ROOT / "docs" / "roadmap" / "README.md"


def _authority_docs() -> list[Path]:
    docs: set[Path] = {
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "CODEX.md",
        REPO_ROOT / "docs" / "roadmap.md",
    }
    docs.update((REPO_ROOT / "docs" / "roadmap").rglob("*.md"))
    docs.update((REPO_ROOT / "docs" / "roadmaps").rglob("*.md"))
    return sorted(p for p in docs if p.is_file())


def test_system_roadmap_exists() -> None:
    assert SYSTEM_ROADMAP.is_file(), "docs/roadmaps/system_roadmap.md must exist"


def test_readme_points_to_authority() -> None:
    text = README.read_text(encoding="utf-8")
    assert "Active roadmap authority is `docs/roadmaps/system_roadmap.md`" in text


def test_authority_bridge_declares_active_and_legacy_paths() -> None:
    text = ROADMAP_AUTHORITY.read_text(encoding="utf-8")
    assert "**Active editorial authority:** `docs/roadmaps/system_roadmap.md`" in text
    assert "**Operational compatibility mirror (required until migration complete):** `docs/roadmap/system_roadmap.md`" in text


def test_active_and_legacy_roadmap_cross_reference_bridge() -> None:
    active_text = SYSTEM_ROADMAP.read_text(encoding="utf-8")
    assert "Compatibility transition rule: `docs/roadmap/system_roadmap.md` is a required parseable operational mirror" in active_text

    legacy_text = LEGACY_ROADMAP.read_text(encoding="utf-8")
    assert "Active editorial roadmap authority: `docs/roadmaps/system_roadmap.md`" in legacy_text


def test_no_conflicting_authority_language() -> None:
    conflict_tokens = ("primary roadmap", "sole active roadmap", "active roadmap is")
    for path in _authority_docs():
        if path == SYSTEM_ROADMAP:
            continue
        text = path.read_text(encoding="utf-8").lower()
        assert "single authoritative roadmap" not in text, f"conflicting authority claim in {path}"
        for token in conflict_tokens:
            assert token not in text, f"conflicting authority token '{token}' in {path}"
