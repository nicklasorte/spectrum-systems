import json
import re
from pathlib import Path
from typing import Iterable, Mapping, Set, Tuple

import pytest
from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "ecosystem" / "ecosystem-registry.json"
SCHEMA_PATH = REPO_ROOT / "ecosystem" / "ecosystem-registry.schema.json"
STANDARDS_MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"
REQUIRED_LAYER3_ENGINES = {
    "comment-resolution-engine",
    "working-paper-review-engine",
    "meeting-minutes-engine",
    "docx-comment-injection-engine",
}
NON_GOVERNANCE_ACTIVE_STATUSES = {"active", "experimental"}
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


def _load_manifest() -> Mapping[str, object]:
    assert STANDARDS_MANIFEST_PATH.is_file(), "contracts/standards-manifest.json is missing"
    with STANDARDS_MANIFEST_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _canonical_contracts(manifest: Mapping[str, object]) -> Set[str]:
    contracts = manifest.get("contracts", [])
    canonical: Set[str] = set()
    for contract in contracts:
        if isinstance(contract, dict) and contract.get("artifact_type"):
            canonical.add(str(contract["artifact_type"]))
    return canonical


def _manifest_consumers(manifest: Mapping[str, object]) -> Set[str]:
    consumers: Set[str] = set()
    for contract in manifest.get("contracts", []):
        for consumer in contract.get("intended_consumers", []):
            if isinstance(consumer, str) and REPO_NAME_PATTERN.match(consumer):
                consumers.add(consumer)
    return consumers


def test_registry_conforms_to_schema() -> None:
    data, _ = _load_registry()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda err: err.path)
    if errors:
        messages = "\n".join(
            f"- {'/'.join(map(str, err.path)) or '<root>'}: {err.message}"
            for err in errors
        )
        pytest.fail(f"ecosystem-registry.json must satisfy ecosystem-registry.schema.json:\n{messages}")


def test_registry_covers_manifest_consumers() -> None:
    _, entries = _load_registry()
    registry_repo_names = {entry.get("repo_name") for entry in entries if isinstance(entry, dict)}
    manifest_consumers = _manifest_consumers(_load_manifest())
    missing = sorted(manifest_consumers - registry_repo_names)
    assert not missing, f"Registry missing intended consumers from standards-manifest.json: {missing}"


def test_registry_contracts_are_canonical() -> None:
    _, entries = _load_registry()
    canonical_contracts = _canonical_contracts(_load_manifest())

    invalid = []
    for entry in entries:
        repo_name = entry.get("repo_name")
        for contract in entry.get("contracts", []):
            if contract not in canonical_contracts:
                invalid.append((repo_name, contract))

    assert not invalid, f"Registry references non-canonical contract names: {invalid}"


def test_required_operational_engines_present() -> None:
    _, entries = _load_registry()
    registry_repo_names = {entry.get("repo_name") for entry in entries if isinstance(entry, dict)}
    missing = sorted(REQUIRED_LAYER3_ENGINES - registry_repo_names)
    assert not missing, f"Registry missing required Layer 3 operational engines: {missing}"


def test_active_repos_declare_contracts_when_expected() -> None:
    _, entries = _load_registry()
    offenders = [
        entry.get("repo_name")
        for entry in entries
        if isinstance(entry, dict)
        and entry.get("repo_type") != "governance"
        and entry.get("status") in NON_GOVERNANCE_ACTIVE_STATUSES
        and not entry.get("contracts")
    ]
    assert not offenders, f"Active or experimental non-governance repos must declare at least one contract: {offenders}"
