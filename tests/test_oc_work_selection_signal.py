"""OC-13..15: Work selection signal unit + red-team tests."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.work_selection_signal import (
    JUSTIFICATION_SCORES,
    REJECTED_JUSTIFICATIONS,
    SUPPORTED_JUSTIFICATIONS,
    WorkSelectionError,
    build_work_selection_record,
)


def test_record_id_required():
    with pytest.raises(WorkSelectionError):
        build_work_selection_record(
            record_id="",
            audit_timestamp="2026-04-28T00:00:00Z",
            candidates=[],
        )


def test_supported_set_finite():
    assert "current_bottleneck" in SUPPORTED_JUSTIFICATIONS
    assert "failing_trust_regression" in SUPPORTED_JUSTIFICATIONS
    assert "expansion_unsupported" not in SUPPORTED_JUSTIFICATIONS


def test_failing_trust_regression_outranks_other_supports():
    rec = build_work_selection_record(
        record_id="wsr-1",
        audit_timestamp="2026-04-28T00:00:00Z",
        candidates=[
            {
                "work_item_id": "BOTL-FIX",
                "justification_kind": "current_bottleneck",
                "evidence_ref": "bc-1",
            },
            {
                "work_item_id": "TRUST-REG-FIX",
                "justification_kind": "failing_trust_regression",
                "evidence_ref": "trp-1",
            },
        ],
    )
    assert rec["recommended_work_item_id"] == "TRUST-REG-FIX"
    assert rec["selection_status"] == "selected"


# ---- OC-14 red team: expansion / low-trust rejected ----


def test_expansion_unsupported_rejected_with_reason():
    rec = build_work_selection_record(
        record_id="wsr-2",
        audit_timestamp="2026-04-28T00:00:00Z",
        candidates=[
            {
                "work_item_id": "EXPAND-X",
                "justification_kind": "expansion_unsupported",
                "evidence_ref": None,
            }
        ],
    )
    assert rec["selection_status"] == "no_recommendation"
    assert rec["recommended_work_item_id"] is None
    bad = rec["candidates"][0]
    assert not bad["accepted"]
    assert bad["reason_code"] == "WORK_SELECTION_REJECTED_EXPANSION"


def test_low_trust_rejected():
    rec = build_work_selection_record(
        record_id="wsr-3",
        audit_timestamp="2026-04-28T00:00:00Z",
        candidates=[
            {
                "work_item_id": "RISKY-X",
                "justification_kind": "low_trust",
                "evidence_ref": "x-1",
            }
        ],
    )
    bad = rec["candidates"][0]
    assert not bad["accepted"]
    assert bad["reason_code"] == "WORK_SELECTION_REJECTED_LOW_TRUST"


def test_supported_justification_without_evidence_blocked():
    rec = build_work_selection_record(
        record_id="wsr-4",
        audit_timestamp="2026-04-28T00:00:00Z",
        candidates=[
            {
                "work_item_id": "BOTL-FIX",
                "justification_kind": "current_bottleneck",
                "evidence_ref": None,
            }
        ],
    )
    bad = rec["candidates"][0]
    assert not bad["accepted"]
    assert bad["reason_code"] == "WORK_SELECTION_MISSING_EVIDENCE"
    assert rec["selection_status"] == "no_recommendation"


def test_unknown_justification_blocked():
    rec = build_work_selection_record(
        record_id="wsr-5",
        audit_timestamp="2026-04-28T00:00:00Z",
        candidates=[
            {
                "work_item_id": "MYSTERY",
                "justification_kind": "vibes",
                "evidence_ref": "x-1",
            }
        ],
    )
    bad = rec["candidates"][0]
    assert not bad["accepted"]
    assert bad["reason_code"] == "WORK_SELECTION_BLOCKED"


def test_scoring_table_has_zero_for_rejected_kinds():
    for kind in REJECTED_JUSTIFICATIONS:
        assert JUSTIFICATION_SCORES[kind] == 0.0


def test_empty_candidates_yield_unknown():
    rec = build_work_selection_record(
        record_id="wsr-empty",
        audit_timestamp="2026-04-28T00:00:00Z",
        candidates=[],
    )
    assert rec["selection_status"] == "unknown"
    assert rec["recommended_work_item_id"] is None
