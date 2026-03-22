from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_governance_provenance_requires_policy_id() -> None:
    schema = _load_json(REPO_ROOT / "governance" / "schemas" / "provenance.schema.json")
    assert "policy_id" in schema["required"]


def test_governance_provenance_missing_policy_id_fails_validation() -> None:
    schema = _load_json(REPO_ROOT / "governance" / "schemas" / "provenance.schema.json")
    payload = _load_json(REPO_ROOT / "governance" / "examples" / "evidence-bundle" / "provenance.json")
    payload.pop("policy_id")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)


def test_shared_provenance_requires_policy_id_and_version_bump() -> None:
    schema = _load_json(REPO_ROOT / "schemas" / "provenance-schema.json")
    assert "policy_id" in schema["required"]
    assert schema["properties"]["schema_version"]["const"] == "1.1.0"


def test_shared_provenance_missing_policy_id_fails_validation() -> None:
    schema = _load_json(REPO_ROOT / "schemas" / "provenance-schema.json")
    payload = {
        "record_id": "PRV-TEST-001",
        "record_type": "artifact",
        "source_document": "unit-test",
        "source_revision": "rev1",
        "workflow_name": "test-workflow",
        "workflow_step": "test-step",
        "generated_by_system": "SYS-TEST",
        "generated_by_repo": "nicklasorte/spectrum-systems",
        "generated_by_version": "abc1234",
        "schema_version": "1.1.0",
        "created_at": "2026-03-22T00:00:00Z",
        "updated_at": "2026-03-22T00:00:00Z",
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)
