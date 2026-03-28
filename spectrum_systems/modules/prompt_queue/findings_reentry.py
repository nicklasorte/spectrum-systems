"""Deterministic fail-closed findings-to-repair reentry wiring."""

from __future__ import annotations

from typing import Callable

from spectrum_systems.modules.prompt_queue.findings_artifact_io import validate_findings_artifact
from spectrum_systems.modules.prompt_queue.queue_artifact_io import (
    validate_findings_reentry,
    validate_review_invocation_result,
    validate_review_parsing_handoff,
)
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now
from spectrum_systems.modules.prompt_queue.repair_prompt_generator import (
    RepairPromptGenerationError,
    generate_repair_prompt_artifact,
)

GENERATOR_VERSION = "prompt_queue_findings_reentry.v1"


class FindingsReentryError(ValueError):
    """Raised when findings-to-repair reentry fails closed."""


def _build_reentry_artifact_id(work_item_id: str, generated_at: str) -> str:
    stamp = generated_at.replace("-", "").replace(":", "")
    return f"findings-reentry-{work_item_id}-{stamp}"


def _validate_lineage(
    *,
    work_item: dict,
    findings_artifact: dict,
    findings_artifact_path: str,
    review_parsing_handoff_artifact: dict,
    review_parsing_handoff_artifact_path: str,
    review_invocation_result_artifact: dict,
    review_invocation_result_artifact_path: str,
) -> None:
    expected_work_item_id = work_item.get("work_item_id")
    expected_parent_id = work_item.get("parent_work_item_id")

    if findings_artifact.get("work_item_id") != expected_work_item_id:
        raise FindingsReentryError("Invalid lineage: findings work_item_id mismatch.")
    if review_parsing_handoff_artifact.get("work_item_id") != expected_work_item_id:
        raise FindingsReentryError("Invalid lineage: handoff work_item_id mismatch.")
    if review_parsing_handoff_artifact.get("parent_work_item_id") != expected_parent_id:
        raise FindingsReentryError("Invalid lineage: handoff parent_work_item_id mismatch.")
    if review_invocation_result_artifact.get("work_item_id") != expected_work_item_id:
        raise FindingsReentryError("Invalid lineage: invocation result work_item_id mismatch.")
    if review_invocation_result_artifact.get("parent_work_item_id") != expected_parent_id:
        raise FindingsReentryError("Invalid lineage: invocation result parent_work_item_id mismatch.")
    if review_invocation_result_artifact.get("invocation_status") != "success":
        raise FindingsReentryError("Invalid lineage: invocation result is not successful.")

    if review_parsing_handoff_artifact.get("findings_artifact_path") != findings_artifact_path:
        raise FindingsReentryError("Invalid lineage: findings artifact path mismatch against handoff artifact.")
    if (
        review_parsing_handoff_artifact.get("review_invocation_result_artifact_path")
        != review_invocation_result_artifact_path
    ):
        raise FindingsReentryError("Invalid lineage: invocation result path mismatch against handoff artifact.")

    if work_item.get("review_parsing_handoff_artifact_path") not in (None, review_parsing_handoff_artifact_path):
        raise FindingsReentryError("Invalid lineage: work item review_parsing_handoff_artifact_path mismatch.")
    if work_item.get("review_invocation_result_artifact_path") not in (None, review_invocation_result_artifact_path):
        raise FindingsReentryError("Invalid lineage: work item review_invocation_result_artifact_path mismatch.")

    if findings_artifact.get("source_review_artifact_path") != review_parsing_handoff_artifact.get("output_reference"):
        raise FindingsReentryError("Invalid lineage: findings source_review_artifact_path mismatch.")


def run_findings_reentry(
    *,
    work_item: dict,
    findings_artifact: dict,
    findings_artifact_path: str,
    review_parsing_handoff_artifact: dict,
    review_parsing_handoff_artifact_path: str,
    review_invocation_result_artifact: dict,
    review_invocation_result_artifact_path: str,
    repair_prompt_artifact_path: str,
    source_queue_state_path: str | None = None,
    clock: Callable = utc_now,
) -> dict:
    """Validate lineage and route findings through existing repair prompt generation."""
    validate_findings_artifact(findings_artifact)
    validate_review_parsing_handoff(review_parsing_handoff_artifact)
    validate_review_invocation_result(review_invocation_result_artifact)

    if not findings_artifact_path:
        raise FindingsReentryError("Missing findings artifact path.")
    if not review_parsing_handoff_artifact_path:
        raise FindingsReentryError("Missing review parsing handoff artifact path.")
    if not review_invocation_result_artifact_path:
        raise FindingsReentryError("Missing review invocation result artifact path.")
    if not repair_prompt_artifact_path:
        raise FindingsReentryError("Missing repair prompt artifact path.")
    if findings_artifact.get("review_decision") != "FAIL":
        raise FindingsReentryError("Findings reentry only supports FAIL findings artifacts.")
    if not findings_artifact.get("required_fixes"):
        raise FindingsReentryError("Findings reentry requires at least one required fix.")

    _validate_lineage(
        work_item=work_item,
        findings_artifact=findings_artifact,
        findings_artifact_path=findings_artifact_path,
        review_parsing_handoff_artifact=review_parsing_handoff_artifact,
        review_parsing_handoff_artifact_path=review_parsing_handoff_artifact_path,
        review_invocation_result_artifact=review_invocation_result_artifact,
        review_invocation_result_artifact_path=review_invocation_result_artifact_path,
    )

    try:
        repair_prompt_artifact = generate_repair_prompt_artifact(
            work_item=work_item,
            findings_artifact=findings_artifact,
            source_findings_artifact_path=findings_artifact_path,
            clock=clock,
        )
    except RepairPromptGenerationError as exc:
        raise FindingsReentryError(f"Repair prompt generation failed: {exc}") from exc

    generated_at = iso_now(clock)
    reentry_artifact = {
        "findings_reentry_artifact_id": _build_reentry_artifact_id(work_item["work_item_id"], generated_at),
        "work_item_id": work_item["work_item_id"],
        "parent_work_item_id": work_item.get("parent_work_item_id"),
        "review_parsing_handoff_artifact_path": review_parsing_handoff_artifact_path,
        "review_invocation_result_artifact_path": review_invocation_result_artifact_path,
        "findings_artifact_path": findings_artifact_path,
        "repair_prompt_artifact_path": repair_prompt_artifact_path,
        "reentry_status": "reentry_completed",
        "reentry_reason_code": "reentry_completed_repair_prompt_generated",
        "source_queue_state_path": source_queue_state_path,
        "warnings": [],
        "blocking_conditions": [],
        "generated_at": generated_at,
        "generator_version": GENERATOR_VERSION,
    }
    validate_findings_reentry(reentry_artifact)

    return {"repair_prompt_artifact": repair_prompt_artifact, "reentry_artifact": reentry_artifact}
