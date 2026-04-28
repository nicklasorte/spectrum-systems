"""OC-19..21: Cleanup candidate report unit + red-team tests."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.cleanup_candidate_report import (
    CANONICAL_REASON_CODES,
    REQUIRED_PROOF_EVIDENCE_KINDS,
    CleanupCandidateError,
    build_cleanup_candidate_report,
)


def test_report_id_required():
    with pytest.raises(CleanupCandidateError):
        build_cleanup_candidate_report(
            report_id="",
            audit_timestamp="2026-04-28T00:00:00Z",
            candidates=[],
        )


def test_advisory_only_assertions_present():
    rep = build_cleanup_candidate_report(
        report_id="cleanup-1",
        audit_timestamp="2026-04-28T00:00:00Z",
        candidates=[],
    )
    assert "advisory_only" in rep["non_authority_assertions"]
    assert "no_deletion" in rep["non_authority_assertions"]


def test_keep_default_classification():
    rep = build_cleanup_candidate_report(
        report_id="cleanup-1",
        audit_timestamp="2026-04-28T00:00:00Z",
        candidates=[
            {
                "artifact_path": "outputs/some_run/notes.txt",
                "artifact_kind": "free_text",
            }
        ],
    )
    assert rep["candidates"][0]["classification"] == "keep"


# ---- OC-20 red team: required proof evidence forced to never_delete ----


def test_required_proof_kind_forced_to_never_delete_even_if_marked_archive():
    rep = build_cleanup_candidate_report(
        report_id="cleanup-redteam",
        audit_timestamp="2026-04-28T00:00:00Z",
        candidates=[
            {
                "artifact_path": "outputs/proof/lpb-old.json",
                "artifact_kind": "loop_proof_bundle",
                "proposed_classification": "candidate_archive",
            }
        ],
    )
    c = rep["candidates"][0]
    assert c["classification"] == "never_delete"
    assert c["reason_code"] == "CLEANUP_NEVER_DELETE_REQUIRED_PROOF"


def test_canonical_owner_path_forced_to_never_delete():
    rep = build_cleanup_candidate_report(
        report_id="cleanup-redteam",
        audit_timestamp="2026-04-28T00:00:00Z",
        candidates=[
            {
                "artifact_path": "spectrum_systems/modules/runtime/closure_decision_engine.py",
                "artifact_kind": "module_file",
                "proposed_classification": "candidate_archive",
            }
        ],
    )
    c = rep["candidates"][0]
    assert c["classification"] == "never_delete"


def test_invalid_classification_forced_to_unknown_blocked():
    rep = build_cleanup_candidate_report(
        report_id="cleanup-amb",
        audit_timestamp="2026-04-28T00:00:00Z",
        candidates=[
            {
                "artifact_path": "outputs/random/file.json",
                "artifact_kind": "intermediate",
                "proposed_classification": "delete_now",
            }
        ],
    )
    c = rep["candidates"][0]
    assert c["classification"] == "unknown_blocked"
    assert c["reason_code"] == "CLEANUP_UNKNOWN_BLOCKED_AMBIGUOUS"


def test_required_proof_kinds_finite_and_include_proof_intake():
    assert "proof_intake_index" in REQUIRED_PROOF_EVIDENCE_KINDS
    assert "loop_proof_bundle" in REQUIRED_PROOF_EVIDENCE_KINDS
    assert "trust_regression_pack" in REQUIRED_PROOF_EVIDENCE_KINDS


def test_canonical_reason_codes_include_never_delete_required_proof():
    assert "CLEANUP_NEVER_DELETE_REQUIRED_PROOF" in CANONICAL_REASON_CODES
    assert "CLEANUP_UNKNOWN_BLOCKED_AMBIGUOUS" in CANONICAL_REASON_CODES
