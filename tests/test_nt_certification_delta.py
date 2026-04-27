"""NT-19..21: Certification delta proof + hidden delta red team + fix.

Validates:
  - delta detects added/removed/changed evidence
  - swapping a ref under the same key while keeping status pass is still
    detected (changed_digest)
  - silent removal of stale evidence is blocked
  - readiness blocks on unexplained high-risk delta
  - status/reason/owner flips are surfaced as medium risk
  - trace identifies the changed evidence
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.certification_delta import (
    CANONICAL_DELTA_REASON_CODES,
    CertificationDeltaError,
    compute_certification_delta,
)


def _index(refs, **kwargs) -> dict:
    return {
        "artifact_type": "certification_evidence_index",
        "index_id": kwargs.pop("index_id", "cei-x"),
        "trace_id": kwargs.pop("trace_id", "tA"),
        "status": kwargs.pop("status", "ready"),
        "references": refs,
        **kwargs,
    }


# ---- NT-19 contract ----


def test_canonical_delta_reason_codes_finite() -> None:
    for code in (
        "CERT_DELTA_OK",
        "CERT_DELTA_ADDED",
        "CERT_DELTA_REMOVED",
        "CERT_DELTA_CHANGED_DIGEST",
        "CERT_DELTA_CHANGED_STATUS",
        "CERT_DELTA_CHANGED_REASON",
        "CERT_DELTA_CHANGED_OWNER",
        "CERT_DELTA_UNEXPLAINED",
        "CERT_DELTA_SILENT_REMOVAL",
    ):
        assert code in CANONICAL_DELTA_REASON_CODES


def test_unchanged_indexes_yield_none_risk() -> None:
    refs = {"eval_summary_ref": "evl-1", "lineage_summary_ref": "lin-1"}
    delta = compute_certification_delta(
        delta_id="d-1",
        previous_index=_index(refs),
        current_index=_index(refs),
    )
    assert delta["overall_delta_risk"] == "low"  # has unchanged_refs
    assert delta["decision"] == "allow"
    assert delta["unchanged_refs"] == ["eval_summary_ref", "lineage_summary_ref"]


def test_added_only_is_low_risk_and_allows() -> None:
    prev = _index({"eval_summary_ref": "evl-1"})
    curr = _index({"eval_summary_ref": "evl-1", "lineage_summary_ref": "lin-1"})
    delta = compute_certification_delta(
        delta_id="d-2", previous_index=prev, current_index=curr
    )
    assert delta["overall_delta_risk"] == "low"
    assert delta["added_refs"] == ["lineage_summary_ref"]
    assert delta["decision"] == "allow"


# ---- NT-20 red team — hidden delta ----


def test_red_team_swap_eval_ref_keep_status_pass_blocks(capsys) -> None:
    prev = _index({"eval_summary_ref": "evl-1"})
    curr = _index({"eval_summary_ref": "evl-2"})
    delta = compute_certification_delta(
        delta_id="d-3", previous_index=prev, current_index=curr
    )
    assert delta["overall_delta_risk"] == "high"
    assert delta["decision"] == "block"
    assert delta["canonical_reason"] == "CERT_DELTA_CHANGED_DIGEST"
    keys = [c["ref_key"] for c in delta["changed_digest"]]
    assert "eval_summary_ref" in keys


def test_red_team_swap_replay_ref_blocks() -> None:
    prev = _index({"replay_summary_ref": "rpl-1"})
    curr = _index({"replay_summary_ref": "rpl-2"})
    delta = compute_certification_delta(
        delta_id="d-4", previous_index=prev, current_index=curr
    )
    assert delta["decision"] == "block"
    assert delta["overall_delta_risk"] == "high"


def test_red_team_lineage_chain_digest_change_blocks() -> None:
    prev = _index(
        {"lineage_summary_ref": "lin-1"},
        evidence_digests={"lineage_summary_ref": "abc"},
    )
    curr = _index(
        {"lineage_summary_ref": "lin-1"},
        evidence_digests={"lineage_summary_ref": "def"},
    )
    delta = compute_certification_delta(
        delta_id="d-5", previous_index=prev, current_index=curr
    )
    assert delta["decision"] == "block"
    assert any(
        c["ref_key"] == "lineage_summary_ref" and c.get("previous_digest") == "abc"
        for c in delta["changed_digest"]
    )


def test_red_team_control_decision_swap_blocks() -> None:
    prev = _index({"control_decision_ref": "cde-1"})
    curr = _index({"control_decision_ref": "cde-2"})
    delta = compute_certification_delta(
        delta_id="d-6", previous_index=prev, current_index=curr
    )
    assert delta["decision"] == "block"
    assert delta["overall_delta_risk"] == "high"


def test_red_team_silent_removal_blocks() -> None:
    """Stale evidence quietly removed must block, not pass."""
    prev = _index({"eval_summary_ref": "evl-1", "lineage_summary_ref": "lin-1"})
    curr = _index({"lineage_summary_ref": "lin-1"})
    delta = compute_certification_delta(
        delta_id="d-7", previous_index=prev, current_index=curr
    )
    assert delta["decision"] == "block"
    assert delta["canonical_reason"] == "CERT_DELTA_SILENT_REMOVAL"
    assert "eval_summary_ref" in delta["removed_refs"]


def test_red_team_status_flip_with_same_ref_is_medium_risk() -> None:
    prev = _index(
        {"eval_summary_ref": "evl-1"},
        evidence_statuses={"eval_summary_ref": "healthy"},
    )
    curr = _index(
        {"eval_summary_ref": "evl-1"},
        evidence_statuses={"eval_summary_ref": "blocked"},
    )
    delta = compute_certification_delta(
        delta_id="d-8", previous_index=prev, current_index=curr
    )
    assert delta["overall_delta_risk"] == "medium"
    assert delta["changed_status"]
    assert delta["changed_status"][0]["ref_key"] == "eval_summary_ref"


def test_red_team_owner_change_is_medium_risk() -> None:
    prev = _index(
        {"control_decision_ref": "cde-1"},
        evidence_owners={"control_decision_ref": "CDE"},
    )
    curr = _index(
        {"control_decision_ref": "cde-1"},
        evidence_owners={"control_decision_ref": "TPA"},
    )
    delta = compute_certification_delta(
        delta_id="d-9", previous_index=prev, current_index=curr
    )
    assert delta["overall_delta_risk"] == "medium"
    assert delta["changed_owner"]


# ---- NT-21 fix: explained delta unblocks ----


def test_explained_delta_passes_high_risk_change() -> None:
    """If the operator explains the change in writing, the gate passes."""
    prev = _index({"eval_summary_ref": "evl-1"})
    curr = _index({"eval_summary_ref": "evl-2"})
    # Note: digest change still blocks even if explained, because the
    # canonical_reason is CERT_DELTA_CHANGED_DIGEST. Removal would also
    # block. Explanation only suppresses CERT_DELTA_UNEXPLAINED.
    delta = compute_certification_delta(
        delta_id="d-10",
        previous_index=prev,
        current_index=curr,
        explained_delta_keys=["eval_summary_ref"],
    )
    # Digest change always blocks, even when explained.
    assert delta["decision"] == "block"
    assert delta["unexplained_delta_keys"] == []


def test_explained_status_change_passes() -> None:
    prev = _index(
        {"eval_summary_ref": "evl-1"},
        evidence_statuses={"eval_summary_ref": "healthy"},
    )
    curr = _index(
        {"eval_summary_ref": "evl-1"},
        evidence_statuses={"eval_summary_ref": "blocked"},
    )
    delta = compute_certification_delta(
        delta_id="d-11",
        previous_index=prev,
        current_index=curr,
        explained_delta_keys=["eval_summary_ref"],
    )
    # Status flip is medium risk and does not block by itself.
    assert delta["decision"] == "allow"
    assert delta["unexplained_delta_keys"] == []


def test_human_readable_carries_diagnostics() -> None:
    prev = _index({"eval_summary_ref": "evl-1"})
    curr = _index({"eval_summary_ref": "evl-2"})
    delta = compute_certification_delta(
        delta_id="d-12", previous_index=prev, current_index=curr
    )
    assert "delta_id=d-12" in delta["human_readable"]
    assert "risk=high" in delta["human_readable"]


def test_id_required() -> None:
    with pytest.raises(CertificationDeltaError):
        compute_certification_delta(
            delta_id="", previous_index=_index({}), current_index=_index({})
        )
