from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.github_roadmap_builder import (
    GithubRoadmapBuilderError,
    build_two_step_roadmap_from_sources,
)


def _context(tmp_path: Path) -> dict[str, object]:
    return {
        "command_body": "/roadmap-draft scope:runtime keywords:governance,roadmap",
        "emitted_at": "2026-04-06T12:00:00Z",
        "repo_root": tmp_path,
        "pr_number": 42,
        "source_event_ref": "issue_comment:1",
    }


def _write_sources(tmp_path: Path) -> None:
    (tmp_path / "docs" / "roadmaps").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "vision.md").write_text("Vision governance constraints\n", encoding="utf-8")
    (tmp_path / "docs" / "roadmaps" / "system_roadmap.md").write_text("Roadmap governance runtime\n", encoding="utf-8")


def test_valid_command_builds_schema_backed_two_step_artifact(tmp_path: Path) -> None:
    _write_sources(tmp_path)

    artifact = build_two_step_roadmap_from_sources(_context(tmp_path))

    validate_artifact(artifact, "roadmap_two_step_artifact")
    assert artifact["bounded"] is True
    assert artifact["step_count"] == 2
    assert [step["step_id"] for step in artifact["steps"]] == ["step_1", "step_2"]


def test_deterministic_output_for_same_input(tmp_path: Path) -> None:
    _write_sources(tmp_path)
    context = _context(tmp_path)

    one = build_two_step_roadmap_from_sources(context)
    two = build_two_step_roadmap_from_sources(context)

    assert one == two


def test_missing_source_docs_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "vision.md").write_text("only one source\n", encoding="utf-8")

    with pytest.raises(GithubRoadmapBuilderError, match="required source doc is missing"):
        build_two_step_roadmap_from_sources(_context(tmp_path))


def test_invalid_command_marker_fails_closed(tmp_path: Path) -> None:
    _write_sources(tmp_path)
    context = _context(tmp_path)
    context["command_body"] = "/run-ril"

    with pytest.raises(GithubRoadmapBuilderError, match="/roadmap-draft"):
        build_two_step_roadmap_from_sources(context)
