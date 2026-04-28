"""OC-04..06: Bottleneck classifier unit + red-team tests."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.observability.bottleneck_classifier import (
    CANONICAL_REASON_CODES,
    CATEGORY_PRECEDENCE,
    CATEGORY_TO_OWNER,
    BottleneckClassifierError,
    classify_bottleneck,
)


def test_classification_id_required():
    with pytest.raises(BottleneckClassifierError):
        classify_bottleneck(classification_id="", findings=[])


def test_owners_finite_and_match_registry_letters():
    # All owners must be exactly 3 letters and from the canonical set.
    canonical = {
        "AEX", "PQX", "EVL", "TPA", "CDE", "SEL", "REP", "LIN", "OBS",
        "SLO", "CTX", "PRM", "POL", "TLC", "RIL", "FRE", "RAX", "RSM",
        "CAP", "SEC", "JDX", "JSX", "PRA", "GOV", "MAP", "HOP",
    }
    for cat, owner in CATEGORY_TO_OWNER.items():
        assert owner in canonical, f"{cat}->{owner} missing in canonical set"


def test_canonical_reason_codes_finite():
    assert "BOTTLENECK_EVAL_FAILED" in CANONICAL_REASON_CODES
    assert "BOTTLENECK_AMBIGUOUS" in CANONICAL_REASON_CODES
    assert "BOTTLENECK_UNKNOWN" in CANONICAL_REASON_CODES


def test_eval_finding_classified_as_eval_block():
    out = classify_bottleneck(
        classification_id="bc-1",
        findings=[
            {
                "category": "eval",
                "reason_code": "BOTTLENECK_EVAL_FAILED",
                "evidence_ref": "evl-1",
            }
        ],
    )
    assert out["category"] == "eval"
    assert out["owning_system"] == "EVL"
    assert out["reason_code"] == "BOTTLENECK_EVAL_FAILED"
    assert out["next_safe_action"]["action"] == "block"
    assert out["evidence_artifact_ref"] == "evl-1"
    assert out["confidence"] == "medium"
    assert out["ambiguous"] is False


def test_keyword_only_finding_recognised():
    out = classify_bottleneck(
        classification_id="bc-kw",
        findings=[
            {
                "summary": "lineage gap detected upstream",
                "evidence_ref": "lin-1",
            }
        ],
    )
    assert out["category"] == "lineage"
    assert out["owning_system"] == "LIN"


def test_unknown_finding_yields_unknown_with_investigate():
    out = classify_bottleneck(
        classification_id="bc-unknown",
        findings=[
            {"summary": "weird thing happened", "evidence_ref": "x-1"}
        ],
    )
    assert out["category"] == "unknown"
    assert out["next_safe_action"]["action"] == "investigate"


def test_empty_findings_yield_unknown_investigate():
    out = classify_bottleneck(classification_id="bc-empty", findings=[])
    assert out["category"] == "unknown"
    assert out["next_safe_action"]["action"] == "investigate"
    assert out["confidence"] == "low"


# ---- OC-05 red team: ambiguity must block ----


def test_ambiguous_findings_force_block_and_ambiguous_flag():
    out = classify_bottleneck(
        classification_id="bc-ambig",
        findings=[
            {"category": "eval", "reason_code": "BOTTLENECK_EVAL_FAILED",
             "evidence_ref": "evl-1"},
            {"category": "lineage", "reason_code": "BOTTLENECK_LINEAGE_GAP",
             "evidence_ref": "lin-1"},
        ],
    )
    assert out["ambiguous"] is True
    # registry/authority/eval all hit precedence: eval comes after registry
    # and authority_shape, before lineage. So eval wins precedence:
    assert out["category"] == "eval"
    assert out["next_safe_action"]["action"] == "block"
    assert out["reason_code"] == "BOTTLENECK_AMBIGUOUS"
    cats = [c["category"] for c in out["ambiguity_candidates"]]
    assert "lineage" in cats


def test_registry_takes_precedence_over_eval():
    out = classify_bottleneck(
        classification_id="bc-prec",
        findings=[
            {"category": "eval", "reason_code": "BOTTLENECK_EVAL_FAILED"},
            {"category": "registry", "reason_code": "BOTTLENECK_REGISTRY_DRIFT"},
        ],
    )
    # registry comes first in precedence
    assert out["category"] == "registry"
    assert out["ambiguous"] is True
    # ambiguous always forces block
    assert out["next_safe_action"]["action"] == "block"


def test_precedence_order_stable():
    # `registry` precedes `eval`; `eval` precedes `lineage`; etc.
    assert CATEGORY_PRECEDENCE.index("registry") < CATEGORY_PRECEDENCE.index("eval")
    assert CATEGORY_PRECEDENCE.index("eval") < CATEGORY_PRECEDENCE.index("lineage")
    assert CATEGORY_PRECEDENCE.index("authority_shape") < CATEGORY_PRECEDENCE.index("dashboard")


def test_slo_finding_freezes_not_blocks():
    out = classify_bottleneck(
        classification_id="bc-slo",
        findings=[
            {"category": "slo", "reason_code": "BOTTLENECK_SLO_BURN",
             "evidence_ref": "slo-1"}
        ],
    )
    assert out["category"] == "slo"
    assert out["next_safe_action"]["action"] == "freeze"
