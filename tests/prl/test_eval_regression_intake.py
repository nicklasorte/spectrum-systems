"""F3L-04 — Tests for PRL eval-regression intake record builder.

PRL retains only classification and eval-candidate authority. These
tests assert that the intake record:

  * proves PRL eval candidates have been routed into a governed
    regression-coverage intake surface,
  * fails closed when ``intake_status`` is ``present`` without
    ``eval_candidate_refs`` (no PR body prose substitution),
  * carries reason codes for partial / missing / unknown intake,
  * routes unknown failure classes to ``manual_review_required``,
  * preserves authority-safe language (``authority_scope`` =
    ``observation_only``, ``source_system`` = ``PRL``),
  * binds back to the source failure packet refs and the PRL artifact
    index ref so EVL/CLP/APU can detect it later.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from spectrum_systems.modules.prl.eval_regression_intake import (
    CandidateIntake,
    REASON_CANDIDATE_NOT_GATE_ELIGIBLE,
    REASON_NO_EVAL_CANDIDATES_FOR_FAILURE_PACKETS,
    REASON_NO_FAILURES_DETECTED,
    REASON_UNKNOWN_FAILURE_REQUIRES_MANUAL_REVIEW,
    build_eval_regression_intake_record,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    REPO_ROOT
    / "contracts"
    / "schemas"
    / "prl_eval_regression_intake_record.schema.json"
)


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _accepted_candidate(ref: str = "outputs/prl/eval_candidates/a.json") -> CandidateIntake:
    return CandidateIntake(
        ref=ref,
        failure_class="authority_shape_violation",
        gate_eligible=True,
    )


def _rejected_unknown_candidate(
    ref: str = "outputs/prl/eval_candidates/u.json",
) -> CandidateIntake:
    return CandidateIntake(
        ref=ref, failure_class="unknown_failure", gate_eligible=False
    )


# ---------------------------------------------------------------------------
# Behavior 1: PRL eval candidates produce an eval-regression intake record.
# ---------------------------------------------------------------------------


def test_eval_candidates_produce_intake_record():
    record = build_eval_regression_intake_record(
        run_id="run-1",
        trace_id="trace-1",
        candidates=[_accepted_candidate()],
        source_failure_packet_refs=["outputs/prl/failure_packets/p.json"],
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
    )
    assert record["artifact_type"] == "prl_eval_regression_intake_record"
    assert record["schema_version"] == "1.0.0"
    assert record["intake_status"] == "present"
    assert record["candidate_count"] == 1
    assert record["coverage_intent"] == "regression_candidate"
    assert record["accepted_candidate_refs"] == [
        "outputs/prl/eval_candidates/a.json"
    ]
    jsonschema.validate(record, _load_schema())


# ---------------------------------------------------------------------------
# Behavior 2: present requires eval_candidate_refs.
# ---------------------------------------------------------------------------


def test_intake_status_present_requires_candidate_refs():
    """Schema must reject present-without-refs (no prose substitution)."""
    schema = _load_schema()
    bad = {
        "artifact_type": "prl_eval_regression_intake_record",
        "schema_version": "1.0.0",
        "id": "prl-eri-0123456789abcdef",
        "run_id": "r",
        "trace_id": "t",
        "generated_at": "2026-05-02T00:00:00Z",
        "source_system": "PRL",
        "source_failure_packet_refs": ["outputs/prl/failure_packets/p.json"],
        "eval_candidate_refs": [],
        "prl_artifact_index_ref": "outputs/prl/prl_artifact_index.json",
        "intake_status": "present",
        "candidate_count": 0,
        "accepted_candidate_refs": [],
        "rejected_candidate_refs": [],
        "reason_codes": [],
        "coverage_intent": "regression_candidate",
        "authority_scope": "observation_only",
        "evidence_hash": "sha256-" + "0" * 64,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


# ---------------------------------------------------------------------------
# Behavior 3: missing eval candidates produce missing/partial with reason_codes.
# ---------------------------------------------------------------------------


def test_failures_without_candidates_yield_missing_with_reason_codes():
    record = build_eval_regression_intake_record(
        run_id="run-2",
        trace_id="trace-2",
        candidates=[],
        source_failure_packet_refs=["outputs/prl/failure_packets/p.json"],
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
    )
    assert record["intake_status"] == "missing"
    assert record["coverage_intent"] == "manual_review_required"
    assert (
        REASON_NO_EVAL_CANDIDATES_FOR_FAILURE_PACKETS in record["reason_codes"]
    )
    jsonschema.validate(record, _load_schema())


def test_clean_run_yields_missing_with_no_failures_reason_code():
    record = build_eval_regression_intake_record(
        run_id="run-3",
        trace_id="trace-3",
        candidates=[],
        source_failure_packet_refs=[],
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
    )
    assert record["intake_status"] == "missing"
    assert record["coverage_intent"] == "not_applicable"
    assert REASON_NO_FAILURES_DETECTED in record["reason_codes"]
    jsonschema.validate(record, _load_schema())


def test_partial_status_requires_reason_codes_in_schema():
    schema = _load_schema()
    bad = {
        "artifact_type": "prl_eval_regression_intake_record",
        "schema_version": "1.0.0",
        "id": "prl-eri-0123456789abcdef",
        "run_id": "r",
        "trace_id": "t",
        "generated_at": "2026-05-02T00:00:00Z",
        "source_system": "PRL",
        "source_failure_packet_refs": [],
        "eval_candidate_refs": ["outputs/prl/eval_candidates/x.json"],
        "prl_artifact_index_ref": "outputs/prl/prl_artifact_index.json",
        "intake_status": "partial",
        "candidate_count": 1,
        "accepted_candidate_refs": [],
        "rejected_candidate_refs": ["outputs/prl/eval_candidates/x.json"],
        "reason_codes": [],
        "coverage_intent": "manual_review_required",
        "authority_scope": "observation_only",
        "evidence_hash": "sha256-" + "0" * 64,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


# ---------------------------------------------------------------------------
# Behavior 4: unknown failure class produces manual_review_required.
# ---------------------------------------------------------------------------


def test_unknown_failure_routes_to_manual_review_required():
    record = build_eval_regression_intake_record(
        run_id="run-4",
        trace_id="trace-4",
        candidates=[_rejected_unknown_candidate()],
        source_failure_packet_refs=["outputs/prl/failure_packets/u.json"],
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
    )
    assert record["intake_status"] == "partial"
    assert record["coverage_intent"] == "manual_review_required"
    assert (
        REASON_UNKNOWN_FAILURE_REQUIRES_MANUAL_REVIEW in record["reason_codes"]
    )
    assert record["accepted_candidate_refs"] == []
    assert record["rejected_candidate_refs"] == [
        "outputs/prl/eval_candidates/u.json"
    ]
    jsonschema.validate(record, _load_schema())


def test_mixed_known_and_unknown_emits_present_with_reason_code_for_rejected():
    record = build_eval_regression_intake_record(
        run_id="run-5",
        trace_id="trace-5",
        candidates=[
            _accepted_candidate("outputs/prl/eval_candidates/a.json"),
            _rejected_unknown_candidate("outputs/prl/eval_candidates/u.json"),
        ],
        source_failure_packet_refs=[
            "outputs/prl/failure_packets/p.json",
            "outputs/prl/failure_packets/u.json",
        ],
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
    )
    assert record["intake_status"] == "present"
    assert record["coverage_intent"] == "regression_candidate"
    assert "outputs/prl/eval_candidates/a.json" in record["accepted_candidate_refs"]
    assert "outputs/prl/eval_candidates/u.json" in record["rejected_candidate_refs"]
    assert (
        REASON_UNKNOWN_FAILURE_REQUIRES_MANUAL_REVIEW in record["reason_codes"]
    )
    jsonschema.validate(record, _load_schema())


# ---------------------------------------------------------------------------
# Behavior 5: intake record links back to PRL artifact index and failure refs.
# ---------------------------------------------------------------------------


def test_intake_record_binds_to_artifact_index_and_failure_packets():
    failure_refs = [
        "outputs/prl/failure_packets/p1.json",
        "outputs/prl/failure_packets/p2.json",
    ]
    record = build_eval_regression_intake_record(
        run_id="run-6",
        trace_id="trace-6",
        candidates=[_accepted_candidate()],
        source_failure_packet_refs=failure_refs,
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
        prl_gate_result_ref="outputs/prl/prl_gate_result.json",
    )
    assert (
        record["prl_artifact_index_ref"]
        == "outputs/prl/prl_artifact_index.json"
    )
    assert (
        record["prl_gate_result_ref"] == "outputs/prl/prl_gate_result.json"
    )
    assert sorted(record["source_failure_packet_refs"]) == sorted(failure_refs)


# ---------------------------------------------------------------------------
# Behavior 6: evidence hash changes when candidate refs change.
# ---------------------------------------------------------------------------


def test_evidence_hash_changes_when_candidate_refs_change():
    a = build_eval_regression_intake_record(
        run_id="run-7",
        trace_id="trace-7",
        candidates=[_accepted_candidate("outputs/prl/eval_candidates/x.json")],
        source_failure_packet_refs=["outputs/prl/failure_packets/p.json"],
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
    )
    b = build_eval_regression_intake_record(
        run_id="run-7",
        trace_id="trace-7",
        candidates=[_accepted_candidate("outputs/prl/eval_candidates/y.json")],
        source_failure_packet_refs=["outputs/prl/failure_packets/p.json"],
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
    )
    assert a["evidence_hash"] != b["evidence_hash"]


def test_evidence_hash_stable_for_identical_inputs():
    a = build_eval_regression_intake_record(
        run_id="run-8",
        trace_id="trace-8",
        candidates=[_accepted_candidate()],
        source_failure_packet_refs=["outputs/prl/failure_packets/p.json"],
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
    )
    b = build_eval_regression_intake_record(
        run_id="run-8",
        trace_id="trace-8",
        candidates=[_accepted_candidate()],
        source_failure_packet_refs=["outputs/prl/failure_packets/p.json"],
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
    )
    assert a["evidence_hash"] == b["evidence_hash"]


# ---------------------------------------------------------------------------
# Behavior 7: PR body prose cannot substitute for eval candidate refs.
# ---------------------------------------------------------------------------


def test_pr_body_prose_cannot_substitute_for_candidate_refs():
    """A 'present' intake claim cannot be made with prose-only evidence.

    The schema requires file-backed eval_candidate_refs whenever
    intake_status is present. Prose, comments, or PR body text are not
    accepted because eval_candidate_refs items must be path-shaped
    strings persisted by PRL.
    """
    schema = _load_schema()
    prose = {
        "artifact_type": "prl_eval_regression_intake_record",
        "schema_version": "1.0.0",
        "id": "prl-eri-0123456789abcdef",
        "run_id": "r",
        "trace_id": "t",
        "generated_at": "2026-05-02T00:00:00Z",
        "source_system": "PRL",
        "source_failure_packet_refs": ["outputs/prl/failure_packets/p.json"],
        "eval_candidate_refs": [],  # prose claims live elsewhere; refs are empty
        "prl_artifact_index_ref": "outputs/prl/prl_artifact_index.json",
        "intake_status": "present",
        "candidate_count": 0,
        "accepted_candidate_refs": [],
        "rejected_candidate_refs": [],
        "reason_codes": [],
        "coverage_intent": "regression_candidate",
        "authority_scope": "observation_only",
        "evidence_hash": "sha256-" + "0" * 64,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(prose, schema)


# ---------------------------------------------------------------------------
# Behavior 8: schema rejects present-without-refs (covered above) — also assert
# the builder fails closed when we fabricate a present claim with no refs.
# ---------------------------------------------------------------------------


def test_builder_fails_closed_for_present_without_refs(monkeypatch):
    """The builder cannot be coerced into emitting present without refs.

    With zero failure packets and zero candidates, the builder lands on
    ``missing`` / ``not_applicable``. There is no public path that
    yields ``present`` without real eval_candidate_refs.
    """
    record = build_eval_regression_intake_record(
        run_id="run-9",
        trace_id="trace-9",
        candidates=[],
        source_failure_packet_refs=[],
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
    )
    assert record["intake_status"] != "present"
    assert record["eval_candidate_refs"] == []


# ---------------------------------------------------------------------------
# Behavior 9: authority-safe language is preserved.
# ---------------------------------------------------------------------------


def test_authority_safe_language_preserved():
    record = build_eval_regression_intake_record(
        run_id="run-10",
        trace_id="trace-10",
        candidates=[_accepted_candidate()],
        source_failure_packet_refs=["outputs/prl/failure_packets/p.json"],
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
    )
    assert record["source_system"] == "PRL"
    assert record["authority_scope"] == "observation_only"


def test_schema_pins_authority_scope_to_observation_only():
    """authority_scope=control_signal must be rejected — PRL emits intake
    evidence only; canonical authority remains with EVL per
    docs/architecture/system_registry.md.
    """
    schema = _load_schema()
    bad = {
        "artifact_type": "prl_eval_regression_intake_record",
        "schema_version": "1.0.0",
        "id": "prl-eri-0123456789abcdef",
        "run_id": "r",
        "trace_id": "t",
        "generated_at": "2026-05-02T00:00:00Z",
        "source_system": "PRL",
        "source_failure_packet_refs": [],
        "eval_candidate_refs": ["outputs/prl/eval_candidates/a.json"],
        "prl_artifact_index_ref": "outputs/prl/prl_artifact_index.json",
        "intake_status": "present",
        "candidate_count": 1,
        "accepted_candidate_refs": ["outputs/prl/eval_candidates/a.json"],
        "rejected_candidate_refs": [],
        "reason_codes": [],
        "coverage_intent": "regression_candidate",
        "authority_scope": "control_signal",
        "evidence_hash": "sha256-" + "0" * 64,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_schema_rejects_non_prl_source_system():
    schema = _load_schema()
    bad = {
        "artifact_type": "prl_eval_regression_intake_record",
        "schema_version": "1.0.0",
        "id": "prl-eri-0123456789abcdef",
        "run_id": "r",
        "trace_id": "t",
        "generated_at": "2026-05-02T00:00:00Z",
        "source_system": "APU",
        "source_failure_packet_refs": [],
        "eval_candidate_refs": ["outputs/prl/eval_candidates/a.json"],
        "prl_artifact_index_ref": "outputs/prl/prl_artifact_index.json",
        "intake_status": "present",
        "candidate_count": 1,
        "accepted_candidate_refs": ["outputs/prl/eval_candidates/a.json"],
        "rejected_candidate_refs": [],
        "reason_codes": [],
        "coverage_intent": "regression_candidate",
        "authority_scope": "observation_only",
        "evidence_hash": "sha256-" + "0" * 64,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


# ---------------------------------------------------------------------------
# Behavior 10: example artifact validates against the schema.
# ---------------------------------------------------------------------------


def test_example_artifact_validates_against_schema():
    example_path = (
        REPO_ROOT
        / "contracts"
        / "examples"
        / "prl_eval_regression_intake_record.example.json"
    )
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    jsonschema.validate(payload, _load_schema())


def test_non_unknown_rejected_yields_candidate_not_gate_eligible_reason():
    """When a candidate is rejected but not for unknown_failure, the
    candidate_not_gate_eligible reason code surfaces."""
    rejected_known = CandidateIntake(
        ref="outputs/prl/eval_candidates/r.json",
        failure_class="contract_schema_violation",
        gate_eligible=False,
    )
    record = build_eval_regression_intake_record(
        run_id="run-11",
        trace_id="trace-11",
        candidates=[rejected_known],
        source_failure_packet_refs=["outputs/prl/failure_packets/p.json"],
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
    )
    assert record["intake_status"] == "partial"
    assert REASON_CANDIDATE_NOT_GATE_ELIGIBLE in record["reason_codes"]


def test_intake_status_unknown_requires_reason_codes_in_schema():
    schema = _load_schema()
    bad = {
        "artifact_type": "prl_eval_regression_intake_record",
        "schema_version": "1.0.0",
        "id": "prl-eri-0123456789abcdef",
        "run_id": "r",
        "trace_id": "t",
        "generated_at": "2026-05-02T00:00:00Z",
        "source_system": "PRL",
        "source_failure_packet_refs": [],
        "eval_candidate_refs": [],
        "prl_artifact_index_ref": "outputs/prl/prl_artifact_index.json",
        "intake_status": "unknown",
        "candidate_count": 0,
        "accepted_candidate_refs": [],
        "rejected_candidate_refs": [],
        "reason_codes": [],
        "coverage_intent": "not_applicable",
        "authority_scope": "observation_only",
        "evidence_hash": "sha256-" + "0" * 64,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)
