from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

_NON_AUTHORITY_SLICE_FILES = [
    _REPO_ROOT / "spectrum_systems" / "modules" / "runtime" / "failure_eval_generation.py",
    _REPO_ROOT / "contracts" / "examples" / "generated_eval_case.json",
    _REPO_ROOT / "tests" / "fixtures" / "failure_eval_generation_cases.json",
]

_FORBIDDEN_AUTHORITY_VALUES = ("block", "freeze", "allow")
_FORBIDDEN_AUTHORITY_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(token) for token in _FORBIDDEN_AUTHORITY_VALUES) + r")\b",
    flags=re.IGNORECASE,
)


def _find_forbidden_authority_values(text: str) -> list[str]:
    return sorted({match.group(0) for match in _FORBIDDEN_AUTHORITY_PATTERN.finditer(text)})


def test_forbidden_authority_value_detector_finds_known_bad_tokens() -> None:
    sample = "state block transitions to Freeze and ALLOW"
    assert _find_forbidden_authority_values(sample) == ["ALLOW", "Freeze", "block"]


def test_non_authority_runtime_slice_files_do_not_emit_forbidden_authority_values() -> None:
    violations: list[str] = []

    for path in _NON_AUTHORITY_SLICE_FILES:
        content = path.read_text(encoding="utf-8")
        found = _find_forbidden_authority_values(content)
        if found:
            violations.append(f"{path.relative_to(_REPO_ROOT)}:{','.join(found)}")

    assert violations == []
