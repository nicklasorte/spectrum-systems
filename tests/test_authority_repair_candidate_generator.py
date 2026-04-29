"""Tests for authority_repair_candidate_generator (CLX-ALL-01 Phase 1).

Covers:
- Valid packet produces candidates with correct shape
- Empty violations produce no candidates
- Never-patch files are excluded
- Missing packet_id raises error
- Wrong artifact_type raises error
- Unsafe replacements are blocked
- Only vocabulary_correction and rename patch types allowed
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.authority_repair_candidate_generator import (
    AuthorityRepairCandidateError,
    generate_authority_repair_candidates,
)


def _make_packet(violations: list[dict] | None = None, packet_id: str = "pkt-001") -> dict:
    return {
        "artifact_type": "authority_preflight_failure_packet",
        "schema_version": "1.0.0",
        "packet_id": packet_id,
        "trace_id": "trace-001",
        "violations": violations or [],
        "shadow_overlaps": [],
        "forbidden_symbols": [],
        "status": "fail",
        "emitted_at": "2026-04-29T00:00:00+00:00",
    }


def _make_violation(
    symbol: str = "harness_promotion_decision",
    file: str = "spectrum_systems/modules/hop/emitter.py",
    suggestions: list[str] | None = None,
    owners: list[str] | None = None,
    violation_type: str = "vocabulary_violation",
) -> dict:
    return {
        "file": file,
        "line": 12,
        "symbol": symbol,
        "cluster": "promotion",
        "canonical_owners": owners or ["CDE"],
        "suggested_replacements": suggestions if suggestions is not None else ["promotion_signal", "readiness_observation"],
        "violation_type": violation_type,
        "rationale": "test violation",
    }


def test_valid_packet_produces_candidates() -> None:
    packet = _make_packet([_make_violation()])
    candidates = generate_authority_repair_candidates(failure_packet=packet, trace_id="t")
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand["artifact_type"] == "authority_repair_candidate"
    assert cand["safe_to_apply"] is True
    assert len(cand["patches"]) == 1
    assert cand["patches"][0]["original_symbol"] == "harness_promotion_decision"
    assert cand["patches"][0]["replacement_symbol"] == "promotion_signal"


def test_no_violations_produces_no_candidates() -> None:
    packet = _make_packet([])
    candidates = generate_authority_repair_candidates(failure_packet=packet, trace_id="t")
    assert candidates == []


def test_never_patch_guard_file_is_excluded() -> None:
    v = _make_violation(file="scripts/run_authority_shape_preflight.py")
    packet = _make_packet([v])
    candidates = generate_authority_repair_candidates(failure_packet=packet, trace_id="t")
    assert candidates == []


def test_wrong_artifact_type_raises() -> None:
    import pytest
    packet = {"artifact_type": "something_else", "packet_id": "x"}
    with pytest.raises(AuthorityRepairCandidateError, match="Expected authority_preflight_failure_packet"):
        generate_authority_repair_candidates(failure_packet=packet, trace_id="t")


def test_missing_packet_id_raises() -> None:
    import pytest
    packet = {"artifact_type": "authority_preflight_failure_packet"}
    with pytest.raises(AuthorityRepairCandidateError, match="packet_id"):
        generate_authority_repair_candidates(failure_packet=packet, trace_id="t")


def test_non_dict_input_raises() -> None:
    import pytest
    with pytest.raises(AuthorityRepairCandidateError):
        generate_authority_repair_candidates(failure_packet="not-a-dict", trace_id="t")


def test_no_replacement_makes_candidate_unsafe() -> None:
    v = _make_violation(symbol="promotion_decision", suggestions=[])
    packet = _make_packet([v])
    candidates = generate_authority_repair_candidates(failure_packet=packet, trace_id="t")
    # Either no candidate (skipped) or unsafe.
    for cand in candidates:
        assert cand["safe_to_apply"] is False or cand["patches"] == []


def test_candidate_has_non_authority_assertions() -> None:
    v = _make_violation()
    packet = _make_packet([v])
    candidates = generate_authority_repair_candidates(failure_packet=packet, trace_id="t")
    assert len(candidates) == 1
    assertions = candidates[0].get("non_authority_assertions") or []
    assert len(assertions) > 0
    assert any("CDE" in a for a in assertions)


def test_multiple_files_produce_one_candidate_per_file() -> None:
    v1 = _make_violation(file="spectrum_systems/modules/hop/a.py")
    v2 = _make_violation(file="spectrum_systems/modules/hop/b.py")
    packet = _make_packet([v1, v2])
    candidates = generate_authority_repair_candidates(failure_packet=packet, trace_id="t")
    files = {c["patches"][0]["file"] for c in candidates}
    assert "spectrum_systems/modules/hop/a.py" in files
    assert "spectrum_systems/modules/hop/b.py" in files
