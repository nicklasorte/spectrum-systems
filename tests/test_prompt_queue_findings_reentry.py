"""Tests for governed prompt queue findings-to-repair reentry wiring."""

from __future__ import annotations

import json
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
    apply_findings_reentry_to_queue,
    default_findings_reentry_path,
    default_repair_prompt_path,
    run_findings_reentry,
    validate_findings_reentry,
    validate_queue_state,
    write_findings_reentry_artifact,
    write_repair_prompt_artifact,
)
from spectrum_systems.modules.prompt_queue.findings_reentry import FindingsReentryError  # noqa: E402
from spectrum_systems.modules.prompt_queue.queue_models import make_queue_state, make_work_item  # noqa: E402


class FixedClock:
    def __init__(self, values: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in values]

    def __call__(self):
        if self._values:
            return self._values.pop(0)
        return datetime(2026, 3, 22, 0, 0, 0, tzinfo=timezone.utc)


def _work_item() -> dict:
    item = make_work_item(
        work_item_id="wi-reentry-1",
        prompt_id="prompt-reentry-1",
        title="Findings reentry",
        priority=Priority.HIGH,
        risk_level=RiskLevel.HIGH,
        repo="spectrum-systems",
        branch="main",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        clock=FixedClock(["2026-03-22T00:00:00Z"]),
    )
    item["status"] = WorkItemStatus.FINDINGS_PARSED.value
    item["findings_artifact_path"] = "artifacts/prompt_queue/findings/wi-reentry-1.findings.json"
    item["review_invocation_result_artifact_path"] = (
        "artifacts/prompt_queue/review_invocation_results/queue.wi-reentry-1.review_invocation_result.json"
    )
    item["review_parsing_handoff_artifact_path"] = (
        "artifacts/prompt_queue/review_parsing_handoffs/queue.wi-reentry-1.review_parsing_handoff.json"
    )
    return item


def _findings() -> dict:
    findings = load_example("prompt_queue_review_findings")
    findings["work_item_id"] = "wi-reentry-1"
    findings["review_decision"] = "FAIL"
    findings["source_review_artifact_path"] = "artifacts/prompt_queue/reviews/wi-reentry-1.review.md"
    findings["required_fixes"] = [
        {
            "finding_id": "required_fixes-1",
            "summary": "Fix deterministic state update",
            "body": "Repair queue transition path in findings reentry integration.",
            "severity": "high",
            "file_references": ["spectrum_systems/modules/prompt_queue/findings_reentry_queue_integration.py"],
            "source_section": "required_fixes",
        }
    ]
    return findings


def _invocation_result() -> dict:
    data = load_example("prompt_queue_review_invocation_result")
    data["work_item_id"] = "wi-reentry-1"
    data["parent_work_item_id"] = None
    data["invocation_status"] = "success"
    data["output_reference"] = "artifacts/prompt_queue/reviews/wi-reentry-1.review.md"
    data["review_trigger_artifact_path"] = "artifacts/prompt_queue/review_triggers/wi-reentry-1.review_trigger.json"
    return data


def _handoff() -> dict:
    data = load_example("prompt_queue_review_parsing_handoff")
    data["work_item_id"] = "wi-reentry-1"
    data["parent_work_item_id"] = None
    data["findings_artifact_path"] = "artifacts/prompt_queue/findings/wi-reentry-1.findings.json"
    data["review_invocation_result_artifact_path"] = (
        "artifacts/prompt_queue/review_invocation_results/queue.wi-reentry-1.review_invocation_result.json"
    )
    data["output_reference"] = "artifacts/prompt_queue/reviews/wi-reentry-1.review.md"
    return data


def test_valid_live_findings_reentry_completes_and_links_repair_prompt(tmp_path: Path):
    work_item = _work_item()
    queue = make_queue_state(queue_id="queue-reentry", work_items=[work_item], clock=FixedClock(["2026-03-22T00:00:01Z"]))

    repair_prompt_path = str(default_repair_prompt_path(work_item_id="wi-reentry-1", root_dir=REPO_ROOT).relative_to(REPO_ROOT))
    result = run_findings_reentry(
        work_item=work_item,
        findings_artifact=_findings(),
        findings_artifact_path=work_item["findings_artifact_path"],
        review_parsing_handoff_artifact=_handoff(),
        review_parsing_handoff_artifact_path=work_item["review_parsing_handoff_artifact_path"],
        review_invocation_result_artifact=_invocation_result(),
        review_invocation_result_artifact_path=work_item["review_invocation_result_artifact_path"],
        repair_prompt_artifact_path=repair_prompt_path,
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T00:01:00Z", "2026-03-22T00:01:01Z"]),
    )

    assert result["reentry_artifact"]["reentry_status"] == "reentry_completed"
    assert result["repair_prompt_artifact"]["prompt_generation_status"] == "generated"

    reentry_path = default_findings_reentry_path(work_item_id="wi-reentry-1", root_dir=tmp_path)
    repair_path = default_repair_prompt_path(work_item_id="wi-reentry-1", root_dir=tmp_path)
    write_findings_reentry_artifact(artifact=result["reentry_artifact"], output_path=reentry_path)
    write_repair_prompt_artifact(result["repair_prompt_artifact"], repair_path)

    updated_queue, updated_item = apply_findings_reentry_to_queue(
        queue_state=queue,
        work_item_id="wi-reentry-1",
        findings_reentry_artifact_path=str(reentry_path.relative_to(tmp_path)),
        repair_prompt_artifact_path=str(repair_path.relative_to(tmp_path)),
        clock=FixedClock(["2026-03-22T00:01:02Z", "2026-03-22T00:01:03Z"]),
    )
    validate_queue_state(updated_queue)
    assert updated_item["status"] == WorkItemStatus.REPAIR_PROMPT_GENERATED.value


