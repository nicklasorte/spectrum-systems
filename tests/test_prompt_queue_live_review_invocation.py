"""Focused tests for governed prompt queue live review invocation."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    InvocationProviderResult,
    Priority,
    RiskLevel,
    WorkItemStatus,
    apply_live_review_invocation,
    make_queue_state,
    make_work_item,
    validate_review_invocation_result,
    write_review_invocation_result_artifact,
)


class FixedClock:
    def __init__(self, values: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in values]

    def __call__(self):
        if self._values:
            return self._values.pop(0)
        return datetime(2026, 3, 22, 0, 0, 0, tzinfo=timezone.utc)


def _base_queue(tmp_path: Path) -> tuple[dict, str, Path, Path, Path]:
    work_item = make_work_item(
        work_item_id="wi-live-1",
        prompt_id="prompt-live-1",
        title="Live invocation",
        priority=Priority.HIGH,
        risk_level=RiskLevel.HIGH,
        repo="spectrum-systems",
        branch="main",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        clock=FixedClock(["2026-03-22T00:00:00Z"]),
    )
    work_item["status"] = WorkItemStatus.REVIEW_TRIGGERED.value

    execution_rel = Path("artifacts/prompt_queue/execution_results/wi-live-1.execution_result.json")
    trigger_rel = Path("artifacts/prompt_queue/review_triggers/wi-live-1.review_trigger.json")
    output_rel = Path("artifacts/prompt_queue/reviews/wi-live-1.review.md")

    (REPO_ROOT / execution_rel).parent.mkdir(parents=True, exist_ok=True)
    (REPO_ROOT / trigger_rel).parent.mkdir(parents=True, exist_ok=True)
    (REPO_ROOT / output_rel).parent.mkdir(parents=True, exist_ok=True)

    (REPO_ROOT / execution_rel).write_text(json.dumps({"work_item_id": "wi-live-1"}), encoding="utf-8")
    (REPO_ROOT / trigger_rel).write_text(
        json.dumps(
            {
                "work_item_id": "wi-live-1",
                "execution_result_artifact_path": str(execution_rel),
            }
        ),
        encoding="utf-8",
    )
    (REPO_ROOT / output_rel).write_text("review output", encoding="utf-8")

    work_item["review_trigger_artifact_path"] = str(trigger_rel)
    queue_state = make_queue_state(queue_id="queue-live", work_items=[work_item], clock=FixedClock(["2026-03-22T00:00:00Z"]))
    queue_state_path = tmp_path / "queue_state.json"
    queue_state_path.write_text(json.dumps(queue_state), encoding="utf-8")
    return queue_state, work_item["work_item_id"], queue_state_path, trigger_rel, output_rel


def _ok_provider(output_ref: str):
    return lambda _wi: InvocationProviderResult(success=True, output_reference=output_ref)


def test_valid_review_triggered_work_item_invokes_codex_successfully(tmp_path: Path):
    queue_state, work_item_id, queue_state_path, _, output_rel = _base_queue(tmp_path)
    updated_queue, updated_item, invocation_result = apply_live_review_invocation(
        queue_state=queue_state,
        work_item_id=work_item_id,
        queue_state_path=queue_state_path,
        repo_root=REPO_ROOT,
        run_codex=_ok_provider(str(output_rel)),
        run_claude=_ok_provider(str(output_rel)),
        clock=FixedClock(["2026-03-22T00:01:00Z", "2026-03-22T00:01:01Z", "2026-03-22T00:01:02Z", "2026-03-22T00:01:03Z"]),
    )
    assert updated_item["status"] == WorkItemStatus.REVIEW_INVOCATION_SUCCEEDED.value
    assert invocation_result["provider_used"] == "codex"
    assert invocation_result["fallback_used"] is False
    assert updated_queue["work_items"][0]["review_invocation_result_artifact_path"] is not None


@pytest.mark.parametrize("reason", ["usage_limit", "rate_limited", "auth_failure", "timeout", "provider_unavailable"])
def test_bounded_fallback_to_claude_for_allowed_reasons(tmp_path: Path, reason: str):
    queue_state, work_item_id, queue_state_path, _, output_rel = _base_queue(tmp_path)
    _, updated_item, invocation_result = apply_live_review_invocation(
        queue_state=queue_state,
        work_item_id=work_item_id,
        queue_state_path=queue_state_path,
        repo_root=REPO_ROOT,
        run_codex=lambda _wi: InvocationProviderResult(success=False, failure_reason=reason, error_message=reason),
        run_claude=_ok_provider(str(output_rel)),
        clock=FixedClock(["2026-03-22T00:01:00Z", "2026-03-22T00:01:01Z", "2026-03-22T00:01:02Z", "2026-03-22T00:01:03Z"]),
    )
    assert updated_item["status"] == WorkItemStatus.REVIEW_INVOCATION_SUCCEEDED.value
    assert invocation_result["provider_used"] == "claude"
    assert invocation_result["fallback_used"] is True
    assert invocation_result["fallback_reason"] == reason


def test_fallback_cannot_occur_with_null_reason(tmp_path: Path):
    queue_state, work_item_id, queue_state_path, _, output_rel = _base_queue(tmp_path)
    _, updated_item, invocation_result = apply_live_review_invocation(
        queue_state=queue_state,
        work_item_id=work_item_id,
        queue_state_path=queue_state_path,
        repo_root=REPO_ROOT,
        run_codex=lambda _wi: InvocationProviderResult(success=False, failure_reason=None, error_message="bad"),
        run_claude=_ok_provider(str(output_rel)),
    )
    assert updated_item["status"] == WorkItemStatus.REVIEW_INVOCATION_FAILED.value
    assert invocation_result["fallback_used"] is False
    assert invocation_result["fallback_reason"] is None


def test_success_artifact_with_null_output_reference_is_rejected(tmp_path: Path):
    artifact = {
        "review_invocation_result_artifact_id": "id-1",
        "invocation_id": "inv-1",
        "work_item_id": "wi-live-1",
        "parent_work_item_id": None,
        "review_trigger_artifact_path": "a",
        "execution_result_artifact_path": "b",
        "provider_requested": "codex",
        "provider_used": "codex",
        "fallback_used": False,
        "fallback_reason": None,
        "invocation_status": "success",
        "started_at": "2026-03-22T00:00:00Z",
        "completed_at": "2026-03-22T00:00:01Z",
        "generated_at": "2026-03-22T00:00:01Z",
        "generator_version": "v1",
        "output_reference": None,
        "error_summary": None,
    }
    with pytest.raises(ValueError):
        write_review_invocation_result_artifact(artifact=artifact, output_path=tmp_path / "x.json", repo_root=REPO_ROOT)


def test_provider_failure_before_output_maps_to_review_invocation_failed(tmp_path: Path):
    queue_state, work_item_id, queue_state_path, _, _ = _base_queue(tmp_path)
    _, updated_item, _ = apply_live_review_invocation(
        queue_state=queue_state,
        work_item_id=work_item_id,
        queue_state_path=queue_state_path,
        repo_root=REPO_ROOT,
        run_codex=lambda _wi: InvocationProviderResult(success=False, failure_reason="unexpected_failure", error_message="x"),
        run_claude=lambda _wi: InvocationProviderResult(success=True, output_reference="unused"),
    )
    assert updated_item["status"] == WorkItemStatus.REVIEW_INVOCATION_FAILED.value


def test_trigger_lineage_mismatch_leads_to_blocked(tmp_path: Path):
    queue_state, work_item_id, queue_state_path, trigger_rel, _ = _base_queue(tmp_path)
    (REPO_ROOT / trigger_rel).write_text(json.dumps({"work_item_id": "other", "execution_result_artifact_path": "x"}), encoding="utf-8")
    _, updated_item, _ = apply_live_review_invocation(
        queue_state=queue_state,
        work_item_id=work_item_id,
        queue_state_path=queue_state_path,
        repo_root=REPO_ROOT,
        run_codex=lambda _wi: InvocationProviderResult(success=True, output_reference="unused"),
        run_claude=lambda _wi: InvocationProviderResult(success=True, output_reference="unused"),
    )
    assert updated_item["status"] == WorkItemStatus.BLOCKED.value


def test_missing_trigger_artifact_leads_to_blocked(tmp_path: Path):
    queue_state, work_item_id, queue_state_path, trigger_rel, _ = _base_queue(tmp_path)
    (REPO_ROOT / trigger_rel).unlink(missing_ok=True)
    _, updated_item, _ = apply_live_review_invocation(
        queue_state=queue_state,
        work_item_id=work_item_id,
        queue_state_path=queue_state_path,
        repo_root=REPO_ROOT,
        run_codex=lambda _wi: InvocationProviderResult(success=True, output_reference="unused"),
        run_claude=lambda _wi: InvocationProviderResult(success=True, output_reference="unused"),
    )
    assert updated_item["status"] == WorkItemStatus.BLOCKED.value


def test_existing_invocation_result_path_prevents_duplicate_invocation(tmp_path: Path):
    queue_state, work_item_id, queue_state_path, _, _ = _base_queue(tmp_path)
    queue_state["work_items"][0]["review_invocation_result_artifact_path"] = "artifacts/prompt_queue/review_invocation_results/existing.json"
    _, updated_item, _ = apply_live_review_invocation(
        queue_state=queue_state,
        work_item_id=work_item_id,
        queue_state_path=queue_state_path,
        repo_root=REPO_ROOT,
        run_codex=lambda _wi: InvocationProviderResult(success=True, output_reference="unused"),
        run_claude=lambda _wi: InvocationProviderResult(success=True, output_reference="unused"),
    )
    assert updated_item["status"] == WorkItemStatus.BLOCKED.value


def test_artifact_write_failure_leads_to_blocked(tmp_path: Path):
    queue_state, work_item_id, queue_state_path, _, _ = _base_queue(tmp_path)
    _, updated_item, _ = apply_live_review_invocation(
        queue_state=queue_state,
        work_item_id=work_item_id,
        queue_state_path=queue_state_path,
        repo_root=REPO_ROOT,
        run_codex=lambda _wi: InvocationProviderResult(success=True, output_reference="artifacts/prompt_queue/reviews/missing.md"),
        run_claude=lambda _wi: InvocationProviderResult(success=True, output_reference="unused"),
    )
    assert updated_item["status"] == WorkItemStatus.BLOCKED.value


def test_queue_state_update_failure_after_artifact_write_retries_then_blocks(tmp_path: Path):
    queue_state, work_item_id, queue_state_path, _, output_rel = _base_queue(tmp_path)

    calls = {"n": 0}

    def persist_fail(_state):
        calls["n"] += 1
        raise RuntimeError("persist failed")

    _, updated_item, _ = apply_live_review_invocation(
        queue_state=queue_state,
        work_item_id=work_item_id,
        queue_state_path=queue_state_path,
        repo_root=REPO_ROOT,
        run_codex=_ok_provider(str(output_rel)),
        run_claude=_ok_provider(str(output_rel)),
        persist_queue_state=persist_fail,
    )
    assert calls["n"] == 2
    assert updated_item["status"] == WorkItemStatus.BLOCKED.value


def test_invocation_result_artifact_validates_against_schema(tmp_path: Path):
    queue_state, work_item_id, queue_state_path, _, output_rel = _base_queue(tmp_path)
    _, _, invocation_result = apply_live_review_invocation(
        queue_state=queue_state,
        work_item_id=work_item_id,
        queue_state_path=queue_state_path,
        repo_root=REPO_ROOT,
        run_codex=_ok_provider(str(output_rel)),
        run_claude=_ok_provider(str(output_rel)),
    )
    validate_review_invocation_result(invocation_result)


def test_deterministic_behavior_for_same_input_and_provider_outcome(tmp_path: Path):
    queue_state_1, work_item_id_1, queue_state_path_1, _, output_rel_1 = _base_queue(tmp_path)
    queue_state_2, work_item_id_2, queue_state_path_2, _, output_rel_2 = _base_queue(tmp_path)
    fixed_clock_values = ["2026-03-22T00:01:00Z", "2026-03-22T00:01:01Z", "2026-03-22T00:01:02Z", "2026-03-22T00:01:03Z"]

    _, _, result_1 = apply_live_review_invocation(
        queue_state=queue_state_1,
        work_item_id=work_item_id_1,
        queue_state_path=queue_state_path_1,
        repo_root=REPO_ROOT,
        run_codex=_ok_provider(str(output_rel_1)),
        run_claude=_ok_provider(str(output_rel_1)),
        clock=FixedClock(list(fixed_clock_values)),
    )
    _, _, result_2 = apply_live_review_invocation(
        queue_state=queue_state_2,
        work_item_id=work_item_id_2,
        queue_state_path=queue_state_path_2,
        repo_root=REPO_ROOT,
        run_codex=_ok_provider(str(output_rel_2)),
        run_claude=_ok_provider(str(output_rel_2)),
        clock=FixedClock(list(fixed_clock_values)),
    )

    assert result_1 == result_2
