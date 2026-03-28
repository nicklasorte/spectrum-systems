"""Deterministic fail-closed handoff from review invocation output to findings parsing."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from spectrum_systems.modules.prompt_queue.execution_artifact_io import read_execution_result_artifact
from spectrum_systems.modules.prompt_queue.findings_normalizer import build_findings_artifact, default_findings_path
from spectrum_systems.modules.prompt_queue.queue_artifact_io import validate_review_invocation_result
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now
from spectrum_systems.modules.prompt_queue.review_parser import ReviewParseError, parse_queue_step_report, parse_review_markdown
from spectrum_systems.modules.prompt_queue.step_decision import build_step_decision, default_step_decision_path

GENERATOR_VERSION = "prompt_queue_review_parsing_handoff.v2"


class ReviewParsingHandoffError(ValueError):
    """Raised when invocation output cannot be safely handed off to parsing."""


def _build_handoff_artifact_id(work_item_id: str, generated_at: str) -> str:
    stamp = generated_at.replace("-", "").replace(":", "")
    return f"review-parsing-handoff-{work_item_id}-{stamp}"


def _relative_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _validate_lineage(*, work_item: dict, invocation_result: dict) -> None:
    if invocation_result.get("work_item_id") != work_item.get("work_item_id"):
        raise ReviewParsingHandoffError("Invalid lineage: invocation work_item_id does not match queue work item.")
    if invocation_result.get("parent_work_item_id") != work_item.get("parent_work_item_id"):
        raise ReviewParsingHandoffError("Invalid lineage: invocation parent_work_item_id does not match queue work item.")
    if invocation_result.get("review_trigger_artifact_path") != work_item.get("review_trigger_artifact_path"):
        raise ReviewParsingHandoffError("Invalid lineage: invocation review_trigger_artifact_path mismatch.")


def run_review_parsing_handoff(
    *,
    work_item: dict,
    review_invocation_result: dict,
    review_invocation_result_artifact_path: str,
    repo_root: Path,
    source_queue_state_path: str | None = None,
    clock: Callable = utc_now,
) -> dict:
    """Validate lineage and parse review output into deterministic handoff + findings + decision payloads."""
    validate_review_invocation_result(review_invocation_result)
    _validate_lineage(work_item=work_item, invocation_result=review_invocation_result)

    if review_invocation_result.get("invocation_status") != "success":
        raise ReviewParsingHandoffError("Invocation result is not successful; handoff denied.")

    output_reference = review_invocation_result.get("output_reference")
    if not output_reference:
        raise ReviewParsingHandoffError("Invocation success is missing required output_reference.")

    output_path = repo_root / output_reference
    if not output_path.exists():
        raise ReviewParsingHandoffError("Referenced review output artifact is missing.")
    if not output_path.is_file():
        raise ReviewParsingHandoffError("Referenced review output artifact path is not a readable file.")

    try:
        markdown = output_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReviewParsingHandoffError("Referenced review output artifact is unreadable.") from exc

    try:
        parsed_review = parse_review_markdown(markdown, provider=review_invocation_result["provider_used"])
    except ReviewParseError as exc:
        raise ReviewParsingHandoffError(f"Review parser failure: {exc}") from exc

    findings_rel_path = _relative_path(
        default_findings_path(work_item_id=work_item["work_item_id"], root_dir=repo_root),
        repo_root,
    )

    findings_artifact = build_findings_artifact(
        work_item=work_item,
        parsed_review=parsed_review,
        source_review_artifact_path=output_reference,
        clock=clock,
    )

    execution_result_path = review_invocation_result.get("execution_result_artifact_path")
    if not execution_result_path:
        raise ReviewParsingHandoffError("Invocation result is missing execution_result_artifact_path.")

    queue_step_report = parse_queue_step_report(read_execution_result_artifact(repo_root / execution_result_path))
    step_decision_artifact = build_step_decision(queue_step_report, clock=clock)
    decision_rel_path = _relative_path(default_step_decision_path(step_id=queue_step_report["step_id"], root_dir=repo_root), repo_root)

    generated_at = iso_now(clock)
    handoff_artifact = {
        "review_parsing_handoff_artifact_id": _build_handoff_artifact_id(work_item["work_item_id"], generated_at),
        "work_item_id": work_item["work_item_id"],
        "parent_work_item_id": work_item.get("parent_work_item_id"),
        "review_invocation_result_artifact_path": review_invocation_result_artifact_path,
        "review_trigger_artifact_path": review_invocation_result["review_trigger_artifact_path"],
        "output_reference": output_reference,
        "findings_artifact_path": findings_rel_path,
        "step_decision_artifact_path": decision_rel_path,
        "handoff_status": "handoff_completed",
        "handoff_reason_code": "handoff_completed_findings_emitted",
        "source_queue_state_path": source_queue_state_path,
        "warnings": [],
        "blocking_conditions": [],
        "generated_at": generated_at,
        "generator_version": GENERATOR_VERSION,
    }
    return {
        "handoff_artifact": handoff_artifact,
        "findings_artifact": findings_artifact,
        "findings_artifact_path": findings_rel_path,
        "step_decision_artifact": step_decision_artifact,
        "step_decision_artifact_path": decision_rel_path,
    }
