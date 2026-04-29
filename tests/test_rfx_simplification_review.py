"""Tests for rfx_simplification_review (RFX-N12)."""

from spectrum_systems.modules.runtime.rfx_simplification_review import (
    assess_rfx_simplification,
)


def _helper(name="rfx_foo", failure_prevented="blocks bad thing", signal_improved="improves X", role="foo", **kw):
    return {"name": name, "failure_prevented": failure_prevented,
            "signal_improved": signal_improved, "role": role, **kw}


# RT-N12: helper with no failure/signal justification → must fail or mark fold.
def test_rt_n12_unjustified_helper_flagged():
    result = assess_rfx_simplification(
        helpers=[{"name": "rfx_orphan", "failure_prevented": "", "signal_improved": "", "role": "orphan"}]
    )
    assert "rfx_simplification_no_justification" in result["reason_codes_emitted"]
    assert result["recommendations"][0]["recommendation"] == "fold_or_deprecate"


def test_rt_n12_justified_helper_kept():
    result = assess_rfx_simplification(helpers=[_helper()])
    assert result["status"] == "complete"
    assert result["recommendations"][0]["recommendation"] == "keep"


def test_duplicate_role_flagged():
    result = assess_rfx_simplification(helpers=[
        _helper(name="rfx_a", role="same_role"),
        _helper(name="rfx_b", role="same_role"),
    ])
    assert "rfx_simplification_duplicate_role" in result["reason_codes_emitted"]
    assert any(r["recommendation"] == "consolidate" for r in result["recommendations"])


def test_empty_input_flagged():
    result = assess_rfx_simplification(helpers=[])
    assert "rfx_simplification_empty_input" in result["reason_codes_emitted"]


def test_missing_name_flagged():
    result = assess_rfx_simplification(helpers=[{"name": "", "failure_prevented": "ok", "signal_improved": "ok", "role": "r"}])
    assert "rfx_simplification_missing_name" in result["reason_codes_emitted"]


def test_signals_justified_count():
    result = assess_rfx_simplification(helpers=[_helper(), _helper(name="rfx_b", role="b")])
    assert result["signals"]["justified_count"] == 2


def test_signals_fold_candidates():
    result = assess_rfx_simplification(helpers=[
        _helper(),
        {"name": "rfx_orphan", "failure_prevented": "", "signal_improved": "", "role": "orphan"},
    ])
    assert result["signals"]["fold_candidates"] == 1


def test_artifact_type():
    result = assess_rfx_simplification(helpers=[_helper()])
    assert result["artifact_type"] == "rfx_simplification_review_result"


def test_non_dict_helper_does_not_raise():
    # P1 fix: non-dict helper rows must emit rfx_simplification_malformed_row, not AttributeError.
    result = assess_rfx_simplification(helpers=["not-a-dict"])
    assert "rfx_simplification_malformed_row" in result["reason_codes_emitted"]
    assert result["artifact_type"] == "rfx_simplification_review_result"


def test_mixed_helpers_malformed_skipped():
    # P1 fix: malformed rows are skipped; valid rows still appear in recommendations.
    result = assess_rfx_simplification(helpers=[_helper(), "bad-row"])
    assert "rfx_simplification_malformed_row" in result["reason_codes_emitted"]
    assert len(result["recommendations"]) == 1
