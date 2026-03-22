"""Artifact IO boundary for prompt queue review invocation results."""

from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.modules.prompt_queue.queue_artifact_io import validate_review_invocation_result


class ReviewInvocationArtifactIOError(ValueError):
    """Raised when invocation artifact validation or write fails."""


def default_review_invocation_result_path(*, work_item_id: str, queue_state_path: Path) -> Path:
    return queue_state_path.parent / "review_invocation_results" / f"{queue_state_path.stem}.{work_item_id}.review_invocation_result.json"


def _validate_cross_field_invariants(*, artifact: dict, repo_root: Path) -> None:
    fallback_used = artifact.get("fallback_used")
    fallback_reason = artifact.get("fallback_reason")
    if fallback_used and fallback_reason is None:
        raise ReviewInvocationArtifactIOError("Invariant failed: fallback_used=true requires non-null fallback_reason.")
    if not fallback_used and fallback_reason is not None:
        raise ReviewInvocationArtifactIOError("Invariant failed: fallback_used=false requires fallback_reason=null.")

    status = artifact.get("invocation_status")
    output_reference = artifact.get("output_reference")
    if status == "success" and not output_reference:
        raise ReviewInvocationArtifactIOError("Invariant failed: invocation_status=success requires non-null output_reference.")
    if status == "success":
        output_path = repo_root / output_reference
        if not output_path.exists():
            raise ReviewInvocationArtifactIOError("Invariant failed: success output_reference must point to a readable artifact.")


def write_review_invocation_result_artifact(*, artifact: dict, output_path: Path, repo_root: Path) -> Path:
    _validate_cross_field_invariants(artifact=artifact, repo_root=repo_root)
    try:
        validate_review_invocation_result(artifact)
    except ValueError as exc:
        raise ReviewInvocationArtifactIOError(str(exc)) from exc

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(artifact, handle, indent=2)
    except OSError as exc:
        raise ReviewInvocationArtifactIOError(f"Failed to write invocation result artifact: {output_path}") from exc
    return output_path
