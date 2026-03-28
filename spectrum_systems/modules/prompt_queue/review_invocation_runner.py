"""Pure live review invocation runner (validation + provider boundary, no queue mutation)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now
from spectrum_systems.modules.prompt_queue.review_invocation_entry_validation import validate_review_invocation_entry
from spectrum_systems.modules.prompt_queue.review_invocation_provider_adapter import (
    InvocationProviderOutcome,
    InvocationProviderResult,
    invoke_review_provider,
)


ProviderRunner = Callable[[dict], InvocationProviderResult]


def build_invocation_id(*, work_item_id: str, review_trigger_artifact_path: str) -> str:
    raw = f"{work_item_id}|{review_trigger_artifact_path}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return f"inv-{digest[:16]}"


def run_live_review_invocation(
    *,
    work_item: dict,
    repo_root: Path,
    run_codex: ProviderRunner,
    run_claude: ProviderRunner,
    lineage_context: dict | None = None,
    clock=utc_now,
) -> tuple[dict, InvocationProviderOutcome]:
    lineage = lineage_context or validate_review_invocation_entry(work_item=work_item, repo_root=repo_root)
    started_at = iso_now(clock)
    provider_outcome = invoke_review_provider(work_item=work_item, run_codex=run_codex, run_claude=run_claude)
    completed_at = iso_now(clock)

    invocation_result = {
        "review_invocation_result_artifact_id": f"review-invocation-result-{work_item['work_item_id']}",
        "invocation_id": build_invocation_id(
            work_item_id=work_item["work_item_id"],
            review_trigger_artifact_path=lineage["review_trigger_artifact_path"],
        ),
        "work_item_id": work_item["work_item_id"],
        "parent_work_item_id": work_item.get("parent_work_item_id"),
        "review_trigger_artifact_path": lineage["review_trigger_artifact_path"],
        "execution_result_artifact_path": lineage["execution_result_artifact_path"],
        "provider_requested": provider_outcome.provider_requested,
        "provider_used": provider_outcome.provider_used,
        "fallback_used": provider_outcome.fallback_used,
        "fallback_reason": provider_outcome.fallback_reason,
        "invocation_status": provider_outcome.invocation_status,
        "started_at": started_at,
        "completed_at": completed_at,
        "generated_at": completed_at,
        "generator_version": "prompt_queue_live_review_invocation.v1",
        "output_reference": provider_outcome.output_reference,
        "error_summary": provider_outcome.error_summary,
    }
    return invocation_result, provider_outcome


def run_review_invocation_step_adapter(
    *,
    step: dict,
    queue_state: dict,
    work_item: dict,
    repo_root: Path,
    run_codex: ProviderRunner,
    run_claude: ProviderRunner,
    lineage_context: dict | None = None,
    clock=utc_now,
) -> tuple[dict, InvocationProviderOutcome]:
    """Normalized review-invocation adapter compatible with queue-step execution boundary."""

    step_id = step.get("step_id")
    if not isinstance(step_id, str) or not step_id:
        raise ValueError("Review invocation adapter requires step_id.")
    queue_id = queue_state.get("queue_id")
    if not isinstance(queue_id, str) or not queue_id:
        raise ValueError("Review invocation adapter requires queue_state.queue_id.")

    invocation_result, provider_outcome = run_live_review_invocation(
        work_item=work_item,
        repo_root=repo_root,
        run_codex=run_codex,
        run_claude=run_claude,
        lineage_context=lineage_context,
        clock=clock,
    )
    normalized = dict(invocation_result)
    normalized.update(
        {
            "step_id": step_id,
            "queue_id": queue_id,
            "execution_type": "review_invocation",
        }
    )
    return normalized, provider_outcome
