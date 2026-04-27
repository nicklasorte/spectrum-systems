"""NT-19..21: Certification delta proof — added/removed/changed detection.

Red-team: hidden delta — same status, swapped digest; same owner,
swapped reason; silent removal of stale evidence; same filename, different
content.
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.certification_delta import (
    CertificationDeltaError,
    build_certification_delta_index,
)


def _index(
    *,
    eval_ref="evl-1",
    lineage_ref="lin-1",
    replay_ref="rpl-1",
    control_ref="cde-1",
    enforcement_ref="sel-1",
    asp_ref="asp-1",
    reg_ref="reg-1",
    tier_ref="tier-1",
    status="ready",
    blocking_reason_canonical="CERT_OK",
    owning_system="GOV",
):
    return {
        "artifact_type": "certification_evidence_index",
        "index_id": "cei-x",
        "trace_id": "t1",
        "status": status,
        "blocking_reason_canonical": blocking_reason_canonical,
        "owning_system": owning_system,
        "references": {
            "eval_summary_ref": eval_ref,
            "lineage_summary_ref": lineage_ref,
            "replay_summary_ref": replay_ref,
            "control_decision_ref": control_ref,
            "enforcement_action_ref": enforcement_ref,
            "authority_shape_preflight_ref": asp_ref,
            "registry_validation_ref": reg_ref,
            "artifact_tier_validation_ref": tier_ref,
        },
    }


def test_unchanged_indexes_yield_ok_delta():
    delta = build_certification_delta_index(
        delta_id="d1",
        trace_id="t1",
        previous_evidence_index=_index(),
        current_evidence_index=_index(),
    )
    assert delta["delta_risk"] == "none"
    assert delta["reason_code"] == "CERTIFICATION_DELTA_OK"
    assert delta["blocking_reasons"] == []


def test_swap_eval_ref_with_same_status_pass_is_detected():
    """Red team: status pass → pass, but eval ref swapped silently."""
    prev = _index(eval_ref="evl-OLD")
    curr = _index(eval_ref="evl-NEW")
    delta = build_certification_delta_index(
        delta_id="d2",
        trace_id="t1",
        previous_evidence_index=prev,
        current_evidence_index=curr,
    )
    assert delta["delta_risk"] in {"medium", "high"}
    assert delta["reason_code"] == "CERTIFICATION_DELTA_CHANGED_DIGEST"
    keys = [d["ref_key"] for d in delta["changed_digest"]]
    assert "eval_summary_ref" in keys


def test_swap_replay_ref_detected():
    delta = build_certification_delta_index(
        delta_id="d3",
        trace_id="t1",
        previous_evidence_index=_index(replay_ref="rpl-OLD"),
        current_evidence_index=_index(replay_ref="rpl-NEW"),
    )
    assert delta["delta_risk"] in {"medium", "high"}
    keys = [d["ref_key"] for d in delta["changed_digest"]]
    assert "replay_summary_ref" in keys


def test_changed_status_is_high_risk():
    """When the certification status changed (ready → blocked) the delta
    must be high risk."""
    delta = build_certification_delta_index(
        delta_id="d4",
        trace_id="t1",
        previous_evidence_index=_index(status="ready"),
        current_evidence_index=_index(
            status="blocked", blocking_reason_canonical="EVAL_FAILURE"
        ),
    )
    assert delta["delta_risk"] == "high"
    assert delta["reason_code"] in {
        "CERTIFICATION_DELTA_CHANGED_STATUS",
        "CERTIFICATION_DELTA_CHANGED_REASON",
    }


def test_changed_canonical_reason_detected():
    delta = build_certification_delta_index(
        delta_id="d5",
        trace_id="t1",
        previous_evidence_index=_index(blocking_reason_canonical="EVAL_FAILURE"),
        current_evidence_index=_index(blocking_reason_canonical="REPLAY_MISMATCH"),
    )
    assert delta["changed_reason"]
    assert delta["delta_risk"] == "high"


def test_changed_owner_system_detected():
    delta = build_certification_delta_index(
        delta_id="d6",
        trace_id="t1",
        previous_evidence_index=_index(owning_system="GOV"),
        current_evidence_index=_index(owning_system="OTHER"),
    )
    assert delta["changed_owner"]
    assert delta["delta_risk"] == "high"


def test_silent_removal_of_evidence_blocks_unless_explained():
    prev = _index(enforcement_ref="sel-1")
    curr = _index(enforcement_ref=None)
    delta = build_certification_delta_index(
        delta_id="d7",
        trace_id="t1",
        previous_evidence_index=prev,
        current_evidence_index=curr,
    )
    assert delta["delta_risk"] in {"medium", "high"}
    assert delta["reason_code"] == "CERTIFICATION_DELTA_REMOVED_UNEXPLAINED"


def test_explained_removal_still_records_but_does_not_block():
    prev = _index(enforcement_ref="sel-1")
    curr = _index(enforcement_ref=None)
    delta = build_certification_delta_index(
        delta_id="d8",
        trace_id="t1",
        previous_evidence_index=prev,
        current_evidence_index=curr,
        explanations=[
            {
                "kind": "removed",
                "ref_key": "enforcement_action_ref",
                "rationale": "non-state-changing run, enforcement_ref not required",
            }
        ],
    )
    # Removal recorded, but flagged explained
    assert delta["removed"]
    assert delta["removed"][0]["explained"] is True
    # No blocking reason since it was explained
    assert delta["reason_code"] != "CERTIFICATION_DELTA_REMOVED_UNEXPLAINED"


def test_unknown_baseline_is_high_risk():
    delta = build_certification_delta_index(
        delta_id="d9",
        trace_id="t1",
        previous_evidence_index=None,
        current_evidence_index=_index(),
    )
    assert delta["delta_risk"] == "high"
    assert delta["reason_code"] == "CERTIFICATION_DELTA_UNKNOWN_BASELINE"


def test_added_evidence_without_explanation_blocks():
    prev = _index(enforcement_ref=None)
    curr = _index(enforcement_ref="sel-NEW")
    delta = build_certification_delta_index(
        delta_id="dA",
        trace_id="t1",
        previous_evidence_index=prev,
        current_evidence_index=curr,
    )
    # Addition without explanation should block
    assert delta["reason_code"] == "CERTIFICATION_DELTA_ADDED_UNEXPLAINED"


def test_invalid_inputs_raise():
    with pytest.raises(CertificationDeltaError):
        build_certification_delta_index(
            delta_id="",
            trace_id="t1",
            previous_evidence_index=_index(),
            current_evidence_index=_index(),
        )
    with pytest.raises(CertificationDeltaError):
        build_certification_delta_index(
            delta_id="d",
            trace_id="t",
            previous_evidence_index=_index(),
            current_evidence_index="not a mapping",  # type: ignore[arg-type]
        )


def test_unchanged_refs_recorded():
    delta = build_certification_delta_index(
        delta_id="dB",
        trace_id="t1",
        previous_evidence_index=_index(),
        current_evidence_index=_index(),
    )
    assert "eval_summary_ref" in delta["unchanged"]
    assert "replay_summary_ref" in delta["unchanged"]
