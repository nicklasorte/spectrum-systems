"""Deterministic request classification for AEX."""

from __future__ import annotations

import re
from typing import Any

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
_CONTEXT_CAPABILITY_HINTS = (
    "context",
    "recipe",
    "admission",
    "bundle",
    "source",
    "lineage",
    "tpa",
    "tlc",
    "pqx",
    "aex",
)


ExecutionType = str


def classify_execution_type(prompt_text: str, target_paths: list[str] | None = None) -> ExecutionType:
    text = (prompt_text or "").lower()
    paths = [str(item) for item in (target_paths or [])]

    if any(re.search(pattern, text) for pattern in _WRITE_PATTERNS):
        return "repo_write"
    if any(re.search(pattern, text) for pattern in _READ_PATTERNS):
        return "analysis_only"
    return "unknown"


def classify_with_reasons(prompt_text: str, target_paths: list[str] | None = None) -> dict[str, Any]:
    execution_type = classify_execution_type(prompt_text, target_paths)
    reasons: list[str] = []
    if execution_type == "repo_write":
        reasons.append("repo_write_signal_detected")
    elif execution_type == "analysis_only":
        reasons.append("analysis_signal_detected")
    else:
        reasons.append("classification_ambiguous")
    normalization_outcome = "normalized" if execution_type != "unknown" else "normalized_with_ambiguity"
    return {
        "execution_type": execution_type,
        "reason_codes": reasons,
        "normalization_outcome": normalization_outcome,
    }


def is_repo_sensitive_unknown(*, execution_type: str, repo_mutation_requested: bool, target_paths: list[str]) -> bool:
    if execution_type != "unknown":
        return False
    if repo_mutation_requested:
        return True
    return any(path.startswith(prefix) for path in target_paths for prefix in _REPO_SENSITIVE_PATH_HINTS)


def is_context_capability_request(prompt_text: str, target_paths: list[str] | None = None) -> bool:
    text = (prompt_text or "").lower()
    paths = " ".join(str(item).lower() for item in (target_paths or []))
    haystack = f"{text} {paths}"
    return any(hint in haystack for hint in _CONTEXT_CAPABILITY_HINTS)
