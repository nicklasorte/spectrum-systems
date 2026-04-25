from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from spectrum_systems.modules.hop.experience_store import ExperienceStore


def _now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def test_experience_store_append_and_filter(tmp_path: Path) -> None:
    schema_root = Path(__file__).resolve().parents[1] / "contracts" / "schemas" / "hop"
    store = ExperienceStore(tmp_path / "store", schema_root=schema_root)

    score = {
        "artifact_type": "harness_score",
        "artifact_id": "score-1",
        "schema_ref": "hop/harness_score.schema.json@1.0.0",
        "trace": {"trace_id": "trace-1", "timestamp": _now(), "steps": [{"name": "s", "status": "pass"}]},
        "content_hash": _hash({"score": 0.9}),
        "created_at": _now(),
        "candidate_id": "cand-1",
        "score": 0.9,
        "coverage": 1.0,
        "run_count": 25,
    }
    store.append(score, "harness_score")

    fetched = list(store.iter_records(min_score=0.8, max_score=1.0))
    assert len(fetched) == 1
    assert fetched[0]["artifact"]["candidate_id"] == "cand-1"


def test_experience_store_rejects_malformed_artifact(tmp_path: Path) -> None:
    schema_root = Path(__file__).resolve().parents[1] / "contracts" / "schemas" / "hop"
    store = ExperienceStore(tmp_path / "store", schema_root=schema_root)
    invalid = {
        "artifact_type": "harness_score",
        "artifact_id": "score-2",
        "schema_ref": "hop/harness_score.schema.json@1.0.0",
        "trace": {"trace_id": "trace-2", "timestamp": _now(), "steps": [{"name": "s", "status": "pass"}]},
        "content_hash": _hash({"score": 0.1}),
        "created_at": _now(),
        "candidate_id": "cand-2",
        "coverage": 1.0,
        "run_count": 1,
    }
    with pytest.raises(Exception):
        store.append(invalid, "harness_score")
