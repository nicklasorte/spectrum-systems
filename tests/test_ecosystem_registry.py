import json
import re
from pathlib import Path
from typing import Iterable, Mapping, Tuple

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "ecosystem" / "ecosystem-registry.json"
STANDARDS_MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"
DESIGN_PACKAGES_DIR = REPO_ROOT / "design-packages"
REQUIRED_FIELDS = ("repo_name", "repo_type", "status", "layer", "contracts")
REPO_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
REPO_URL_PATTERN = re.compile(
    r"^https://github\.com/(?P<org>[A-Za-z0-9_.-]+)/(?P<slug>[A-Za-z0-9_.-]+)/?$"
)

# Expected layer for each repo_type.
EXPECTED_LAYER: dict[str, str] = {
    "governance": "Layer 2",
    "factory": "Layer 1",
    "operational_engine": "Layer 3",
    "pipeline": "Layer 4",
    "advisory": "Layer 5",
}


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
            if field != "contracts":
                assert entry[field], f"Field '{field}' must be non-empty in entry: {entry}"
        assert REPO_NAME_PATTERN.match(entry["repo_name"]), f"Invalid repo_name format: {entry['repo_name']}"
        assert isinstance(entry["contracts"], list), "contracts must be a list"
        for contract in entry["contracts"]:
            assert isinstance(contract, str), "contracts entries must be strings"
        if entry["repo_type"] not in {"governance", "factory"}:
            assert "system_id" in entry, f"Missing system_id for governed repo: {entry.get('repo_name')}"


def test_contract_consumers_exist_in_registry() -> None:
    _, entries = _load_registry()
    registry_repo_names = {entry.get("repo_name") for entry in entries if isinstance(entry, dict)}
    consumers = _load_standards_manifest()
    missing = sorted(consumers - registry_repo_names)
    assert not missing, f"Registry missing intended consumers from standards manifest: {missing}"


def test_repo_names_are_unique() -> None:
    _, entries = _load_registry()
    names = [entry.get("repo_name") for entry in entries if isinstance(entry, dict)]
    duplicates = sorted(name for name in set(names) if names.count(name) > 1)
    assert not duplicates, f"Duplicate repo_name values found: {duplicates}"


def test_repo_url_structure() -> None:
    """repo_url must follow https://github.com/<org>/<repo_name> with a slug matching repo_name."""
    _, entries = _load_registry()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("repo_name", "")
        url = entry.get("repo_url", "")
        m = REPO_URL_PATTERN.match(url)
        assert m, (
            f"[{name}] repo_url '{url}' does not match the required GitHub URL pattern "
            f"'https://github.com/<org>/<repo>'."
        )
        url_slug = m.group("slug").rstrip("/")
        assert url_slug == name, (
            f"[{name}] URL slug '{url_slug}' does not match repo_name '{name}'."
        )


def test_system_id_matches_repo_name() -> None:
    """When system_id is present it must equal repo_name."""
    _, entries = _load_registry()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("repo_name", "")
        system_id = entry.get("system_id")
        if system_id is not None:
            assert system_id == name, (
                f"[{name}] system_id '{system_id}' does not match repo_name '{name}'."
            )


def test_system_id_has_design_package() -> None:
    """Every registry entry with a system_id must have a corresponding design package file."""
    _, entries = _load_registry()
    missing: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        system_id = entry.get("system_id")
        if system_id is None:
            continue
        expected_path = DESIGN_PACKAGES_DIR / f"{system_id}.design-package.json"
        if not expected_path.is_file():
            missing.append(
                f"{entry.get('repo_name')}: missing design-packages/{system_id}.design-package.json"
            )
    assert not missing, (
        "The following systems lack a design package:\n" + "\n".join(f"  {m}" for m in missing)
    )


def test_layer_classification_matches_repo_type() -> None:
    """Each repo's layer must match the expected layer for its repo_type."""
    _, entries = _load_registry()
    errors: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("repo_name", "")
        repo_type = entry.get("repo_type", "")
        layer = entry.get("layer", "")
        expected = EXPECTED_LAYER.get(repo_type)
        if expected is not None and layer != expected:
            errors.append(
                f"[{name}] repo_type '{repo_type}' expects layer '{expected}' "
                f"but registry declares layer '{layer}'."
            )
    assert not errors, (
        "Layer classification mismatches detected:\n" + "\n".join(f"  {e}" for e in errors)
    )
