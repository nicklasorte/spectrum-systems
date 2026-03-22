"""Artifact IO boundary for findings-to-repair reentry artifacts."""

from __future__ import annotations

from pathlib import Path

from spectrum_systems.modules.prompt_queue.queue_artifact_io import validate_findings_reentry, write_artifact


class FindingsReentryArtifactIOError(ValueError):
    """Raised when findings reentry artifact validation/write fails."""


def default_findings_reentry_path(*, work_item_id: str, root_dir: Path) -> Path:
    return root_dir / "artifacts" / "prompt_queue" / "findings_reentries" / f"{work_item_id}.findings_reentry.json"


def write_findings_reentry_artifact(*, artifact: dict, output_path: Path) -> Path:
    try:
        validate_findings_reentry(artifact)
    except ValueError as exc:
        raise FindingsReentryArtifactIOError(str(exc)) from exc

    try:
        return write_artifact(artifact, output_path)
    except OSError as exc:
        raise FindingsReentryArtifactIOError(f"Failed to write findings reentry artifact: {output_path}") from exc