def test_missing_findings_artifact_fails_closed():
    with pytest.raises(FindingsReentryError):
        run_findings_reentry(
            work_item=_work_item(),
            findings_artifact=_findings(),
            findings_artifact_path="",
            review_parsing_handoff_artifact=_handoff(),
            review_parsing_handoff_artifact_path=_work_item()["review_parsing_handoff_artifact_path"],
            review_invocation_result_artifact=_invocation_result(),
            review_invocation_result_artifact_path=_work_item()["review_invocation_result_artifact_path"],
            repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-reentry-1.repair_prompt.json",
        )


def test_missing_handoff_artifact_fails_closed():
    with pytest.raises(ValueError):
        run_findings_reentry(
            work_item=_work_item(),
            findings_artifact=_findings(),
            findings_artifact_path=_work_item()["findings_artifact_path"],
            review_parsing_handoff_artifact={},
            review_parsing_handoff_artifact_path=_work_item()["review_parsing_handoff_artifact_path"],
            review_invocation_result_artifact=_invocation_result(),
            review_invocation_result_artifact_path=_work_item()["review_invocation_result_artifact_path"],
            repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-reentry-1.repair_prompt.json",
        )


def test_lineage_mismatch_fails_closed():
    bad_handoff = _handoff()
    bad_handoff["findings_artifact_path"] = "artifacts/prompt_queue/findings/other.findings.json"
    with pytest.raises(FindingsReentryError):
        run_findings_reentry(
            work_item=_work_item(),
            findings_artifact=_findings(),
            findings_artifact_path=_work_item()["findings_artifact_path"],
            review_parsing_handoff_artifact=bad_handoff,
            review_parsing_handoff_artifact_path=_work_item()["review_parsing_handoff_artifact_path"],
            review_invocation_result_artifact=_invocation_result(),
            review_invocation_result_artifact_path=_work_item()["review_invocation_result_artifact_path"],
            repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-reentry-1.repair_prompt.json",
        )


def test_repair_prompt_generation_failure_fails_closed():
    findings = _findings()
    findings["review_decision"] = "PASS"
    with pytest.raises(FindingsReentryError):
        run_findings_reentry(
            work_item=_work_item(),
            findings_artifact=findings,
            findings_artifact_path=_work_item()["findings_artifact_path"],
            review_parsing_handoff_artifact=_handoff(),
            review_parsing_handoff_artifact_path=_work_item()["review_parsing_handoff_artifact_path"],
            review_invocation_result_artifact=_invocation_result(),
            review_invocation_result_artifact_path=_work_item()["review_invocation_result_artifact_path"],
            repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-reentry-1.repair_prompt.json",
        )


def test_findings_reentry_requires_required_fixes():
    findings = _findings()
    findings["required_fixes"] = []
    with pytest.raises(FindingsReentryError, match="at least one required fix"):
        run_findings_reentry(
            work_item=_work_item(),
            findings_artifact=findings,
            findings_artifact_path=_work_item()["findings_artifact_path"],
            review_parsing_handoff_artifact=_handoff(),
            review_parsing_handoff_artifact_path=_work_item()["review_parsing_handoff_artifact_path"],
            review_invocation_result_artifact=_invocation_result(),
            review_invocation_result_artifact_path=_work_item()["review_invocation_result_artifact_path"],
            repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-reentry-1.repair_prompt.json",
        )


def test_duplicate_reentry_attempt_is_prevented():
    item = _work_item()
    item["findings_reentry_artifact_path"] = "artifacts/prompt_queue/findings_reentries/existing.json"
    queue = {
        "queue_id": "queue-reentry",
        "queue_status": "active",
        "work_items": [item],
        "active_work_item_id": "wi-reentry-1",
        "created_at": "2026-03-22T00:00:00Z",
        "updated_at": "2026-03-22T00:00:00Z",
    }
    with pytest.raises(ValueError):
        apply_findings_reentry_to_queue(
            queue_state=queue,
            work_item_id="wi-reentry-1",
            findings_reentry_artifact_path="artifacts/prompt_queue/findings_reentries/new.json",
            repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-reentry-1.repair_prompt.json",
        )


def test_findings_reentry_example_validates_against_schema():
    validate_findings_reentry(load_example("prompt_queue_findings_reentry"))


def test_queue_update_is_deterministic_and_schema_valid():
    queue = make_queue_state(queue_id="q", work_items=[_work_item()], clock=FixedClock(["2026-03-22T00:00:01Z"]))
    updated_queue_a, updated_item_a = apply_findings_reentry_to_queue(
        queue_state=queue,
        work_item_id="wi-reentry-1",
        findings_reentry_artifact_path="artifacts/prompt_queue/findings_reentries/wi-reentry-1.findings_reentry.json",
        repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-reentry-1.repair_prompt.json",
        clock=FixedClock(["2026-03-22T00:01:00Z", "2026-03-22T00:01:01Z"]),
    )
    queue_copy = json.loads(json.dumps(queue))
    updated_queue_b, updated_item_b = apply_findings_reentry_to_queue(
        queue_state=queue_copy,
        work_item_id="wi-reentry-1",
        findings_reentry_artifact_path="artifacts/prompt_queue/findings_reentries/wi-reentry-1.findings_reentry.json",
        repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-reentry-1.repair_prompt.json",
        clock=FixedClock(["2026-03-22T00:01:00Z", "2026-03-22T00:01:01Z"]),
    )
    assert updated_item_a == updated_item_b
    assert updated_queue_a == updated_queue_b
    validate_queue_state(updated_queue_a)
