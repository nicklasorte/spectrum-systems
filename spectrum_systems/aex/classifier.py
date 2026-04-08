"""Deterministic request classification for AEX.

This classifier intentionally uses simple lexical rules and defaults to `unknown` for ambiguity.
"""

from __future__ import annotations

import re

_WRITE_PATTERNS = (
    r"\bcreate\b",
    r"\bmodify\b",
    r"\bupdate\b",
    r"\bedit\b",
    r"\bpatch\b",
    r"\bdiff\b",
    r"\bcommit\b",
    r"\bwrite\b",
    r"\bdelete\b",
    r"\brename\b",
)
_READ_PATTERNS = (
    r"\banaly[sz]e\b",
    r"\bexplain\b",
    r"\bsummarize\b",
    r"\breview\b",
    r"\bread\b",
)
_REPO_SENSITIVE_PATH_HINTS = ("contracts/", "spectrum_systems/", "tests/", "docs/")


ExecutionType = str


def classify_execution_type(prompt_text: str, target_paths: list[str] | None = None) -> ExecutionType:
    text = (prompt_text or "").lower()
    paths = [str(item) for item in (target_paths or [])]

    if any(re.search(pattern, text) for pattern in _WRITE_PATTERNS):
        return "repo_write"
    if any(re.search(pattern, text) for pattern in _READ_PATTERNS) and not paths:
        return "analysis_only"
    return "unknown"


def is_repo_sensitive_unknown(*, execution_type: str, repo_mutation_requested: bool, target_paths: list[str]) -> bool:
    if execution_type != "unknown":
        return False
    if repo_mutation_requested:
        return True
    return any(path.startswith(prefix) for path in target_paths for prefix in _REPO_SENSITIVE_PATH_HINTS)
