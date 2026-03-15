import json
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "governance" / "policies" / "policy-registry.json"
SCHEMA_PATH = REPO_ROOT / "governance" / "policies" / "policy-registry.schema.json"


def test_policy_registry_matches_schema() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=registry, schema=schema)


def test_policy_ids_are_unique() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    policy_ids = [policy["policy_id"] for policy in registry.get("policies", [])]
    assert len(policy_ids) == len(set(policy_ids))
