"""Artifact IO boundary for prompt queue loop continuation artifacts."""

from __future__ import annotations

from pathlib import Path

from spectrum_systems.modules.prompt_queue.queue_artifact_io import validate_loop_continuation, write_artifact


class LoopContinuationArtifactIOError(ValueError):
    """Raised when loop continuation artifact validation/write fails."""


def default_loop_continuation_path(*, work_item_id: str, root_dir: Path) -> Path:
    return root_dir / "artifacts" / "prompt_queue" / "loop_continuations" / f"{work_item_id}.loop_continuation.json"


def write_loop_continuation_artifact(*, artifact: dict, output_path: Path) -> Path:
    try:
        validate_loop_continuation(artifact)
    except ValueError as exc:
        raise LoopContinuationArtifactIOError(str(exc)) from exc

    try:
        return write_artifact(artifact, output_path)
    except OSError as exc:
        raise LoopContinuationArtifactIOError(f"Failed to write loop continuation artifact: {output_path}") from exc
