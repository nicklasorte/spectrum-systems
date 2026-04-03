from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.review_signal_extractor import (
    ReviewSignalExtractionError,
    extract_review_signal,
)
from spectrum_systems.modules.runtime.review_eval_bridge import build_eval_result_from_review_signal


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


def test_same_review_markdown_produces_deterministic_derived_eval_result() -> None:
    first_signal = extract_review_signal("docs/reviews/2026-03-27-control-loop-trace-context-stabilization-checkpoint.md")
    second_signal = extract_review_signal("docs/reviews/2026-03-27-control-loop-trace-context-stabilization-checkpoint.md")
    first_eval = build_eval_result_from_review_signal(first_signal)
    second_eval = build_eval_result_from_review_signal(second_signal)
    assert first_eval == second_eval


def test_malformed_review_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "bad-review.md"
    path.write_text("# no frontmatter\n", encoding="utf-8")
    with pytest.raises(ReviewSignalExtractionError):
        extract_review_signal(path)


def test_unknown_review_type_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "bad-review-type.md"
    path.write_text(
        "---\n"
        "module: runtime\n"
        "review_type: unknown_type\n"
        "review_date: 2026-04-03\n"
        "reviewer: test\n"
        "decision: PASS\n"
        "status: final\n"
        "---\n",
        encoding="utf-8",
    )
    with pytest.raises(ReviewSignalExtractionError, match="review_type"):
        extract_review_signal(path)
