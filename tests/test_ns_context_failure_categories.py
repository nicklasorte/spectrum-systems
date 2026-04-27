"""NS-16..18: Context failure category compression + chaos red team."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.observability.failure_trace import build_failure_trace
from spectrum_systems.modules.runtime.context_admission_gate import (
    CTX_COMPRESSED_CATEGORIES,
    CTX_REASON_TO_CATEGORY,
    admit_context_bundle,
    compress_ctx_reason_to_category,
)


def _bundle(**overrides) -> dict:
    base = {
        "preflight_passed": True,
        "admitted_candidates": [
            {
                "candidate_id": "c1",
                "role": "evidence",
                "trust_level": "trusted",
                "artifact_type": "context_evidence",
                "schema_version": "1.0.0",
                "provenance": {"source": "system_repo"},
                "expires_at": "2099-01-01T00:00:00Z",
                "topic": "spec",
                "assertion": "ok",
            }
        ],
    }
    base.update(overrides)
    return base


def test_categories_finite() -> None:
    assert set(CTX_COMPRESSED_CATEGORIES) == {
        "missing",
        "stale",
        "conflicting",
        "untrusted",
        "incompatible",
        "injection_risk",
    }


def test_each_canonical_ctx_reason_has_category_or_none() -> None:
    for reason, cat in CTX_REASON_TO_CATEGORY.items():
        if reason == "CTX_OK":
            assert cat is None
        else:
            assert cat in CTX_COMPRESSED_CATEGORIES


def test_compress_unknown_returns_unknown() -> None:
    assert compress_ctx_reason_to_category("BOGUS") == "unknown"


# ---- NS-17: chaos red team ----


def test_chaos_missing_provenance_blocks_with_missing_category() -> None:
    bundle = _bundle()
    bundle["admitted_candidates"][0].pop("provenance")
    res = admit_context_bundle(bundle=bundle)
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_MISSING_PROVENANCE"
    assert res["compressed_category"] == "missing"


def test_chaos_stale_ttl_blocks_with_stale_category() -> None:
    bundle = _bundle()
    bundle["admitted_candidates"][0]["expires_at"] = "2020-01-01T00:00:00Z"
    res = admit_context_bundle(bundle=bundle)
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_STALE_TTL"
    assert res["compressed_category"] == "stale"


def test_chaos_conflicting_assertions_blocks_with_conflicting_category() -> None:
    bundle = _bundle()
    bundle["admitted_candidates"].append(
        {
            "candidate_id": "c2",
            "role": "evidence",
            "trust_level": "trusted",
            "artifact_type": "context_evidence",
            "schema_version": "1.0.0",
            "provenance": {"source": "system_repo"},
            "topic": "spec",
            "assertion": "not_ok",  # conflicts with c1
        }
    )
    res = admit_context_bundle(bundle=bundle)
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_CONTRADICTORY_CONTEXT"
    assert res["compressed_category"] == "conflicting"


def test_chaos_injection_risk_untrusted_instruction_blocks() -> None:
    bundle = _bundle()
    bundle["admitted_candidates"][0]["trust_level"] = "untrusted"
    bundle["admitted_candidates"][0]["role"] = "instruction"
    res = admit_context_bundle(bundle=bundle)
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_UNTRUSTED_INSTRUCTION"
    assert res["compressed_category"] == "injection_risk"


def test_chaos_schema_incompatible_blocks() -> None:
    bundle = _bundle()
    res = admit_context_bundle(
        bundle=bundle,
        expected_schema_versions={"context_evidence": "2.0.0"},
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_SCHEMA_INCOMPATIBLE"
    assert res["compressed_category"] == "incompatible"


def test_chaos_malformed_bundle_blocks() -> None:
    res = admit_context_bundle(bundle={"admitted_candidates": "not-a-list"})
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_MALFORMED_BUNDLE"
    assert res["compressed_category"] == "incompatible"


def test_chaos_missing_preflight_blocks() -> None:
    bundle = _bundle()
    bundle["preflight_passed"] = False
    res = admit_context_bundle(bundle=bundle)
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_MISSING_PREFLIGHT"
    assert res["compressed_category"] == "missing"


# ---- NS-18: failure trace handoff ----


def test_ctx_failure_produces_compact_failure_trace() -> None:
    """When CTX blocks, a downstream failure trace must surface a compact,
    human-readable summary that names the canonical category and
    next action."""
    bundle = _bundle()
    bundle["admitted_candidates"][0]["expires_at"] = "2020-01-01T00:00:00Z"
    res = admit_context_bundle(bundle=bundle)
    assert res["decision"] == "block"
    # Hand off to failure trace as if eval rejected admission.
    eval_result = {
        "artifact_id": "evl-x",
        "artifact_type": "eval_slice_summary",
        "status": "blocked",
        "block_reason": res["reason_code"],
    }
    trace = build_failure_trace(
        trace_id="ctx-1",
        execution_record={"artifact_id": "exec-1", "status": "ok"},
        output_artifact={"artifact_id": "out-1", "artifact_type": "eval_summary"},
        eval_result=eval_result,
        control_decision={"decision_id": "cde-1", "decision": "block",
                          "reason_code": res["reason_code"]},
        enforcement_action={"enforcement_id": "sel-1", "enforcement_action": "deny_execution"},
    )
    assert trace["overall_status"] == "failed"
    assert trace["canonical_reason_category"] == "CONTEXT_ADMISSION_FAILURE"
    assert "trace_id=ctx-1" in trace["one_page_summary"]
    assert "next_recommended_action" in trace["one_page_summary"]
