"""Validator tests — schema, import, and method existence checks."""

from __future__ import annotations

from spectrum_systems.modules.hop.validator import validate_candidate
from tests.hop.conftest import make_baseline_candidate


def test_validator_accepts_baseline_candidate() -> None:
    candidate = make_baseline_candidate()
    ok, failures = validate_candidate(candidate)
    assert ok is True
    assert failures == []


def test_validator_rejects_schema_violation() -> None:
    bad = {"artifact_type": "hop_harness_candidate", "candidate_id": "x"}
    ok, failures = validate_candidate(bad)
    assert ok is False
    assert len(failures) == 1
    assert failures[0]["failure_class"] == "schema_violation"
    assert failures[0]["severity"] == "reject"


def test_validator_rejects_import_error() -> None:
    candidate = make_baseline_candidate()
    candidate["code_module"] = "spectrum_systems.modules.hop.does_not_exist"
    # Re-finalize content_hash + artifact_id after mutation.
    from spectrum_systems.modules.hop.artifacts import finalize_artifact

    candidate.pop("content_hash", None)
    candidate.pop("artifact_id", None)
    finalize_artifact(candidate, id_prefix="hop_candidate_")

    ok, failures = validate_candidate(candidate)
    assert ok is False
    assert failures[0]["failure_class"] == "import_error"


def test_validator_rejects_missing_method() -> None:
    candidate = make_baseline_candidate()
    candidate["declared_methods"] = ["run", "no_such_method"]
    from spectrum_systems.modules.hop.artifacts import finalize_artifact

    candidate.pop("content_hash", None)
    candidate.pop("artifact_id", None)
    finalize_artifact(candidate, id_prefix="hop_candidate_")

    ok, failures = validate_candidate(candidate)
    assert ok is False
    assert failures[0]["failure_class"] == "missing_method"


def test_validator_rejects_missing_entrypoint() -> None:
    candidate = make_baseline_candidate()
    candidate["code_entrypoint"] = "no_such_entrypoint"
    from spectrum_systems.modules.hop.artifacts import finalize_artifact

    candidate.pop("content_hash", None)
    candidate.pop("artifact_id", None)
    finalize_artifact(candidate, id_prefix="hop_candidate_")

    ok, failures = validate_candidate(candidate)
    assert ok is False
    assert failures[0]["failure_class"] == "missing_method"
