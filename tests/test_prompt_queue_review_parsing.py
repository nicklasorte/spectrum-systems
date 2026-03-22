"""Tests for governed prompt queue review parsing and findings attachment."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    Priority,
    RiskLevel,
    WorkItemStatus,
    attach_findings_to_work_item,
    build_findings_artifact,
    make_work_item,
    parse_review_markdown,
    validate_findings_artifact,
)
from spectrum_systems.modules.prompt_queue.review_parser import ReviewParseError  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "prompt_queue_reviews"


class FixedClock:
    def __init__(self, values: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in values]

    def __call__(self):
        if not self._values:
            return datetime(2026, 3, 22, 0, 0, 0, tzinfo=timezone.utc)
        return self._values.pop(0)


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _work_item(status: WorkItemStatus = WorkItemStatus.REVIEW_COMPLETE) -> dict:
    item = make_work_item(
        work_item_id="wi-777",
        prompt_id="prompt-777",
        title="Review parsing",
        priority=Priority.HIGH,
        risk_level=RiskLevel.HIGH,
        repo="spectrum-systems",
        branch="feature/review-parse",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        clock=FixedClock(["2026-03-22T00:00:00Z"]),
    )
    item["status"] = status.value
    return item


def test_valid_claude_style_pass_review_parses_correctly():
    parsed = parse_review_markdown(_read_fixture("claude_pass_review.md"), provider="claude")
    assert parsed.review_decision == "PASS"
    assert parsed.trust_assessment == "YES"


def test_valid_claude_style_fail_review_parses_correctly():
    parsed = parse_review_markdown(_read_fixture("claude_fail_review.md"), provider="claude")
    assert parsed.review_decision == "FAIL"
    assert parsed.sections["critical_findings"]
    assert parsed.sections["required_fixes"]


def test_valid_codex_style_fail_review_parses_correctly():
    parsed = parse_review_markdown(_read_fixture("codex_fail_review.md"), provider="codex")
    assert parsed.review_decision == "FAIL"
    assert "findings_queue_integration.py" in parsed.sections["required_fixes"]


def test_fail_review_missing_critical_findings_fails_closed():
    with pytest.raises(ReviewParseError):
        parse_review_markdown(_read_fixture("fail_missing_critical_findings.md"), provider="claude")


def test_fail_review_missing_required_fixes_fails_closed():
    with pytest.raises(ReviewParseError):
        parse_review_markdown(_read_fixture("fail_missing_required_fixes.md"), provider="claude")


def test_review_missing_decision_fails_closed():
    with pytest.raises(ReviewParseError):
        parse_review_markdown(_read_fixture("missing_decision.md"), provider="claude")


def test_review_missing_failure_mode_summary_fails_closed():
    with pytest.raises(ReviewParseError):
        parse_review_markdown(_read_fixture("missing_failure_mode_summary.md"), provider="claude")


def test_provider_metadata_is_preserved_in_normalized_artifact():
    parsed = parse_review_markdown(_read_fixture("codex_fail_review.md"), provider="codex")
    work_item = _work_item()
    work_item["review_fallback_used"] = True
    work_item["review_fallback_reason"] = "usage_limit"
    artifact = build_findings_artifact(
        work_item=work_item,
        parsed_review=parsed,
        source_review_artifact_path="docs/reviews/sample.md",
        clock=FixedClock(["2026-03-22T00:02:00Z"]),
    )
    assert artifact["review_provider"] == "codex"
    assert artifact["fallback_used"] is True
    assert artifact["fallback_reason"] == "usage_limit"


def test_findings_artifact_validates_against_schema():
    validate_findings_artifact(load_example("prompt_queue_review_findings"))


def test_queue_work_item_update_occurs_after_successful_parse():
    parsed = parse_review_markdown(_read_fixture("claude_fail_review.md"), provider="claude")
    work_item = _work_item()
    artifact = build_findings_artifact(
        work_item=work_item,
        parsed_review=parsed,
        source_review_artifact_path="docs/reviews/claude-fail.md",
        clock=FixedClock(["2026-03-22T00:03:00Z"]),
    )
    updated = attach_findings_to_work_item(
        work_item,
        findings_artifact_path="artifacts/prompt_queue/findings/wi-777.findings.json",
        clock=FixedClock(["2026-03-22T00:03:01Z"]),
    )

    assert artifact["review_decision"] == "FAIL"
    assert updated["findings_artifact_path"].endswith("wi-777.findings.json")
    assert updated["status"] == WorkItemStatus.FINDINGS_PARSED.value
