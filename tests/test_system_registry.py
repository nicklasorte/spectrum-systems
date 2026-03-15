import json
from pathlib import Path
from typing import List, Mapping, Sequence

import pytest
from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "ecosystem" / "system-registry.json"
SCHEMA_PATH = REPO_ROOT / "ecosystem" / "system-registry.schema.json"
DOC_PATH = REPO_ROOT / "docs" / "system-registry.md"
README_PATH = REPO_ROOT / "README.md"
ECOSYSTEM_ARCH_PATH = REPO_ROOT / "docs" / "ecosystem-architecture.md"


def _load_registry() -> List[Mapping[str, object]]:
    assert REGISTRY_PATH.is_file(), "ecosystem/system-registry.json is missing"
    with REGISTRY_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)

    assert isinstance(data, list), "System registry must be a list of system records"
    return data


def test_system_registry_files_exist() -> None:
    assert DOC_PATH.is_file(), "docs/system-registry.md must exist"
    assert REGISTRY_PATH.is_file(), "ecosystem/system-registry.json must exist"
    assert SCHEMA_PATH.is_file(), "ecosystem/system-registry.schema.json must exist"


def test_system_registry_validates_against_schema() -> None:
    data = _load_registry()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda err: err.path)
    if errors:
        messages = "\n".join(
            f"- {'/'.join(map(str, err.path)) or '<root>'}: {err.message}"
            for err in errors
        )
        pytest.fail(f"system-registry.json must satisfy system-registry.schema.json:\n{messages}")


def test_system_ids_are_unique() -> None:
    entries = _load_registry()
    system_ids: Sequence[str] = [str(entry.get("system_id")) for entry in entries]
    duplicates = sorted({system_id for system_id in system_ids if system_ids.count(system_id) > 1})
    assert not duplicates, f"Duplicate system_id values found: {duplicates}"


def test_registry_referenced_in_docs() -> None:
    combined = (README_PATH.read_text(encoding="utf-8") + ECOSYSTEM_ARCH_PATH.read_text(encoding="utf-8")).lower()
    assert "system registry" in combined or "system-registry" in combined, "Registry should be referenced in README or ecosystem docs"


def test_operational_engines_require_interface_standard() -> None:
    entries = _load_registry()
    offenders = [
        entry.get("system_id")
        for entry in entries
        if entry.get("repo_type") == "operational_engine"
        and entry.get("interface_standard_expected") is not True
    ]
    assert not offenders, f"Operational engines must set interface_standard_expected=true: {offenders}"
