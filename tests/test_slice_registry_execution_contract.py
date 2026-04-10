from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.roadmap_slice_registry import (
    RoadmapSliceRegistryError,
    load_slice_registry,
)


_FIXTURE_ROOT = Path("contracts/roadmap")


def _write_registry(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "slice_registry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_each_slice_has_actionable_execution_contract() -> None:
    slices = load_slice_registry(_FIXTURE_ROOT / "slice_registry.json")

    assert slices
    for row in slices:
        assert any(not command.strip().startswith("pytest ") for command in row["commands"])
        assert "inferred from canonical roadmap" not in row["implementation_notes"].lower()


def test_generic_only_commands_fail(tmp_path: Path) -> None:
    payload = json.loads((_FIXTURE_ROOT / "slice_registry.json").read_text(encoding="utf-8"))
    payload["slices"][0]["commands"] = ["pytest tests/test_roadmap_slice_registry.py -q"]

    with pytest.raises(RoadmapSliceRegistryError, match="all commands are generic validation commands"):
        load_slice_registry(_write_registry(tmp_path, payload))


def test_self_referential_first_command_fails(tmp_path: Path) -> None:
    payload = json.loads((_FIXTURE_ROOT / "slice_registry.json").read_text(encoding="utf-8"))
    payload["slices"][0]["commands"] = [
        "python -c \"from spectrum_systems.modules.runtime.roadmap_slice_registry import load_slice_registry; rows=load_slice_registry('contracts/roadmap/slice_registry.json'); row=rows[0]; assert row['slice_id']\"",
        "pytest tests/test_execution_hierarchy.py -q",
    ]

    with pytest.raises(
        RoadmapSliceRegistryError, match="first command is self-referential registry metadata checking"
    ):
        load_slice_registry(_write_registry(tmp_path, payload))


def test_generic_implementation_notes_fail(tmp_path: Path) -> None:
    payload = json.loads((_FIXTURE_ROOT / "slice_registry.json").read_text(encoding="utf-8"))
    payload["slices"][0]["implementation_notes"] = (
        "Inferred from canonical roadmap batch intent; keep behavior artifact-first and fail-closed."
    )

    with pytest.raises(RoadmapSliceRegistryError, match="implementation_notes"):
        load_slice_registry(_write_registry(tmp_path, payload))


def test_duplicate_family_command_sets_fail(tmp_path: Path) -> None:
    payload = json.loads((_FIXTURE_ROOT / "slice_registry.json").read_text(encoding="utf-8"))
    payload["slices"][1]["commands"] = list(payload["slices"][0]["commands"])

    with pytest.raises(RoadmapSliceRegistryError, match="duplicated command set"):
        load_slice_registry(_write_registry(tmp_path, payload))


def test_boilerplate_notes_repeated_within_family_fail(tmp_path: Path) -> None:
    payload = json.loads((_FIXTURE_ROOT / "slice_registry.json").read_text(encoding="utf-8"))
    payload["slices"][1]["implementation_notes"] = payload["slices"][0]["implementation_notes"]

    with pytest.raises(RoadmapSliceRegistryError, match="duplicated boilerplate notes"):
        load_slice_registry(_write_registry(tmp_path, payload))


def test_mismatched_execution_type_fails(tmp_path: Path) -> None:
    payload = json.loads((_FIXTURE_ROOT / "slice_registry.json").read_text(encoding="utf-8"))
    payload["slices"][0]["execution_type"] = "repair"
    payload["slices"][0]["commands"] = [
        "python -c \"print('validate only')\"",
        "pytest tests/test_execution_hierarchy.py -q",
    ]

    with pytest.raises(RoadmapSliceRegistryError, match="does not match command intent"):
        load_slice_registry(_write_registry(tmp_path, payload))


def test_valid_slice_passes(tmp_path: Path) -> None:
    payload = json.loads((_FIXTURE_ROOT / "slice_registry.json").read_text(encoding="utf-8"))
    payload["slices"][0]["execution_type"] = "validation"
    payload["slices"][0]["commands"] = [
        "python -c \"import json; from spectrum_systems.modules.runtime.execution_hierarchy import validate_execution_hierarchy; validate_execution_hierarchy(json.load(open('contracts/roadmap/roadmap_structure.json')), label='aex_valid')\"",
        "pytest tests/test_execution_hierarchy.py -q",
    ]
    payload["slices"][0]["implementation_notes"] = (
        "Behavior exercised: run admission structure validation. "
        "Artifact/module/flow touched: execution hierarchy on roadmap_structure artifact. "
        "Fail-closed condition: stop when hierarchy validation fails or required fields are missing. "
        "Expected outcome: deterministic behavior command passes before targeted pytest validation."
    )

    loaded = load_slice_registry(_write_registry(tmp_path, payload))
    assert loaded
