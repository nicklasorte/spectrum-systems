import json
import re
from pathlib import Path
from typing import Iterable, Mapping, Tuple

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "ecosystem" / "ecosystem-registry.json"
STANDARDS_MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"
REQUIRED_FIELDS = ("repo_name", "repo_type", "status", "layer")
REPO_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def _load_registry() -> Tuple[Mapping[str, object], Iterable[Mapping[str, object]]]:
    assert REGISTRY_PATH.is_file(), "ecosystem-registry.json is missing"
    with REGISTRY_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)

    if isinstance(data, dict) and "repositories" in data:
        entries = data["repositories"]
    elif isinstance(data, list):
        entries = data
    else:
        pytest.fail("Registry must be an array or an object with a 'repositories' field")

    if not isinstance(entries, list):
        pytest.fail("Repositories collection must be a list")

    return data, entries


def _load_standards_manifest() -> Iterable[str]:
    assert STANDARDS_MANIFEST_PATH.is_file(), "contracts/standards-manifest.json is missing"
    with STANDARDS_MANIFEST_PATH.open(encoding="utf-8") as handle:
        manifest = json.load(handle)

    contracts = manifest.get("contracts", [])
    consumers: set[str] = set()
    for contract in contracts:
        for consumer in contract.get("intended_consumers", []):
            if isinstance(consumer, str) and REPO_NAME_PATTERN.match(consumer):
                consumers.add(consumer)
    return consumers


def test_registry_parses_and_contains_entries() -> None:
    data, entries = _load_registry()
    assert data is not None
    assert isinstance(entries, list)
    assert entries, "Registry must contain at least one repository entry"


def test_registry_entries_have_required_fields() -> None:
    _, entries = _load_registry()
    for entry in entries:
        assert isinstance(entry, dict), "Each repository entry must be an object"
        for field in REQUIRED_FIELDS:
            assert field in entry, f"Missing required field '{field}' in entry: {entry}"
            assert entry[field], f"Field '{field}' must be non-empty in entry: {entry}"


def test_contract_consumers_exist_in_registry() -> None:
    _, entries = _load_registry()
    registry_repo_names = {entry.get("repo_name") for entry in entries if isinstance(entry, dict)}
    consumers = _load_standards_manifest()
    missing = sorted(consumers - registry_repo_names)
    assert not missing, f"Registry missing intended consumers from standards manifest: {missing}"
