"""Tests for rfx_bloat_burndown (RFX-N21)."""

from spectrum_systems.modules.runtime.rfx_bloat_burndown import (
    build_rfx_bloat_burndown_report,
)


def _helper(**kw):
    base = {
        "name": "rfx_golden_failure_corpus_v2",
        "justification": "Prevents regression to known historical failures.",
        "responsibility": "golden_corpus",
    }
    base.update(kw)
    return base


# RT-N21: duplicate/bloated helper survives without justification → must flag.
def test_rt_n21_unjustified_helper_flagged():
    result = build_rfx_bloat_burndown_report(
        helpers=[{"name": "rfx_orphan", "justification": "", "responsibility": "orphan"}]
    )
    assert "rfx_bloat_unjustified_helper" in result["reason_codes_emitted"]
    assert result["consolidation_candidates"][0]["action"] == "review_for_removal"


# RT-N21: duplicate responsibility flagged.
def test_rt_n21_duplicate_responsibility_flagged():
    result = build_rfx_bloat_burndown_report(helpers=[
        _helper(name="rfx_a", responsibility="same_role"),
        _helper(name="rfx_b", responsibility="same_role"),
    ])
    assert "rfx_bloat_duplicate_responsibility" in result["reason_codes_emitted"]
    assert any(c["action"] == "consolidate" for c in result["consolidation_candidates"])


def test_superseded_helper_flagged():
    result = build_rfx_bloat_burndown_report(
        helpers=[_helper(superseded_by="rfx_golden_failure_corpus_v2")]
    )
    assert "rfx_bloat_superseded" in result["reason_codes_emitted"]
    assert result["consolidation_candidates"][0]["action"] == "remove"


def test_justified_helper_not_in_candidates():
    result = build_rfx_bloat_burndown_report(helpers=[_helper()])
    assert result["consolidation_candidates"] == []
    assert result["signals"]["justified_count"] == 1


def test_empty_input_flagged():
    result = build_rfx_bloat_burndown_report(helpers=[])
    assert "rfx_bloat_empty_input" in result["reason_codes_emitted"]


def test_missing_name_flagged():
    result = build_rfx_bloat_burndown_report(helpers=[{"name": "", "justification": "ok", "responsibility": "r"}])
    assert "rfx_bloat_missing_name" in result["reason_codes_emitted"]


def test_mixed_justified_and_unjustified():
    result = build_rfx_bloat_burndown_report(helpers=[
        _helper(name="rfx_ok"),
        {"name": "rfx_orphan", "justification": "", "responsibility": "orphan"},
    ])
    assert result["signals"]["justified_count"] == 1
    assert result["signals"]["consolidation_candidate_count"] == 1


def test_artifact_type():
    result = build_rfx_bloat_burndown_report(helpers=[_helper()])
    assert result["artifact_type"] == "rfx_bloat_burndown_report"


def test_non_dict_helper_does_not_raise():
    # P1 fix: non-dict helper rows must emit rfx_bloat_malformed_helper, not AttributeError.
    result = build_rfx_bloat_burndown_report(helpers=["not-a-dict"])
    assert "rfx_bloat_malformed_helper" in result["reason_codes_emitted"]
    assert result["artifact_type"] == "rfx_bloat_burndown_report"


def test_mixed_helpers_malformed_skipped():
    # P1 fix: malformed rows are skipped; valid rows still appear in report.
    result = build_rfx_bloat_burndown_report(helpers=[_helper(), "bad-row"])
    assert "rfx_bloat_malformed_helper" in result["reason_codes_emitted"]
    assert result["signals"]["justified_count"] == 1


def test_numeric_metadata_fields_do_not_raise():
    # P1 fix: non-string justification/responsibility/superseded_by must not raise AttributeError.
    result = build_rfx_bloat_burndown_report(
        helpers=[{"name": "rfx_foo", "justification": 42, "responsibility": True, "superseded_by": 0}]
    )
    assert result["artifact_type"] == "rfx_bloat_burndown_report"
    assert result["signals"]["justified_count"] == 1
