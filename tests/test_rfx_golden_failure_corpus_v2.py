"""Tests for rfx_golden_failure_corpus_v2 (RFX-N09)."""

from spectrum_systems.modules.runtime.rfx_golden_failure_corpus_v2 import (
    build_rfx_golden_failure_corpus_v2,
    KNOWN_CATEGORIES,
)


def _case(
    id="c1",
    category="authority_shape_doc_violation",
    trace_ref="trace-001",
    fix_ref="fix-001",
    expected="blocked",
    actual="blocked",
    **kw,
):
    return {"id": id, "category": category, "trace_ref": trace_ref,
            "fix_ref": fix_ref, "expected": expected, "actual": actual, **kw}


# RT-N09: mutate expected outcome → must fail with outcome_mismatch.
def test_rt_n09_outcome_mutation_detected():
    bad = build_rfx_golden_failure_corpus_v2(
        cases=[_case(expected="blocked", actual="passed")]
    )
    assert "rfx_v2_outcome_mismatch" in bad["reason_codes_emitted"]
    assert bad["status"] == "drifted"


def test_rt_n09_stable_after_revalidation():
    good = build_rfx_golden_failure_corpus_v2(cases=[_case()])
    assert good["status"] == "stable"
    assert good["reason_codes_emitted"] == []


def test_unregistered_case_id_flagged():
    # P2 fix: registered_case_ids is now enforced; unknown ID emits rfx_v2_case_unregistered.
    result = build_rfx_golden_failure_corpus_v2(
        cases=[_case(id="unknown-id")],
        registered_case_ids={"known-id"},
    )
    assert "rfx_v2_case_unregistered" in result["reason_codes_emitted"]


def test_registered_case_id_passes():
    result = build_rfx_golden_failure_corpus_v2(
        cases=[_case(id="c1")],
        registered_case_ids={"c1"},
    )
    assert "rfx_v2_case_unregistered" not in result["reason_codes_emitted"]


def test_no_registered_set_skips_membership_check():
    # When registered_case_ids is not supplied, no unregistered check runs.
    result = build_rfx_golden_failure_corpus_v2(cases=[_case(id="any-id")])
    assert "rfx_v2_case_unregistered" not in result["reason_codes_emitted"]


def test_empty_corpus_flagged():
    result = build_rfx_golden_failure_corpus_v2(cases=[])
    assert "rfx_v2_corpus_empty" in result["reason_codes_emitted"]


def test_missing_id_flagged():
    result = build_rfx_golden_failure_corpus_v2(cases=[_case(id="")])
    assert "rfx_v2_case_missing_id" in result["reason_codes_emitted"]


def test_missing_trace_ref_flagged():
    result = build_rfx_golden_failure_corpus_v2(cases=[_case(trace_ref=None)])
    assert "rfx_v2_case_missing_trace" in result["reason_codes_emitted"]


def test_missing_fix_ref_flagged():
    result = build_rfx_golden_failure_corpus_v2(cases=[_case(fix_ref=None)])
    assert "rfx_v2_case_missing_fix_ref" in result["reason_codes_emitted"]


def test_missing_category_flagged():
    result = build_rfx_golden_failure_corpus_v2(cases=[_case(category=None)])
    assert "rfx_v2_case_missing_category" in result["reason_codes_emitted"]


def test_duplicate_case_id_flagged():
    result = build_rfx_golden_failure_corpus_v2(cases=[_case(id="dup"), _case(id="dup")])
    assert "rfx_v2_duplicate_case_id" in result["reason_codes_emitted"]


def test_known_categories_present():
    assert "authority_shape_doc_violation" in KNOWN_CATEGORIES
    assert "missing_trace_lineage_replay" in KNOWN_CATEGORIES


def test_signals_populated():
    result = build_rfx_golden_failure_corpus_v2(cases=[_case()])
    assert result["signals"]["total_cases"] == 1
    assert result["signals"]["stable_cases"] == 1


def test_historical_category_coverage():
    cases = [_case(category=cat, id=f"c{i}") for i, cat in enumerate(KNOWN_CATEGORIES)]
    result = build_rfx_golden_failure_corpus_v2(cases=cases)
    assert result["signals"]["historical_category_coverage_pct"] == 100.0


def test_artifact_type_and_schema():
    result = build_rfx_golden_failure_corpus_v2(cases=[_case()])
    assert result["artifact_type"] == "rfx_golden_failure_corpus_v2"
    assert result["schema_version"] == "2.0.0"


def test_explicit_empty_registered_set_enforces_membership():
    # P2 fix: passing an explicit empty set must trigger rfx_v2_case_unregistered,
    # not silently pass because an empty set is falsy.
    result = build_rfx_golden_failure_corpus_v2(
        cases=[_case(id="c1")],
        registered_case_ids=set(),
    )
    assert "rfx_v2_case_unregistered" in result["reason_codes_emitted"]


def test_non_dict_case_does_not_raise():
    # P1 fix: non-dict case rows must emit rfx_v2_case_malformed_row, not AttributeError.
    result = build_rfx_golden_failure_corpus_v2(cases=["not-a-dict"])
    assert "rfx_v2_case_malformed_row" in result["reason_codes_emitted"]
    assert result["artifact_type"] == "rfx_golden_failure_corpus_v2"


def test_mixed_cases_malformed_skipped():
    # P1 fix: malformed rows are skipped; valid rows still appear in corpus.
    result = build_rfx_golden_failure_corpus_v2(cases=[_case(), "bad-row"])
    assert "rfx_v2_case_malformed_row" in result["reason_codes_emitted"]
    assert len(result["cases"]) == 1


def test_non_hashable_case_id_does_not_raise():
    # P1 fix: non-hashable case id (list/dict) must not raise TypeError on set membership check.
    result = build_rfx_golden_failure_corpus_v2(
        cases=[{"id": ["not", "hashable"], "trace_ref": "t", "fix_ref": "f",
                "category": "authority_shape_doc_violation", "expected": "ok", "actual": "ok"}]
    )
    assert result["artifact_type"] == "rfx_golden_failure_corpus_v2"
    assert result["cases"][0]["id"] == "['not', 'hashable']"
