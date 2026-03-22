"""Queue integration for bounded live review invocation with mandatory write ordering."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from spectrum_systems.modules.prompt_queue.queue_artifact_io import validate_queue_state, validate_work_item
from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, utc_now
from spectrum_systems.modules.prompt_queue.queue_state_machine import IllegalTransitionError, transition_work_item
from spectrum_systems.modules.prompt_queue.review_invocation_artifact_io import (
    ReviewInvocationArtifactIOError,
    default_review_invocation_result_path,
    write_review_invocation_result_artifact,
)
from spectrum_systems.modules.prompt_queue.review_invocation_entry_validation import (
    ReviewInvocationEntryValidationError,
    validate_review_invocation_entry,
)
from spectrum_systems.modules.prompt_queue.review_invocation_provider_adapter import InvocationProviderResult
from spectrum_systems.modules.prompt_queue.review_invocation_runner import run_live_review_invocation


class ReviewInvocationQueueIntegrationError(ValueError):
    """Raised when live review invocation queue integration fails closed."""


PersistQueueState = Callable[[dict], None]
ProviderRunner = Callable[[dict], InvocationProviderResult]


def _find_work_item_index(queue_state: dict, work_item_id: str) -> int:
    for idx, item in enumerate(queue_state.get("work_items", [])):
        if item.get("work_item_id") == work_item_id:
            return idx
    raise ReviewInvocationQueueIntegrationError(f"Work item '{work_item_id}' not found in queue state.")


def _block_item(queue_state: dict, idx: int, *, reason: str, clock=utc_now) -> tuple[dict, dict]:
    target = dict(queue_state["work_items"][idx])
    try:
        blocked = transition_work_item(target, WorkItemStatus.BLOCKED.value, clock=clock)
    except IllegalTransitionError as exc:
        raise ReviewInvocationQueueIntegrationError(f"{reason} Unable to transition to blocked: {exc}") from exc
    queue_state["work_items"][idx] = blocked
    queue_state["updated_at"] = iso_now(clock)
    return queue_state, blocked


def apply_live_review_invocation(
    *,
    queue_state: dict,
    work_item_id: str,
    queue_state_path: Path,
    repo_root: Path,
    run_codex: ProviderRunner,
    run_claude: ProviderRunner,
    persist_queue_state: PersistQueueState | None = None,
    clock=utc_now,
) -> tuple[dict, dict, dict]:
    queue_copy = dict(queue_state)
    queue_copy["work_items"] = [dict(item) for item in queue_state.get("work_items", [])]
    idx = _find_work_item_index(queue_copy, work_item_id)

    # 1) assert no prior invocation + 2) validate trigger lineage
    try:
        lineage_context = validate_review_invocation_entry(work_item=queue_copy["work_items"][idx], repo_root=repo_root)
    except ReviewInvocationEntryValidationError as exc:
        queue_copy, blocked = _block_item(queue_copy, idx, reason="Entry validation failed.", clock=clock)
        validate_work_item(blocked)
        validate_queue_state(queue_copy)
        return queue_copy, blocked, {"invocation_status": "failure", "error_summary": str(exc)}

    # 3) transition to review_invoking
    invoking = transition_work_item(queue_copy["work_items"][idx], WorkItemStatus.REVIEW_INVOKING.value, clock=clock)
    queue_copy["work_items"][idx] = invoking
    queue_copy["updated_at"] = iso_now(clock)

    # 4) invoke provider
    invocation_result, provider_outcome = run_live_review_invocation(
        work_item=invoking,
        repo_root=repo_root,
        run_codex=run_codex,
        run_claude=run_claude,
        lineage_context=lineage_context,
        clock=clock,
    )

    if provider_outcome.invocation_status == "failure" and invocation_result.get("output_reference") is None:
        failed = transition_work_item(invoking, WorkItemStatus.REVIEW_INVOCATION_FAILED.value, clock=clock)
        queue_copy["work_items"][idx] = failed
        queue_copy["updated_at"] = iso_now(clock)
        validate_work_item(failed)
        validate_queue_state(queue_copy)
        return queue_copy, failed, invocation_result

    # 5) write schema-valid invocation result artifact
    artifact_path = default_review_invocation_result_path(work_item_id=work_item_id, queue_state_path=queue_state_path)
    try:
        written = write_review_invocation_result_artifact(
            artifact=invocation_result,
            output_path=artifact_path,
            repo_root=repo_root,
        )
    except ReviewInvocationArtifactIOError as exc:
        queue_copy, blocked = _block_item(queue_copy, idx, reason="Artifact write failed.", clock=clock)
        validate_work_item(blocked)
        validate_queue_state(queue_copy)
        return queue_copy, blocked, {"invocation_status": "failure", "error_summary": str(exc)}

    # 6) persist review_invocation_result_artifact_path
    invoking = dict(queue_copy["work_items"][idx])
    try:
        persisted_path = str(written.relative_to(repo_root))
    except ValueError:
        persisted_path = str(written)
    invoking["review_invocation_result_artifact_path"] = persisted_path
    invoking["updated_at"] = iso_now(clock)
    queue_copy["work_items"][idx] = invoking
    queue_copy["updated_at"] = iso_now(clock)

    if persist_queue_state is not None:
        try:
            persist_queue_state(queue_copy)
        except Exception:
            try:
                persist_queue_state(queue_copy)
            except Exception:
                queue_copy, blocked = _block_item(queue_copy, idx, reason="Queue persistence failed after artifact write.", clock=clock)
                validate_work_item(blocked)
                validate_queue_state(queue_copy)
                return queue_copy, blocked, invocation_result

    # 7) transition to terminal state
    terminal_status = (
        WorkItemStatus.REVIEW_INVOCATION_SUCCEEDED.value
        if invocation_result["invocation_status"] == "success"
        else WorkItemStatus.REVIEW_INVOCATION_FAILED.value
    )
    terminal = transition_work_item(invoking, terminal_status, clock=clock)
    queue_copy["work_items"][idx] = terminal
    queue_copy["updated_at"] = iso_now(clock)

    validate_work_item(terminal)
    validate_queue_state(queue_copy)
    return queue_copy, terminal, invocation_result
