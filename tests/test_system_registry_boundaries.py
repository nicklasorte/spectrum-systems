import json
from pathlib import Path
from typing import Dict, List

import pytest
from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "system_registry_artifact.schema.json"
EXAMPLE_PATH = REPO_ROOT / "contracts" / "examples" / "system_registry_artifact.json"
MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_registry() -> dict:
    return _load_json(EXAMPLE_PATH)


def _systems_by_acronym(registry: dict) -> Dict[str, dict]:
    systems = registry["systems"]
    return {system["acronym"]: system for system in systems}


def validate_system_boundary(system_name: str, action_type: str) -> bool:
    """Optional helper used by tests to assert boundary ownership."""
    registry = _load_registry()
    systems = _systems_by_acronym(registry)
    if system_name not in systems:
        return False
    system = systems[system_name]
    return action_type in system.get("owns", []) and action_type not in system.get(
        "prohibited_behaviors", []
    )


def test_registry_example_validates_against_schema() -> None:
    schema = _load_json(SCHEMA_PATH)
    example = _load_registry()
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(example), key=lambda err: list(err.path))
    if errors:
        message = "\n".join(
            f"- {'/'.join(str(item) for item in err.path) or '<root>'}: {err.message}"
            for err in errors
        )
        pytest.fail(f"system_registry_artifact example failed schema validation:\n{message}")


def test_every_system_has_required_boundary_fields() -> None:
    systems = _load_registry()["systems"]
    for system in systems:
        assert system["acronym"]
        assert system["role"]
        assert system["owns"], f"{system['acronym']} must define at least one ownership"
        assert system["prohibited_behaviors"], (
            f"{system['acronym']} must declare must_not_do/prohibited behaviors"
        )


def test_no_duplicate_ownership_across_systems() -> None:
    systems = _load_registry()["systems"]
    owners_by_responsibility: Dict[str, List[str]] = {}
    for system in systems:
        for responsibility in system["owns"]:
            owners_by_responsibility.setdefault(responsibility, []).append(system["acronym"])

    duplicates = {
        responsibility: owners
        for responsibility, owners in owners_by_responsibility.items()
        if len(owners) > 1
    }
    assert not duplicates, f"Duplicate ownership detected: {duplicates}"


def test_known_invariants_hold() -> None:
    expected_owners = {
        "execution": "PQX",
        "failure_diagnosis": "FRE",
        "review_interpretation": "RIL",
        "closure_decisions": "CDE",
        "enforcement": "SEL",
        "orchestration": "TLC",
    }
    systems = _systems_by_acronym(_load_registry())

    for responsibility, system_name in expected_owners.items():
        assert validate_system_boundary(system_name, responsibility), (
            f"{system_name} must own {responsibility}"
        )

        for other_name, other_system in systems.items():
            if other_name == system_name:
                continue
            assert responsibility not in other_system["owns"], (
                f"{responsibility} must not be owned by {other_name}"
            )


def test_registry_is_registered_in_standards_manifest() -> None:
    manifest = _load_json(MANIFEST_PATH)
    contracts = manifest.get("contracts", [])

    matched = [
        contract
        for contract in contracts
        if contract.get("artifact_type") == "system_registry_artifact"
    ]
    assert len(matched) == 1, "system_registry_artifact must appear exactly once in standards manifest"

    contract = matched[0]
    assert contract["artifact_class"] == "coordination"
    assert contract["schema_version"] == "1.0.0"
    assert contract["example_path"] == "contracts/examples/system_registry_artifact.json"
    assert "spectrum-systems" in contract.get("intended_consumers", [])


def test_registry_loading_is_deterministic() -> None:
    first = json.dumps(_load_registry(), sort_keys=True, separators=(",", ":"))
    second = json.dumps(_load_registry(), sort_keys=True, separators=(",", ":"))
    assert first == second


def test_allowed_interaction_edges_present() -> None:
    registry = _load_registry()
    edge_pairs = {(edge["from"], edge["to"]) for edge in registry["interaction_edges"]}
    expected = {
        ("TLC", "PQX"),
        ("TLC", "TPA"),
        ("TLC", "FRE"),
        ("TLC", "RIL"),
        ("TLC", "CDE"),
        ("TLC", "PRG"),
        ("RIL", "CDE"),
    }
    assert expected.issubset(edge_pairs)
