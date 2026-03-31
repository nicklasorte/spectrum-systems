#!/usr/bin/env python3
"""Fail-closed roadmap authority checker."""
from __future__ import annotations

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_ROADMAP = Path("docs/roadmaps/system_roadmap.md")
LEGACY_ROADMAP = Path("docs/roadmap/system_roadmap.md")
AUTHORITY_BRIDGE = Path("docs/roadmaps/roadmap_authority.md")

CONFLICT_PATTERNS = (
    re.compile(r"\bprimary roadmap\b", re.IGNORECASE),
    re.compile(r"\bsole active roadmap\b", re.IGNORECASE),
    re.compile(r"\bactive roadmap is\b", re.IGNORECASE),
    re.compile(r"\bsingle authoritative roadmap\b", re.IGNORECASE),
)


def iter_authority_docs() -> list[Path]:
    docs: set[Path] = {
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "CODEX.md",
        REPO_ROOT / "docs" / "roadmap.md",
    }
    docs.update((REPO_ROOT / "docs" / "roadmap").rglob("*.md"))
    docs.update((REPO_ROOT / "docs" / "roadmaps").rglob("*.md"))
    return sorted(p for p in docs if p.is_file())


def _read(path: Path) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []

    for required in (ACTIVE_ROADMAP, LEGACY_ROADMAP, AUTHORITY_BRIDGE):
        if not (REPO_ROOT / required).is_file():
            failures.append(f"Missing required authority surface: {required}")

    if not failures:
        active_text = _read(ACTIVE_ROADMAP)
        legacy_text = _read(LEGACY_ROADMAP)
        bridge_text = _read(AUTHORITY_BRIDGE)

        required_bridge_line = "**Active editorial authority:** `docs/roadmaps/system_roadmap.md`"
        required_mirror_line = "**Operational compatibility mirror (required until migration complete):** `docs/roadmap/system_roadmap.md`"
        required_active_transition = "Compatibility transition rule: `docs/roadmap/system_roadmap.md` is a required parseable operational mirror"
        required_legacy_authority = "Active editorial roadmap authority: `docs/roadmaps/system_roadmap.md`"

        if required_bridge_line not in bridge_text:
            failures.append("Roadmap authority bridge is missing active authority declaration")
        if required_mirror_line not in bridge_text:
            failures.append("Roadmap authority bridge is missing compatibility mirror declaration")
        if "docs/roadmap/roadmap_step_contract.md" not in bridge_text:
            failures.append("Roadmap authority bridge must reference docs/roadmap/roadmap_step_contract.md")

        if required_active_transition not in active_text:
            failures.append("Active roadmap is missing compatibility transition rule declaration")
        if required_legacy_authority not in legacy_text:
            failures.append("Legacy roadmap is missing active editorial authority declaration")
        if "docs/roadmap/roadmap_step_contract.md" not in legacy_text:
            failures.append("Legacy roadmap must reference docs/roadmap/roadmap_step_contract.md")

        # Compatibility mirror must preserve legacy executable entrypoints while migration is active.
        for required_step in ("| AI-01 |", "| AI-02 |", "| TRUST-01 |"):
            if required_step not in legacy_text:
                failures.append(f"Legacy roadmap missing required executable compatibility row: {required_step}")

    for path in iter_authority_docs():
        rel = path.relative_to(REPO_ROOT)
        if rel == ACTIVE_ROADMAP:
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in CONFLICT_PATTERNS:
            if pattern.search(text):
                failures.append(
                    f"Conflicting roadmap authority language in {rel}: pattern '{pattern.pattern}'"
                )
                break

    if failures:
        for msg in failures:
            print(f"[FAIL] {msg}")
        return 1

    print("[PASS] Roadmap authority checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
