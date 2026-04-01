from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.review_signal_extractor import (
    ReviewSignalExtractionError,
    extract_review_signal,
)


def test_extract_review_signal_from_repo_markdown() -> None:
    signal = extract_review_signal("docs/reviews/2026-03-27-control-loop-trace-context-stabilization-checkpoint.md")
    assert signal["artifact_type"] == "review_control_signal"
    assert signal["review_type"]
    assert signal["gate_assessment"] in {"PASS", "FAIL", "CONDITIONAL"}
    validate_artifact(signal, "review_control_signal")


def test_extract_review_signal_is_deterministic() -> None:
    first = extract_review_signal("docs/reviews/2026-03-27-control-loop-trace-context-stabilization-checkpoint.md")
    second = extract_review_signal("docs/reviews/2026-03-27-control-loop-trace-context-stabilization-checkpoint.md")
    assert first == second


def test_malformed_review_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "bad-review.md"
    path.write_text("# no frontmatter\n", encoding="utf-8")
    with pytest.raises(ReviewSignalExtractionError):
        extract_review_signal(path)
