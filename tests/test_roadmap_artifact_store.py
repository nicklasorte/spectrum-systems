from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example, load_schema  # noqa: E402
from spectrum_systems.modules.runtime.roadmap_artifact_store import (  # noqa: E402
    RoadmapArtifactStoreError,
    read_roadmap_artifact,
    validate_roadmap_artifact,
    write_roadmap_artifact,
)


def _artifact() -> dict:
    return copy.deepcopy(load_example("roadmap_artifact"))


def test_roadmap_artifact_schema_example_validates() -> None:
    validator = Draft202012Validator(load_schema("roadmap_artifact"), format_checker=FormatChecker())
    validator.validate(_artifact())


def test_invalid_roadmap_artifact_fails_closed() -> None:
    artifact = _artifact()
    artifact["batches"][0].pop("status")
    with pytest.raises(RoadmapArtifactStoreError, match="schema validation"):
        validate_roadmap_artifact(artifact)


def test_repo_source_ref_requires_trace_link() -> None:
    artifact = _artifact()
    artifact["source_ref"] = "nicklasorte/spectrum-systems@main"
    with pytest.raises(RoadmapArtifactStoreError, match="trace link"):
        validate_roadmap_artifact(artifact)


def test_roadmap_artifact_storage_round_trip(tmp_path: Path) -> None:
    artifact = _artifact()
    output = tmp_path / "artifacts" / "roadmap" / "roadmap_artifact.json"
    write_roadmap_artifact(artifact, output)
    loaded = read_roadmap_artifact(output)
    assert loaded == json.loads(json.dumps(artifact, sort_keys=True))


def test_roadmap_artifact_write_is_deterministic(tmp_path: Path) -> None:
    artifact = _artifact()
    output = tmp_path / "deterministic" / "roadmap_artifact.json"
    write_roadmap_artifact(artifact, output)
    first = output.read_text(encoding="utf-8")
    write_roadmap_artifact(artifact, output)
    second = output.read_text(encoding="utf-8")
    assert first == second


def test_roadmap_artifact_example_passes_store_validation() -> None:
    validate_roadmap_artifact(_artifact())
