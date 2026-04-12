"""Regression checks for dashboard null-safe render gate and route strategy."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PAGE_PATH = REPO_ROOT / "dashboard" / "app" / "page.tsx"
COMPONENT_PATH = REPO_ROOT / "dashboard" / "components" / "RepoDashboard.tsx"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_page_uses_explicit_dynamic_render_strategy() -> None:
    page = _read(PAGE_PATH)
    assert "export const dynamic = 'force-dynamic'" in page


def test_component_declares_discriminated_render_gate_states() -> None:
    content = _read(COMPONENT_PATH)
    for token in ["'renderable'", "'no_data'", "'incomplete_publication'", "'stale'", "'truth_violation'"]:
        assert token in content


def test_runtime_hotspots_are_not_read_in_repo_dashboard() -> None:
    content = _read(COMPONENT_PATH)
    assert "runtime_hotspots" not in content
