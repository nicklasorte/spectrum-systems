from __future__ import annotations

from spectrum_systems.contracts import load_example, validate_artifact


def test_phase_registry_example_validates() -> None:
    validate_artifact(load_example("phase_registry"), "phase_registry")


def test_phase_requirement_profile_example_validates() -> None:
    validate_artifact(load_example("phase_requirement_profile"), "phase_requirement_profile")


def test_artifact_family_phase_map_example_validates() -> None:
    validate_artifact(load_example("artifact_family_phase_map"), "artifact_family_phase_map")
