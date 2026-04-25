from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from spectrum_systems.modules.hop.validator import validate_artifact_shape


SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "contracts" / "schemas" / "hop"


def _now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _base(artifact_type: str, schema_ref: str) -> dict:
    return {
        "artifact_type": artifact_type,
        "artifact_id": f"id-{artifact_type}",
        "schema_ref": schema_ref,
        "trace": {"trace_id": "trace-1", "timestamp": _now(), "steps": [{"name": "t", "status": "pass"}]},
        "content_hash": _hash({"a": 1}),
        "created_at": _now(),
    }


def test_all_hop_schemas_validate_minimal_artifacts() -> None:
    candidate = _base("harness_candidate", "hop/harness_candidate.schema.json@1.0.0")
    candidate.update({"candidate_id": "cand-1", "code_ref": "/tmp/candidate.py", "interface": {"entrypoint": "HarnessCandidate", "required_methods": ["run"]}})
    validate_artifact_shape(candidate, "harness_candidate", schema_root=SCHEMA_ROOT)

    run = _base("harness_run", "hop/harness_run.schema.json@1.0.0")
    run.update({"run_id": "run-1", "candidate_id": "cand-1", "eval_case_id": "golden-01", "status": "pass", "output_artifact": {"artifact_type": "faq_cluster_artifact", "payload": {}}})
    validate_artifact_shape(run, "harness_run", schema_root=SCHEMA_ROOT)

    score = _base("harness_score", "hop/harness_score.schema.json@1.0.0")
    score.update({"candidate_id": "cand-1", "score": 0.8, "coverage": 1.0, "run_count": 3})
    validate_artifact_shape(score, "harness_score", schema_root=SCHEMA_ROOT)

    trace = _base("harness_trace", "hop/harness_trace.schema.json@1.0.0")
    trace.update({"candidate_id": "cand-1", "run_id": "run-1", "trace_completeness": 1.0})
    validate_artifact_shape(trace, "harness_trace", schema_root=SCHEMA_ROOT)

    frontier = _base("harness_frontier", "hop/harness_frontier.schema.json@1.0.0")
    frontier.update({"frontier_id": "f-1", "objective_keys": ["score"], "entries": [{"candidate_id": "cand-1", "score": 1.0, "cost": 1.0, "latency": 1.0, "trace_completeness": 1.0, "eval_coverage": 1.0}]})
    validate_artifact_shape(frontier, "harness_frontier", schema_root=SCHEMA_ROOT)

    failure = _base("harness_failure_hypothesis", "hop/harness_failure_hypothesis.schema.json@1.0.0")
    failure.update({"candidate_id": "cand-1", "failure_code": "x", "hypothesis": "y", "severity": "high"})
    validate_artifact_shape(failure, "harness_failure_hypothesis", schema_root=SCHEMA_ROOT)


def test_schema_fails_closed_without_required_fields() -> None:
    invalid = _base("harness_score", "hop/harness_score.schema.json@1.0.0")
    invalid.update({"candidate_id": "cand-1", "coverage": 1.0, "run_count": 1})
    with pytest.raises(Exception):
        validate_artifact_shape(invalid, "harness_score", schema_root=SCHEMA_ROOT)
