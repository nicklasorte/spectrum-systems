from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.review_signal_extractor import (
    ReviewSignalExtractionError,
    extract_review_signal,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_review_markdown_extracts_to_structured_signal() -> None:
    review_path = _REPO_ROOT / "docs" / "reviews" / "2026-03-22-replay-engine-review.md"
    signal = extract_review_signal(str(review_path))
    assert signal["artifact_type"] == "review_control_signal"
    assert signal["gate_assessment"] in {"PASS", "FAIL", "CONDITIONAL"}
    assert signal["scale_recommendation"] in {"YES", "NO"}
    assert signal["review_id"].startswith("review-")


def test_malformed_review_fails_closed(tmp_path: Path) -> None:
    malformed = tmp_path / "bad-review.md"
    malformed.write_text("## Missing heading and date\n", encoding="utf-8")
    with pytest.raises(ReviewSignalExtractionError, match="malformed review"):
        extract_review_signal(str(malformed))


def test_extraction_is_deterministic() -> None:
    review_path = _REPO_ROOT / "docs" / "reviews" / "2026-03-22-replay-engine-review.md"
    first = extract_review_signal(str(review_path))
    second = extract_review_signal(str(review_path))
    assert first == second
