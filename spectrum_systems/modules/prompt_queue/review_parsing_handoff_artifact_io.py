"""Artifact IO boundary for review parsing handoff artifacts."""

from __future__ import annotations

from pathlib import Path

from spectrum_systems.modules.prompt_queue.queue_artifact_io import validate_review_parsing_handoff, write_artifact


class ReviewParsingHandoffArtifactIOError(ValueError):
    """Raised when handoff artifact validation or write fails."""


def default_review_parsing_handoff_path(*, work_item_id: str, queue_state_path: Path) -> Path:
    return (
        queue_state_path.parent
        / "review_parsing_handoffs"
        / f"{queue_state_path.stem}.{work_item_id}.review_parsing_handoff.json"
    )


def write_review_parsing_handoff_artifact(*, artifact: dict, output_path: Path) -> Path:
    try:
        validate_review_parsing_handoff(artifact)
    except ValueError as exc:
        raise ReviewParsingHandoffArtifactIOError(str(exc)) from exc

    try:
        return write_artifact(artifact, output_path)
    except OSError as exc:
        raise ReviewParsingHandoffArtifactIOError(f"Failed to write handoff artifact: {output_path}") from exc
