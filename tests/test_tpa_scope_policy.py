from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.governance.tpa_scope_policy import (
    TPAScopePolicyError,
    is_tpa_required,
    load_tpa_scope_policy,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_scope_policy_required_path_enforced() -> None:
    policy = load_tpa_scope_policy(_REPO_ROOT / "config" / "policy" / "tpa_scope_policy.json")
    assert is_tpa_required({"file_path": "spectrum_systems/modules/runtime/pqx_sequence_runner.py"}, policy=policy) is True


def test_scope_policy_optional_path_not_enforced() -> None:
    policy = load_tpa_scope_policy(_REPO_ROOT / "config" / "policy" / "tpa_scope_policy.json")
    assert is_tpa_required({"file_path": "tests/test_done_certification.py"}, policy=policy) is False


def test_scope_policy_missing_file_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(TPAScopePolicyError, match="file not found"):
        load_tpa_scope_policy(tmp_path / "missing_policy.json")


def test_scope_policy_invalid_shape_fails_closed(tmp_path: Path) -> None:
    bad = tmp_path / "bad_policy.json"
    bad.write_text(json.dumps({"artifact_type": "tpa_scope_policy"}), encoding="utf-8")
    with pytest.raises(TPAScopePolicyError, match="failed schema validation"):
        load_tpa_scope_policy(bad)


def test_scope_policy_fails_closed_when_source_authority_refresh_digest_mismatches(tmp_path: Path) -> None:
    policy = load_tpa_scope_policy(_REPO_ROOT / "config" / "policy" / "tpa_scope_policy.json")
    policy["source_authority_refresh"]["source_inventory_digest_sha256"] = "0" * 64
    path = tmp_path / "bad-refresh.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(TPAScopePolicyError, match="refresh digest mismatch"):
        load_tpa_scope_policy(path)
