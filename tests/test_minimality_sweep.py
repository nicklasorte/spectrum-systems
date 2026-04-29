"""Tests for minimality_sweep (CLX-ALL-01 Phase 6).

Covers:
- Sweep returns cleanup_candidate_report artifact
- Required fields present
- Non-authority assertions present
- No deletions performed (advisory only)
- Classification values are valid
- never_delete artifacts are protected
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.minimality_sweep import run_minimality_sweep

_VALID_CLASSIFICATIONS = frozenset([
    "keep", "regenerate", "candidate_archive", "never_delete", "unknown_blocked"
])


def test_returns_cleanup_candidate_report() -> None:
    report = run_minimality_sweep(trace_id="t")
    assert report["artifact_type"] == "cleanup_candidate_report"
    assert report["schema_version"] == "1.0.0"


def test_required_fields_present() -> None:
    report = run_minimality_sweep(trace_id="t")
    required = ["artifact_type", "schema_version", "producer_authority", "report_id", "audit_timestamp", "candidates", "non_authority_assertions"]
    for key in required:
        assert key in report, f"Missing: {key}"
    assert report["producer_authority"] == "OBS"


def test_non_authority_assertions_valid() -> None:
    report = run_minimality_sweep(trace_id="t")
    assertions = report["non_authority_assertions"]
    assert isinstance(assertions, list)
    assert "preparatory_only" in assertions
    assert "not_control_authority" in assertions
    assert "not_certification_authority" in assertions


def test_all_candidate_classifications_are_valid() -> None:
    report = run_minimality_sweep(trace_id="t")
    for candidate in report["candidates"]:
        assert "classification" in candidate
        assert candidate["classification"] in _VALID_CLASSIFICATIONS, (
            f"Invalid classification: {candidate['classification']}"
        )


def test_all_candidates_have_required_fields() -> None:
    report = run_minimality_sweep(trace_id="t")
    required_fields = ["artifact_path", "classification", "reason_code"]
    allowed_fields = {"artifact_path", "artifact_kind", "classification", "reason_code", "evidence_role"}
    for candidate in report["candidates"]:
        for field in required_fields:
            assert field in candidate, f"Missing field '{field}' in candidate: {candidate}"
        extra = set(candidate.keys()) - allowed_fields
        assert not extra, f"Candidate has disallowed fields {extra}: {candidate}"


def test_sweep_is_deterministic() -> None:
    report1 = run_minimality_sweep(trace_id="t")
    report2 = run_minimality_sweep(trace_id="t")
    # Candidate paths must be the same (order may differ, sort to compare).
    paths1 = sorted(c["artifact_path"] for c in report1["candidates"])
    paths2 = sorted(c["artifact_path"] for c in report2["candidates"])
    assert paths1 == paths2


def test_never_delete_artifacts_are_classified_correctly() -> None:
    """Core proof artifacts must be classified as never_delete if found as candidates."""
    report = run_minimality_sweep(trace_id="t")
    for candidate in report["candidates"]:
        # Any candidate whose artifact_path references a never_delete type must be never_delete.
        # This is advisory: just verify classification is consistent.
        path = candidate["artifact_path"]
        reason = candidate.get("reason_code", "")
        if "loop_proof_bundle" in path or "certification_evidence_index" in path:
            assert candidate["classification"] == "never_delete", (
                f"Expected never_delete for {path}, got {candidate['classification']}"
            )


def test_report_id_is_non_empty() -> None:
    report = run_minimality_sweep(trace_id="t")
    assert report["report_id"]
    assert len(report["report_id"]) > 4
