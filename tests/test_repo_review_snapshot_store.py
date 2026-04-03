from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example, load_schema  # noqa: E402
from spectrum_systems.modules.runtime.repo_review_snapshot_store import (  # noqa: E402
    RepoReviewSnapshotStoreError,
    read_repo_review_snapshot,
    validate_repo_review_snapshot,
    write_repo_review_snapshot,
)


def _snapshot() -> dict:
    return copy.deepcopy(load_example("repo_review_snapshot"))


def test_repo_review_snapshot_schema_example_validates() -> None:
    validator = Draft202012Validator(load_schema("repo_review_snapshot"), format_checker=FormatChecker())
    validator.validate(_snapshot())


def test_repo_review_snapshot_storage_round_trip(tmp_path: Path) -> None:
    snapshot = _snapshot()
    output = tmp_path / "artifacts" / "reviews" / "snapshots" / "snapshot.json"
    write_repo_review_snapshot(snapshot, output)
    loaded = read_repo_review_snapshot(output)
    assert loaded == json.loads(json.dumps(snapshot, sort_keys=True))


def test_repo_review_snapshot_missing_required_field_fails_closed() -> None:
    snapshot = _snapshot()
    snapshot.pop("commit_hash")
    with pytest.raises(RepoReviewSnapshotStoreError, match="schema validation"):
        validate_repo_review_snapshot(snapshot)


def test_repo_review_snapshot_read_missing_file_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(RepoReviewSnapshotStoreError, match="artifact not found"):
        read_repo_review_snapshot(tmp_path / "missing.json")
