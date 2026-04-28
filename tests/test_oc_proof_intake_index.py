"""OC-01..03: Proof intake index unit + red-team tests."""

from __future__ import annotations

import hashlib
import json

import pytest

from spectrum_systems.modules.governance.proof_intake_index import (
    CANONICAL_INTAKE_REASON_CODES,
    REQUIRED_PROOF_KINDS,
    ProofIntakeError,
    build_proof_intake_index,
)


def _digest(payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _candidate(kind: str, suffix: str = "1", offset: int = 0):
    inputs = {"kind": kind, "suffix": suffix}
    return {
        "artifact_id": f"{kind}-{suffix}",
        "producer_inputs": inputs,
        "producer_input_digest": _digest(inputs),
        "generated_at": f"2026-04-28T12:0{offset}:00Z",
    }


def _all_kinds_one_each():
    return {kind: [_candidate(kind, "1")] for kind in REQUIRED_PROOF_KINDS}


def test_required_kinds_finite_and_known():
    assert set(REQUIRED_PROOF_KINDS) == {
        "loop_proof_bundle",
        "certification_delta_proof",
        "trust_regression_result",
        "cli_summary",
        "dashboard_proof_ref",
    }


def test_canonical_reason_codes_finite():
    assert "PROOF_INTAKE_OK" in CANONICAL_INTAKE_REASON_CODES
    assert "PROOF_INTAKE_MISSING" in CANONICAL_INTAKE_REASON_CODES
    assert "PROOF_INTAKE_STALE_DIGEST_MISMATCH" in CANONICAL_INTAKE_REASON_CODES
    assert "PROOF_INTAKE_DUPLICATE" in CANONICAL_INTAKE_REASON_CODES
    assert "PROOF_INTAKE_CONFLICT" in CANONICAL_INTAKE_REASON_CODES
    assert "PROOF_INTAKE_SUPERSEDED" in CANONICAL_INTAKE_REASON_CODES


def test_intake_id_required():
    with pytest.raises(ProofIntakeError):
        build_proof_intake_index(
            intake_id="",
            audit_timestamp="2026-04-28T12:00:00Z",
            candidates_by_kind={},
        )


def test_pass_path_selects_each_kind_with_ok():
    idx = build_proof_intake_index(
        intake_id="pii-1",
        audit_timestamp="2026-04-28T12:00:00Z",
        candidates_by_kind=_all_kinds_one_each(),
    )
    assert idx["overall_status"] == "ok"
    assert idx["reason_code"] == "PROOF_INTAKE_OK"
    for kind in REQUIRED_PROOF_KINDS:
        sel = idx["selections"][kind]
        assert sel["selection_status"] == "selected"
        assert sel["reason_code"] == "PROOF_INTAKE_OK"
        assert sel["selected_artifact_id"] == f"{kind}-1"


# ---- OC-02 red team: missing / stale / duplicate / conflict ----


def test_missing_kind_blocks_overall():
    candidates = _all_kinds_one_each()
    candidates["loop_proof_bundle"] = []
    idx = build_proof_intake_index(
        intake_id="pii-missing",
        audit_timestamp="2026-04-28T12:00:00Z",
        candidates_by_kind=candidates,
    )
    assert idx["overall_status"] == "blocked"
    assert idx["selections"]["loop_proof_bundle"]["selection_status"] == "missing"
    assert (
        idx["selections"]["loop_proof_bundle"]["reason_code"]
        == "PROOF_INTAKE_MISSING"
    )


def test_stale_proof_rejected_via_digest_mismatch():
    candidates = _all_kinds_one_each()
    bad = _candidate("loop_proof_bundle", "1")
    bad["producer_input_digest"] = "deadbeef"  # mismatched
    candidates["loop_proof_bundle"] = [bad]
    idx = build_proof_intake_index(
        intake_id="pii-stale",
        audit_timestamp="2026-04-28T12:00:00Z",
        candidates_by_kind=candidates,
    )
    sel = idx["selections"]["loop_proof_bundle"]
    assert sel["selection_status"] == "stale"
    assert sel["reason_code"] == "PROOF_INTAKE_STALE_DIGEST_MISMATCH"
    assert idx["overall_status"] == "blocked"


def test_duplicate_proof_blocks_kind():
    candidates = _all_kinds_one_each()
    dup = _candidate("loop_proof_bundle", "1")
    candidates["loop_proof_bundle"] = [dup, dict(dup)]
    idx = build_proof_intake_index(
        intake_id="pii-dup",
        audit_timestamp="2026-04-28T12:00:00Z",
        candidates_by_kind=candidates,
    )
    sel = idx["selections"]["loop_proof_bundle"]
    assert sel["selection_status"] == "duplicate"
    assert sel["reason_code"] == "PROOF_INTAKE_DUPLICATE"
    assert idx["overall_status"] == "blocked"


def test_conflicting_proof_blocks_kind():
    candidates = _all_kinds_one_each()
    a = _candidate("loop_proof_bundle", "A")
    b = _candidate("loop_proof_bundle", "B")
    # different artifact IDs, different inputs/digests => conflict
    candidates["loop_proof_bundle"] = [a, b]
    idx = build_proof_intake_index(
        intake_id="pii-conflict",
        audit_timestamp="2026-04-28T12:00:00Z",
        candidates_by_kind=candidates,
    )
    sel = idx["selections"]["loop_proof_bundle"]
    assert sel["selection_status"] == "conflict"
    assert sel["reason_code"] == "PROOF_INTAKE_CONFLICT"
    assert idx["overall_status"] == "blocked"


def test_superseded_picks_latest_among_agreeing_candidates():
    # Two candidates that share digest (same producer_inputs) but
    # differ in artifact_id and timestamp. The intake must pick the
    # latest deterministically.
    candidates = _all_kinds_one_each()
    inputs = {"kind": "loop_proof_bundle", "shared": "value"}
    digest = _digest(inputs)
    older = {
        "artifact_id": "loop_proof_bundle-OLD",
        "producer_inputs": inputs,
        "producer_input_digest": digest,
        "generated_at": "2026-04-28T11:00:00Z",
    }
    newer = {
        "artifact_id": "loop_proof_bundle-NEW",
        "producer_inputs": inputs,
        "producer_input_digest": digest,
        "generated_at": "2026-04-28T12:00:00Z",
    }
    candidates["loop_proof_bundle"] = [older, newer]
    idx = build_proof_intake_index(
        intake_id="pii-supersede",
        audit_timestamp="2026-04-28T12:30:00Z",
        candidates_by_kind=candidates,
    )
    sel = idx["selections"]["loop_proof_bundle"]
    assert sel["selected_artifact_id"] == "loop_proof_bundle-NEW"
    assert sel["selection_status"] == "selected"
    rejected_ids = {r["artifact_id"] for r in sel["rejected_candidates"]}
    assert "loop_proof_bundle-OLD" in rejected_ids
    rejected_codes = {r["reason_code"] for r in sel["rejected_candidates"]}
    assert "PROOF_INTAKE_SUPERSEDED" in rejected_codes


def test_non_authority_assertions_present():
    idx = build_proof_intake_index(
        intake_id="pii-1",
        audit_timestamp="2026-04-28T12:00:00Z",
        candidates_by_kind=_all_kinds_one_each(),
    )
    assert "preparatory_only" in idx["non_authority_assertions"]
    assert "not_control_authority" in idx["non_authority_assertions"]
    assert "not_certification_authority" in idx["non_authority_assertions"]
