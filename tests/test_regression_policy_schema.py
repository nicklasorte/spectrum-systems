from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_regression_policy_id_is_explicit_and_versioned() -> None:
    policy = _load_json(REPO_ROOT / "config" / "regression_policy.json")
    assert policy["policy_id"] == "regression-policy-v1.0.0"


def test_regression_policy_schema_enforces_namespace_pattern() -> None:
    schema = _load_json(REPO_ROOT / "contracts" / "schemas" / "regression_policy.schema.json")
    assert schema["properties"]["policy_id"]["pattern"] == "^regression-policy-v\\d+\\.\\d+\\.\\d+$"


def test_regression_policy_default_identifier_rejected() -> None:
    schema = _load_json(REPO_ROOT / "contracts" / "schemas" / "regression_policy.schema.json")
    policy = _load_json(REPO_ROOT / "config" / "regression_policy.json")
    policy["policy_id"] = "default"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=policy, schema=schema)
