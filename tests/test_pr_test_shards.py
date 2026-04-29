"""Tests for PR test shard artifacts and shard routing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.pr_test_selection import assign_to_shard

_EXAMPLE_PATH = REPO_ROOT / "contracts" / "examples" / "pr_test_shard_result.example.json"
_SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "pr_test_shard_result.schema.json"

_FORBIDDEN_TOP_LEVEL_KEYS = {"approve", "certify", "promote", "enforce"}


# ---------------------------------------------------------------------------
# Example artifact tests
# ---------------------------------------------------------------------------


def test_shard_result_example_is_valid_json():
    assert _EXAMPLE_PATH.is_file(), f"Missing example: {_EXAMPLE_PATH}"
    raw = _EXAMPLE_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert isinstance(data, dict)


def test_shard_result_example_has_observation_only_authority_scope():
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    assert data.get("authority_scope") == "observation_only"


def test_shard_result_example_has_required_fields():
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    required = {"artifact_type", "schema_version", "shard_name", "status", "authority_scope"}
    for field in required:
        assert field in data, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


def test_shard_result_schema_exists():
    assert _SCHEMA_PATH.is_file(), f"Missing schema: {_SCHEMA_PATH}"


def test_shard_result_schema_is_valid_json():
    raw = _SCHEMA_PATH.read_text(encoding="utf-8")
    schema = json.loads(raw)
    assert isinstance(schema, dict)


def test_shard_result_schema_has_authority_scope_const():
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    # Traverse schema properties to find authority_scope const enforcement
    raw_text = _SCHEMA_PATH.read_text(encoding="utf-8")
    assert '"const": "observation_only"' in raw_text, (
        "Schema must enforce authority_scope = observation_only via const"
    )


# ---------------------------------------------------------------------------
# Authority scope check on example
# ---------------------------------------------------------------------------


def test_shard_result_cannot_have_approve_language():
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    top_level_keys = set(data.keys())
    forbidden_found = top_level_keys & _FORBIDDEN_TOP_LEVEL_KEYS
    assert not forbidden_found, (
        f"Shard result example must not contain authority-violating keys: {forbidden_found}"
    )


# ---------------------------------------------------------------------------
# Shard routing
# ---------------------------------------------------------------------------


def test_governance_shard_triggers_for_governance_doc_change():
    # A test file whose name maps to the governance shard
    test_path = "tests/test_governance_doc.py"
    shard = assign_to_shard(test_path)
    assert shard == "governance", (
        f"Expected governance shard for {test_path!r}, got {shard!r}"
    )
