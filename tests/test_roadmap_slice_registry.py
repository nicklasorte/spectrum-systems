from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.roadmap_slice_registry import (
    RoadmapSliceRegistryError,
    load_governed_slice_registry_artifacts,
)


_FIXTURE_ROOT = Path("contracts/roadmap")


def test_valid_registry_and_structure_load_successfully() -> None:
    slices, structure = load_governed_slice_registry_artifacts(
        slice_registry_path=_FIXTURE_ROOT / "slice_registry.json",
        roadmap_structure_path=_FIXTURE_ROOT / "roadmap_structure.json",
    )

    assert slices
    assert structure["umbrellas"]


def test_loader_returns_deterministic_ordering() -> None:
    slices_a, structure_a = load_governed_slice_registry_artifacts(
        slice_registry_path=_FIXTURE_ROOT / "slice_registry.json",
        roadmap_structure_path=_FIXTURE_ROOT / "roadmap_structure.json",
    )
    slices_b, structure_b = load_governed_slice_registry_artifacts(
        slice_registry_path=_FIXTURE_ROOT / "slice_registry.json",
        roadmap_structure_path=_FIXTURE_ROOT / "roadmap_structure.json",
    )

    assert [row["slice_id"] for row in slices_a] == sorted(row["slice_id"] for row in slices_a)
    assert slices_a == slices_b
    assert structure_a == structure_b


def test_orphan_slice_reference_fails(tmp_path: Path) -> None:
    bad_structure = json.loads((_FIXTURE_ROOT / "roadmap_structure.json").read_text(encoding="utf-8"))
    bad_structure["umbrellas"][0]["batches"][0]["slice_ids"].append("NOT-REAL-01")
    structure_path = tmp_path / "roadmap_structure.json"
    structure_path.write_text(json.dumps(bad_structure), encoding="utf-8")

    with pytest.raises(RoadmapSliceRegistryError, match="unknown slice_id"):
        load_governed_slice_registry_artifacts(
            slice_registry_path=_FIXTURE_ROOT / "slice_registry.json",
            roadmap_structure_path=structure_path,
        )


def test_duplicate_slice_id_fails(tmp_path: Path) -> None:
    bad_registry = json.loads((_FIXTURE_ROOT / "slice_registry.json").read_text(encoding="utf-8"))
    bad_registry["slices"].append(dict(bad_registry["slices"][0]))
    registry_path = tmp_path / "slice_registry.json"
    registry_path.write_text(json.dumps(bad_registry), encoding="utf-8")

    with pytest.raises(RoadmapSliceRegistryError, match="duplicate slice_id"):
        load_governed_slice_registry_artifacts(
            slice_registry_path=registry_path,
            roadmap_structure_path=_FIXTURE_ROOT / "roadmap_structure.json",
        )


def test_single_slice_batch_fails(tmp_path: Path) -> None:
    bad_structure = json.loads((_FIXTURE_ROOT / "roadmap_structure.json").read_text(encoding="utf-8"))
    bad_structure["umbrellas"][0]["batches"][0]["slice_ids"] = ["AEX-01"]
    structure_path = tmp_path / "roadmap_structure.json"
    structure_path.write_text(json.dumps(bad_structure), encoding="utf-8")

    with pytest.raises(RoadmapSliceRegistryError, match="at least 2 slices"):
        load_governed_slice_registry_artifacts(
            slice_registry_path=_FIXTURE_ROOT / "slice_registry.json",
            roadmap_structure_path=structure_path,
        )


def test_single_batch_umbrella_fails(tmp_path: Path) -> None:
    bad_structure = json.loads((_FIXTURE_ROOT / "roadmap_structure.json").read_text(encoding="utf-8"))
    bad_structure["umbrellas"][0]["batches"] = bad_structure["umbrellas"][0]["batches"][:1]
    structure_path = tmp_path / "roadmap_structure.json"
    structure_path.write_text(json.dumps(bad_structure), encoding="utf-8")

    with pytest.raises(RoadmapSliceRegistryError, match="at least 2 batches"):
        load_governed_slice_registry_artifacts(
            slice_registry_path=_FIXTURE_ROOT / "slice_registry.json",
            roadmap_structure_path=structure_path,
        )


def test_implementation_metadata_presence_is_enforced(tmp_path: Path) -> None:
    bad_registry = json.loads((_FIXTURE_ROOT / "slice_registry.json").read_text(encoding="utf-8"))
    bad_registry["slices"][0]["implementation_notes"] = ""
    registry_path = tmp_path / "slice_registry.json"
    registry_path.write_text(json.dumps(bad_registry), encoding="utf-8")

    with pytest.raises(RoadmapSliceRegistryError, match="implementation_notes"):
        load_governed_slice_registry_artifacts(
            slice_registry_path=registry_path,
            roadmap_structure_path=_FIXTURE_ROOT / "roadmap_structure.json",
        )


def test_missing_execution_type_fails(tmp_path: Path) -> None:
    bad_registry = json.loads((_FIXTURE_ROOT / "slice_registry.json").read_text(encoding="utf-8"))
    bad_registry["slices"][0].pop("execution_type", None)
    registry_path = tmp_path / "slice_registry.json"
    registry_path.write_text(json.dumps(bad_registry), encoding="utf-8")

    with pytest.raises(RoadmapSliceRegistryError, match="missing required field: execution_type"):
        load_governed_slice_registry_artifacts(
            slice_registry_path=registry_path,
            roadmap_structure_path=_FIXTURE_ROOT / "roadmap_structure.json",
        )


def test_empty_commands_fails(tmp_path: Path) -> None:
    bad_registry = json.loads((_FIXTURE_ROOT / "slice_registry.json").read_text(encoding="utf-8"))
    bad_registry["slices"][0]["commands"] = []
    registry_path = tmp_path / "slice_registry.json"
    registry_path.write_text(json.dumps(bad_registry), encoding="utf-8")

    with pytest.raises(RoadmapSliceRegistryError, match="invalid commands"):
        load_governed_slice_registry_artifacts(
            slice_registry_path=registry_path,
            roadmap_structure_path=_FIXTURE_ROOT / "roadmap_structure.json",
        )


def test_empty_success_criteria_fails(tmp_path: Path) -> None:
    bad_registry = json.loads((_FIXTURE_ROOT / "slice_registry.json").read_text(encoding="utf-8"))
    bad_registry["slices"][0]["success_criteria"] = []
    registry_path = tmp_path / "slice_registry.json"
    registry_path.write_text(json.dumps(bad_registry), encoding="utf-8")

    with pytest.raises(RoadmapSliceRegistryError, match="invalid success_criteria"):
        load_governed_slice_registry_artifacts(
            slice_registry_path=registry_path,
            roadmap_structure_path=_FIXTURE_ROOT / "roadmap_structure.json",
        )


def test_valid_execution_fields_pass() -> None:
    slices, _ = load_governed_slice_registry_artifacts(
        slice_registry_path=_FIXTURE_ROOT / "slice_registry.json",
        roadmap_structure_path=_FIXTURE_ROOT / "roadmap_structure.json",
    )
    sample = slices[0]
    assert sample["execution_type"]
    assert sample["commands"]
    assert sample["success_criteria"]
