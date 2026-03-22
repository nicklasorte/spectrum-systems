"""Tests for governed prompt queue review parsing handoff from invocation output_reference."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    Priority,
    RiskLevel,
    WorkItemStatus,
    apply_review_parsing_handoff_to_queue,
    make_queue_state,
    make_work_item,
    run_review_parsing_handoff,
    validate_queue_state,
    validate_review_parsing_handoff,
)
from spectrum_systems.modules.prompt_queue.review_parsing_handoff import ReviewParsingHandoffError  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "prompt_queue_reviews"


class FixedClock:
    def __init__(self, values: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in values]

    def __call__(self):
        if not self._values:
            return datetime(2026, 3, 22, 0, 0, 0, tzinfo=timezone.utc)
        return self._values.pop(0)


def _base_work_item() -> dict:
    item = make_work_item(
        work_item_id="wi-handoff-1",
        prompt_id="prompt-handoff-1",
        title="Review parsing handoff",
        priority=Priority.HIGH,
        risk_level=RiskLevel.HIGH,
        repo="spectrum-systems",
        branch="main",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        clock=FixedClock(["2026-03-22T00:00:00Z"]),
    )
    item["status"] = WorkItemStatus.REVIEW_INVOCATION_SUCCEEDED.value
    item["review_trigger_artifact_path"] = "artifacts/prompt_queue/review_triggers/wi-handoff-1.review_trigger.json"
    return item


def _invocation(*, output_reference: str | None, status: str = "success") -> dict:
    return {
        "review_invocation_result_artifact_id": "review-invocation-result-001",
        "invocation_id": "inv-2bbf7d6b40301d9b",
        "work_item_id": "wi-handoff-1",
        "parent_work_item_id": None,
        "review_trigger_artifact_path": "artifacts/prompt_queue/review_triggers/wi-handoff-1.review_trigger.json",
        "execution_result_artifact_path": "artifacts/prompt_queue/execution_results/wi-handoff-1.execution_result.json",
        "provider_requested": "codex",
        "provider_used": "codex",
        "fallback_used": False,
        "fallback_reason": None,
        "invocation_status": status,
        "started_at": "2026-03-22T00:10:00Z",
        "completed_at": "2026-03-22T00:10:12Z",
        "generated_at": "2026-03-22T00:10:12Z",
        "generator_version": "prompt_queue_review_invocation_recorder.v1",
        "output_reference": output_reference,
        "error_summary": None,
    }


def test_successful_handoff_emits_completed_payload_and_queue_linkage(tmp_path: Path):
    work_item = _base_work_item()
    output_rel = Path("artifacts/prompt_queue/reviews/wi-handoff-1.review.md")
    (tmp_path / output_rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / output_rel).write_text((FIXTURES / "codex_fail_review.md").read_text(encoding="utf-8"), encoding="utf-8")

    handoff = run_review_parsing_handoff(
        work_item=work_item,
        review_invocation_result=_invocation(output_reference=str(output_rel)),
        review_invocation_result_artifact_path="artifacts/prompt_queue/review_invocation_results/q.wi-handoff-1.json",
        repo_root=tmp_path,
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T00:11:00Z", "2026-03-22T00:11:01Z"]),
    )

    assert handoff["handoff_artifact"]["handoff_status"] == "handoff_completed"
    assert handoff["handoff_artifact"]["findings_artifact_path"].endswith("wi-handoff-1.findings.json")
    validate_review_parsing_handoff(handoff["handoff_artifact"])

    queue = make_queue_state(queue_id="queue-handoff", work_items=[work_item], clock=FixedClock(["2026-03-22T00:11:02Z"]))
    updated_queue, updated_item = apply_review_parsing_handoff_to_queue(
        queue_state=queue,
        work_item_id="wi-handoff-1",
        findings_artifact_path=handoff["findings_artifact_path"],
        review_parsing_handoff_artifact_path="artifacts/prompt_queue/review_parsing_handoffs/queue.wi-handoff-1.json",
        clock=FixedClock(["2026-03-22T00:11:03Z", "2026-03-22T00:11:04Z"]),
    )
    validate_queue_state(updated_queue)
    assert updated_item["status"] == WorkItemStatus.FINDINGS_PARSED.value


def test_invocation_status_not_success_fails_closed(tmp_path: Path):
    with pytest.raises(ReviewParsingHandoffError):
        run_review_parsing_handoff(
            work_item=_base_work_item(),
            review_invocation_result=_invocation(output_reference="artifacts/prompt_queue/reviews/x.md", status="failure"),
            review_invocation_result_artifact_path="a.json",
            repo_root=tmp_path,
        )


def test_missing_output_reference_fails_closed(tmp_path: Path):
    with pytest.raises(ValueError):
        run_review_parsing_handoff(
            work_item=_base_work_item(),
            review_invocation_result=_invocation(output_reference=None),
            review_invocation_result_artifact_path="a.json",
            repo_root=tmp_path,
        )


def test_missing_output_file_fails_closed(tmp_path: Path):
    with pytest.raises(ReviewParsingHandoffError):
        run_review_parsing_handoff(
            work_item=_base_work_item(),
            review_invocation_result=_invocation(output_reference="artifacts/prompt_queue/reviews/missing.md"),
            review_invocation_result_artifact_path="a.json",
            repo_root=tmp_path,
        )


def test_malformed_review_output_fails_closed(tmp_path: Path):
    work_item = _base_work_item()
    output_rel = Path("artifacts/prompt_queue/reviews/wi-handoff-1.review.md")
    (tmp_path / output_rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / output_rel).write_text((FIXTURES / "missing_decision.md").read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ReviewParsingHandoffError):
        run_review_parsing_handoff(
            work_item=work_item,
            review_invocation_result=_invocation(output_reference=str(output_rel)),
            review_invocation_result_artifact_path="a.json",
            repo_root=tmp_path,
        )


def test_invalid_lineage_fails_closed(tmp_path: Path):
    work_item = _base_work_item()
    bad = _invocation(output_reference="artifacts/prompt_queue/reviews/x.md")
    bad["work_item_id"] = "other"
    with pytest.raises(ReviewParsingHandoffError):
        run_review_parsing_handoff(
            work_item=work_item,
            review_invocation_result=bad,
            review_invocation_result_artifact_path="a.json",
            repo_root=tmp_path,
        )


def test_duplicate_handoff_attempt_is_rejected_deterministically():
    item = _base_work_item()
    item["review_parsing_handoff_artifact_path"] = "artifacts/prompt_queue/review_parsing_handoffs/existing.json"
    queue = {"queue_id": "q", "queue_status": "active", "work_items": [item], "active_work_item_id": "wi-handoff-1", "created_at": "2026-03-22T00:00:00Z", "updated_at": "2026-03-22T00:00:00Z"}

    with pytest.raises(ValueError):
        apply_review_parsing_handoff_to_queue(
            queue_state=queue,
            work_item_id="wi-handoff-1",
            findings_artifact_path="artifacts/prompt_queue/findings/wi-handoff-1.findings.json",
            review_parsing_handoff_artifact_path="artifacts/prompt_queue/review_parsing_handoffs/new.json",
            clock=FixedClock(["2026-03-22T00:11:03Z", "2026-03-22T00:11:04Z"]),
        )
