"""NS-04..06: Failure reason canonicalization + cross-subsystem stability."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.observability.reason_code_canonicalizer import (
    CANONICAL_CATEGORIES,
    ReasonCodeError,
    assert_canonical_or_alias,
    canonicalize_reason_code,
)


def test_canonical_category_round_trip() -> None:
    for cat in CANONICAL_CATEGORIES:
        res = canonicalize_reason_code(cat)
        assert res["canonical_category"] == cat


def test_alias_maps_to_canonical_and_preserves_detail() -> None:
    res = canonicalize_reason_code(
        "missing_required_eval_result", detail_fields={"eval_id": "schema_ok"}
    )
    assert res["canonical_category"] == "EVAL_FAILURE"
    assert res["detail_code"] == "missing_required_eval_result"
    assert res["details"]["eval_id"] == "schema_ok"


def test_unknown_code_does_not_silently_pass() -> None:
    res = canonicalize_reason_code("not_a_real_reason_code_at_all")
    assert res["canonical_category"] == "UNKNOWN"


def test_empty_code_treated_as_unknown_not_silent_allow() -> None:
    res = canonicalize_reason_code("")
    assert res["canonical_category"] == "UNKNOWN"


# ---- NS-05: same underlying failure, multiple subsystem injections ----


def test_same_missing_artifact_failure_is_stable_across_subsystems() -> None:
    """A missing-artifact failure surfaced through eval, replay, lineage, ctx,
    cert, and obs must canonicalize to a stable category set while preserving
    the per-subsystem detail code."""

    eval_side = canonicalize_reason_code("missing_required_eval_result")
    replay_side = canonicalize_reason_code("REPLAY_MISSING_ORIGINAL_RECORD")
    lineage_side = canonicalize_reason_code("LINEAGE_MISSING_PRODUCED_ARTIFACT")
    ctx_side = canonicalize_reason_code("CTX_MISSING_PROVENANCE")
    cert_side = canonicalize_reason_code("CERT_MISSING_EVAL_PASS")
    obs_side = canonicalize_reason_code("OBS_MISSING_OUTPUT_ARTIFACT")
    control_side = canonicalize_reason_code("CONTROL_CHAIN_MISSING_EVAL_REFERENCE")

    # Stable canonical category sets per subsystem
    assert eval_side["canonical_category"] == "EVAL_FAILURE"
    assert replay_side["canonical_category"] == "MISSING_ARTIFACT"
    assert lineage_side["canonical_category"] == "LINEAGE_GAP"
    assert ctx_side["canonical_category"] == "CONTEXT_ADMISSION_FAILURE"
    assert cert_side["canonical_category"] == "CERTIFICATION_GAP"
    assert obs_side["canonical_category"] == "MISSING_ARTIFACT"
    assert control_side["canonical_category"] == "CONTROL_CHAIN_VIOLATION"

    # Per-side detail still distinguishable
    details = {
        eval_side["detail_code"],
        replay_side["detail_code"],
        lineage_side["detail_code"],
        ctx_side["detail_code"],
        cert_side["detail_code"],
        obs_side["detail_code"],
        control_side["detail_code"],
    }
    assert len(details) == 7


def test_replay_mismatch_codes_canonicalize_to_replay_mismatch() -> None:
    for raw in [
        "REPLAY_HASH_MISMATCH_INPUT",
        "REPLAY_HASH_MISMATCH_OUTPUT",
        "REPLAY_HASH_MISMATCH_BOTH",
    ]:
        assert canonicalize_reason_code(raw)["canonical_category"] == "REPLAY_MISMATCH"


def test_slo_codes_canonicalize_to_slo_budget_failure() -> None:
    for raw in [
        "SLO_BUDGET_EXHAUSTED",
        "SLO_DRIFT_RISING",
        "SLO_OVERRIDE_RATE_EXCEEDED",
    ]:
        assert canonicalize_reason_code(raw)["canonical_category"] == "SLO_BUDGET_FAILURE"


def test_authority_shape_violation_canonicalizes() -> None:
    res = canonicalize_reason_code("CERT_MISSING_AUTHORITY_SHAPE_PREFLIGHT")
    assert res["canonical_category"] == "AUTHORITY_SHAPE_VIOLATION"


def test_subsystem_prefix_inferred_when_no_alias() -> None:
    res = canonicalize_reason_code("REPLAY_HASH_NEW_VARIANT")
    # Unknown specific code, but prefix infers REPLAY_MISMATCH
    assert res["canonical_category"] == "REPLAY_MISMATCH"
    assert res["source_subsystem"] == "REP"


# ---- NS-06: guardrails on new blocking reason codes ----


def test_assert_canonical_or_alias_passes_for_canonical() -> None:
    for cat in CANONICAL_CATEGORIES:
        assert_canonical_or_alias(cat)


def test_assert_canonical_or_alias_passes_for_alias() -> None:
    assert_canonical_or_alias("missing_required_eval_result")
    assert_canonical_or_alias("REPLAY_HASH_MISMATCH_INPUT")
    assert_canonical_or_alias("CTX_STALE_TTL")


def test_high_level_blocking_codes_rejected_without_mapping() -> None:
    for raw in ["blocked", "freeze", "fail", "rejected", "error"]:
        with pytest.raises(ReasonCodeError):
            assert_canonical_or_alias(raw)


def test_unknown_arbitrary_code_rejected() -> None:
    with pytest.raises(ReasonCodeError):
        assert_canonical_or_alias("totally_made_up_block_reason")


def test_empty_blocking_reason_rejected() -> None:
    with pytest.raises(ReasonCodeError):
        assert_canonical_or_alias("")
    with pytest.raises(ReasonCodeError):
        assert_canonical_or_alias("   ")
