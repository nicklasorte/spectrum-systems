"""Tests for FRE authority-shape repair-candidate generator (AEX-FRE-AUTH-SHAPE-01).

Covers:

* Manifest-entry decision diagnostic produces a candidate proposing a safe
  replacement.
* Generated report-heading diagnostic produces a content-only repair.
* Broad exclusion proposals (``docs/**``) are rejected.
* Diagnostics missing a vocabulary-suggested replacement produce an
  ``incomplete`` candidate carrying the missing-safe-replacement reason
  code rather than a guessed rename.
* Owner-elevation proposals are rejected.
* Schema validation of every emitted candidate.
"""

from __future__ import annotations

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.fix_engine.authority_shape_repair import (
    REASON_MISSING_SAFE_REPLACEMENT,
    REJECT_BROAD_EXCLUSION,
    REJECT_OWNER_ELEVATION,
    FREAuthorityShapeRepairError,
    RepairOptions,
    generate_repair_candidate,
    generate_repair_candidates,
)


def _diag(**overrides):
    base = {
        "status": "block",
        "file": "contracts/standards-manifest.json",
        "line": 12,
        "symbol": "allow_decision_proof",
        "cluster": "decision",
        "canonical_owner": "JDX",
        "canonical_owners": ["JDX", "CDE"],
        "current_context": "manifest",
        "owner_context_allowed": False,
        "context_kind": "manifest",
        "fail_closed_reason_code": "protected_term_in_non_owner_manifest_entry",
        "suggested_safe_replacements": [
            "signal",
            "observation",
            "recommendation",
        ],
        "rationale": "Decision authority belongs to JDX/CDE.",
    }
    base.update(overrides)
    return base


def _admission(diags):
    return {
        "artifact_type": "authority_shape_admission_result",
        "schema_version": "1.0.0",
        "status": "block",
        "mode": "enforce",
        "scanned_files": ["contracts/standards-manifest.json"],
        "skipped_files": [],
        "diagnostics": diags,
        "summary": {"violation_count": len(diags), "block_count": len(diags), "pass_count": 0},
        "non_authority_assertions": ["aex_admission_is_non_owning"],
    }


def test_manifest_decision_candidate_proposes_safe_replacement():
    diag = _diag()
    candidate = generate_repair_candidate(
        diagnostic=diag,
        admission_artifact_id="auth-shape-01",
    )
    validate_artifact(candidate, "authority_shape_repair_candidate")
    assert candidate["candidate_status"] == "ready"
    assert candidate["safe_replacement"]
    assert "decision" not in candidate["safe_replacement"].lower()
    assert candidate["rename_kind"] == "identifier_breaking"
    assert candidate["risk_level"] in {"medium", "high"}
    assert "tests/test_aex_authority_shape_admission.py" in candidate["required_tests"]
    assert "tests/test_fre_authority_shape_repair.py" in candidate["required_tests"]


def test_report_heading_candidate_is_content_only():
    diag = _diag(
        file="docs/governance-reports/contract-enforcement-report.md",
        line=1,
        symbol="Contract Enforcement Report",
        cluster="enforcement",
        canonical_owner="SEL",
        canonical_owners=["SEL", "ENF"],
        context_kind="report",
        current_context="report",
        fail_closed_reason_code="protected_term_in_generated_report_heading",
        suggested_safe_replacements=[
            "enforcement_signal",
            "compliance_observation",
        ],
    )
    candidate = generate_repair_candidate(
        diagnostic=diag,
        admission_artifact_id="auth-shape-01",
    )
    validate_artifact(candidate, "authority_shape_repair_candidate")
    assert candidate["rename_kind"] == "content_only"
    assert candidate["risk_level"] == "low"
    assert "Compliance" in candidate["safe_replacement"] or "compliance" in candidate["safe_replacement"]
    assert candidate["candidate_status"] == "ready"


def test_broad_exclusion_proposal_is_rejected():
    diag = _diag(proposed_exclusion="docs/**")
    candidate = generate_repair_candidate(
        diagnostic=diag,
        admission_artifact_id="auth-shape-01",
    )
    validate_artifact(candidate, "authority_shape_repair_candidate")
    assert candidate["candidate_status"] == "rejected"
    assert candidate["rejection_reason"] == REJECT_BROAD_EXCLUSION
    assert REJECT_BROAD_EXCLUSION in candidate["fail_closed_reason_codes"]


def test_owner_elevation_proposal_is_rejected():
    diag = _diag(propose_owner_elevation=True)
    candidate = generate_repair_candidate(
        diagnostic=diag,
        admission_artifact_id="auth-shape-01",
    )
    validate_artifact(candidate, "authority_shape_repair_candidate")
    assert candidate["candidate_status"] == "rejected"
    assert candidate["rejection_reason"] == REJECT_OWNER_ELEVATION


def test_missing_safe_replacement_produces_incomplete_candidate():
    diag = _diag(suggested_safe_replacements=[])
    candidate = generate_repair_candidate(
        diagnostic=diag,
        admission_artifact_id="auth-shape-01",
    )
    validate_artifact(candidate, "authority_shape_repair_candidate")
    assert candidate["candidate_status"] == "incomplete"
    assert REASON_MISSING_SAFE_REPLACEMENT in candidate["fail_closed_reason_codes"]
    assert candidate["safe_replacement"]


def test_generate_repair_candidates_only_handles_block_diagnostics():
    diag_block = _diag()
    diag_pass = _diag(status="pass")
    candidates = generate_repair_candidates(
        admission_result=_admission([diag_block, diag_pass]),
    )
    assert len(candidates) == 1
    assert candidates[0]["candidate_status"] == "ready"


def test_generate_rejects_non_admission_input():
    with pytest.raises(FREAuthorityShapeRepairError):
        generate_repair_candidates(
            admission_result={"artifact_type": "something_else", "diagnostics": []},
        )


def test_owner_elevation_flag_is_internal_only():
    """Even when allow_owner_elevation is set, the candidate stays advisory."""
    diag = _diag(propose_owner_elevation=True)
    candidate = generate_repair_candidate(
        diagnostic=diag,
        admission_artifact_id="auth-shape-01",
        options=RepairOptions(allow_owner_elevation=True),
    )
    validate_artifact(candidate, "authority_shape_repair_candidate")
    assert candidate["candidate_status"] in {"ready", "incomplete"}
    assert "fre_repair_candidate_is_advisory" in candidate["non_authority_assertions"]
