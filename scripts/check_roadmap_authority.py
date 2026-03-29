#!/usr/bin/env python3
"""Fail-closed roadmap authority checker."""
from __future__ import annotations

from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
AUTH_PATH = Path("docs/roadmap/system_roadmap.md")
AUTH_CLAIM = "single authoritative roadmap"
CONFLICT_PATTERNS = (
    re.compile(r"\bprimary roadmap\b", re.IGNORECASE),
    re.compile(r"\bsole active roadmap\b", re.IGNORECASE),
    re.compile(r"\bactive roadmap is\b", re.IGNORECASE),
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


def main() -> int:
    failures: list[str] = []
    authority_file = REPO_ROOT / AUTH_PATH
    if not authority_file.is_file():
        failures.append(f"Missing authoritative roadmap file: {AUTH_PATH}")

    claims: list[Path] = []
    for path in iter_authority_docs():
        rel = path.relative_to(REPO_ROOT)
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        if AUTH_CLAIM in lowered:
            claims.append(rel)

        if rel == AUTH_PATH:
            continue

        for pattern in CONFLICT_PATTERNS:
            if pattern.search(text):
                failures.append(
                    f"Conflicting roadmap authority language in {rel}: pattern '{pattern.pattern}'"
                )
                break

    if claims != [AUTH_PATH]:
        failures.append(
            "Authority claim must appear exactly once in docs/roadmap/system_roadmap.md; found: "
            + ", ".join(str(p) for p in claims)
        )

    if failures:
        for msg in failures:
            print(f"[FAIL] {msg}")
        return 1

    print("[PASS] Roadmap authority checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
