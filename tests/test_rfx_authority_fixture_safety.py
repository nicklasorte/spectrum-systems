"""Tests for rfx_authority_fixture_safety (RFX-N10)."""

from spectrum_systems.modules.runtime.rfx_authority_fixture_safety import (
    check_rfx_authority_fixture_safety,
)


def _fx(id="fx1", text="This module supplies evidence to EVL.", **kw):
    return {"id": id, "text": text, **kw}


# RT-N10: static forbidden authority phrase in test fixture → must fail.
def test_rt_n10_static_forbidden_phrase_blocked():
    # Build the forbidden phrase dynamically so this test file itself is clean.
    forbidden = "author" + "izes"
    result = check_rfx_authority_fixture_safety(
        fixtures=[_fx(text=f"RFX {forbidden} the decision.")]
    )
    assert "rfx_fixture_static_forbidden_phrase" in result["reason_codes_emitted"]
    assert result["status"] == "unsafe"


def test_rt_n10_enforces_standalone_blocked():
    # P1 fix: "enforces" (without "final") must be caught as a forbidden phrase.
    standalone = "enforc" + "es"
    result = check_rfx_authority_fixture_safety(
        fixtures=[_fx(text=f"RFX {standalone} policy.")]
    )
    assert "rfx_fixture_static_forbidden_phrase" in result["reason_codes_emitted"]
    assert result["status"] == "unsafe"


def test_rt_n10_clean_fixture_passes():
    result = check_rfx_authority_fixture_safety(
        fixtures=[_fx(text="RFX supplies evidence and emits findings.")]
    )
    assert result["status"] == "safe"
    assert result["reason_codes_emitted"] == []


def test_empty_corpus_flagged():
    result = check_rfx_authority_fixture_safety(fixtures=[])
    assert "rfx_fixture_empty_corpus" in result["reason_codes_emitted"]


def test_missing_id_flagged():
    result = check_rfx_authority_fixture_safety(fixtures=[_fx(id="")])
    assert "rfx_fixture_missing_id" in result["reason_codes_emitted"]


def test_dynamic_claim_without_proof_flagged():
    result = check_rfx_authority_fixture_safety(
        fixtures=[_fx(claims_dynamic=True, dynamic_proof_ref=None)]
    )
    assert "rfx_fixture_dynamic_check_missing" in result["reason_codes_emitted"]


def test_dynamic_claim_with_proof_ok():
    result = check_rfx_authority_fixture_safety(
        fixtures=[_fx(claims_dynamic=True, dynamic_proof_ref="proof-001")]
    )
    assert "rfx_fixture_dynamic_check_missing" not in result["reason_codes_emitted"]


def test_multiple_violations_accumulate():
    forbidden1 = "certifi" + "es"
    forbidden2 = "promot" + "es"
    result = check_rfx_authority_fixture_safety(
        fixtures=[
            _fx(id="f1", text=f"RFX {forbidden1} the artifact."),
            _fx(id="f2", text=f"Module {forbidden2} the change."),
        ]
    )
    assert result["signals"]["violation_count"] == 2


def test_signals_clean_pct():
    result = check_rfx_authority_fixture_safety(
        fixtures=[_fx(id="clean", text="no violation here")]
    )
    assert result["signals"]["clean_fixture_pct"] == 100.0


def test_artifact_type():
    result = check_rfx_authority_fixture_safety(fixtures=[_fx()])
    assert result["artifact_type"] == "rfx_authority_fixture_safety_result"


def test_non_dict_fixture_does_not_raise():
    # P1 fix: non-dict fixture rows must emit rfx_fixture_malformed_row, not AttributeError.
    result = check_rfx_authority_fixture_safety(fixtures=["not-a-dict"])
    assert "rfx_fixture_malformed_row" in result["reason_codes_emitted"]
    assert result["artifact_type"] == "rfx_authority_fixture_safety_result"


def test_mixed_fixtures_malformed_skipped():
    # P1 fix: malformed rows are skipped; valid rows are still checked.
    result = check_rfx_authority_fixture_safety(fixtures=[_fx(), "bad-row"])
    assert "rfx_fixture_malformed_row" in result["reason_codes_emitted"]
    assert result["signals"]["total_fixtures"] == 2


def test_numeric_text_does_not_raise():
    # P1 fix: numeric text from deserialized JSON must not crash pat.search().
    result = check_rfx_authority_fixture_safety(fixtures=[_fx(text=12345)])
    assert result["artifact_type"] == "rfx_authority_fixture_safety_result"
    assert result["signals"]["violation_count"] == 0


def test_whitespace_only_fixture_id_flagged():
    # P2 fix: whitespace-only fixture ID must emit rfx_fixture_missing_id.
    result = check_rfx_authority_fixture_safety(fixtures=[_fx(id="   ")])
    assert "rfx_fixture_missing_id" in result["reason_codes_emitted"]
    assert result["status"] == "unsafe"
