"""NT-04..06: Proof bundle size budget + bloat red team + compression fix.

Validates:
  - compact proof passes
  - bloated bundle (oversized refs / inline evidence / deep nesting / bloated
    summary / repeated refs) blocks deterministically
  - blocked result has a clear canonical reason code
  - oversized one-page trace compresses deterministically
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.loop_proof_bundle import (
    build_loop_proof_bundle,
)
from spectrum_systems.modules.governance.proof_bundle_size_budget import (
    CANONICAL_PROOF_SIZE_REASON_CODES,
    ProofBundleSizeError,
    compress_one_page_trace,
    evaluate_proof_bundle_size,
    load_proof_bundle_size_policy,
)


def _passing_loop_inputs() -> dict:
    return dict(
        bundle_id="lpb-size-pass",
        trace_id="tSZ",
        run_id="rSZ",
        execution_record={
            "artifact_id": "exec-1",
            "artifact_type": "pqx_slice_execution_record",
            "status": "ok",
        },
        output_artifact={"artifact_id": "out-1", "artifact_type": "eval_summary"},
        eval_summary={"artifact_id": "evl-1", "status": "healthy"},
        control_decision={"decision_id": "cde-1", "decision": "allow"},
        enforcement_action={
            "enforcement_id": "sel-1",
            "enforcement_action": "allow_execution",
        },
        replay_record={"replay_id": "rpl-1", "artifact_id": "rpl-1", "status": "healthy"},
        lineage_summary={"summary_id": "lin-1", "artifact_id": "lin-1", "status": "healthy"},
    )


# ---- NT-04 contract ----


def test_canonical_reason_codes_finite() -> None:
    assert "PROOF_SIZE_OK" in CANONICAL_PROOF_SIZE_REASON_CODES
    for code in (
        "PROOF_SIZE_OVER_REF_BUDGET",
        "PROOF_SIZE_NESTED_TOO_DEEP",
        "PROOF_SIZE_OVER_LINE_BUDGET",
        "PROOF_SIZE_OVER_CHAR_BUDGET",
        "PROOF_SIZE_DUPLICATE_REFS",
        "PROOF_SIZE_INLINE_EVIDENCE",
    ):
        assert code in CANONICAL_PROOF_SIZE_REASON_CODES


def test_policy_loadable_and_kinds_present() -> None:
    pol = load_proof_bundle_size_policy()
    assert pol["artifact_type"] == "proof_bundle_size_policy"
    for kind in ("loop_proof_bundle", "certification_evidence_index", "one_page_trace"):
        assert kind in pol


def test_compact_loop_proof_passes_size_budget() -> None:
    bundle = build_loop_proof_bundle(**_passing_loop_inputs())
    res = evaluate_proof_bundle_size(bundle=bundle)
    assert res["decision"] == "allow"
    assert res["reason_code"] == "PROOF_SIZE_OK"


# ---- NT-05 red team — bloat ----


def test_red_team_oversized_refs_blocks() -> None:
    """Synthesise a bundle with too many top-level *_ref keys."""
    bundle = build_loop_proof_bundle(**_passing_loop_inputs())
    # Inflate: add 30 extra ref-shaped keys.
    for i in range(30):
        bundle[f"extra_evidence_{i}_ref"] = f"art-{i}"
    res = evaluate_proof_bundle_size(bundle=bundle, kind="loop_proof_bundle")
    assert res["decision"] == "block"
    assert res["reason_code"] == "PROOF_SIZE_OVER_REF_BUDGET"


def test_red_team_inline_evidence_blocks() -> None:
    """Producer puts a full eval_summary inline instead of a ref."""
    bundle = build_loop_proof_bundle(**_passing_loop_inputs())
    bundle["eval_summary"] = {
        "artifact_id": "evl-1",
        "status": "healthy",
        "fields": {"a": 1, "b": [1, 2, 3]},
    }
    res = evaluate_proof_bundle_size(bundle=bundle, kind="loop_proof_bundle")
    assert res["decision"] == "block"
    assert res["reason_code"] == "PROOF_SIZE_INLINE_EVIDENCE"


def test_red_team_duplicate_refs_blocks() -> None:
    bundle = build_loop_proof_bundle(**_passing_loop_inputs())
    # Two refs pointing to the same artifact_id.
    bundle["lineage_chain_ref"] = bundle["replay_record_ref"]
    res = evaluate_proof_bundle_size(bundle=bundle, kind="loop_proof_bundle")
    assert res["decision"] == "block"
    assert res["reason_code"] == "PROOF_SIZE_DUPLICATE_REFS"


def test_red_team_deep_nesting_blocks() -> None:
    """Synthesise a bundle with deeply nested non-ref payload."""
    bundle = build_loop_proof_bundle(**_passing_loop_inputs())
    nested = {}
    cur = nested
    for _ in range(10):
        cur["deeper"] = {}
        cur = cur["deeper"]
    bundle["debug_payload"] = nested
    res = evaluate_proof_bundle_size(bundle=bundle, kind="loop_proof_bundle")
    assert res["decision"] == "block"
    assert res["reason_code"] == "PROOF_SIZE_NESTED_TOO_DEEP"


def test_red_team_bloated_one_page_summary_blocks() -> None:
    bundle = build_loop_proof_bundle(**_passing_loop_inputs())
    bundle["trace_summary"] = dict(bundle["trace_summary"])
    bundle["trace_summary"]["one_page_summary"] = "\n".join(
        f"line {i}" for i in range(200)
    )
    res = evaluate_proof_bundle_size(bundle=bundle, kind="loop_proof_bundle")
    assert res["decision"] == "block"
    assert res["reason_code"] == "PROOF_SIZE_OVER_LINE_BUDGET"


def test_red_team_bloated_human_readable_blocks() -> None:
    bundle = build_loop_proof_bundle(**_passing_loop_inputs())
    bundle["human_readable"] = "x" * 50_000
    res = evaluate_proof_bundle_size(bundle=bundle, kind="loop_proof_bundle")
    assert res["decision"] == "block"
    assert res["reason_code"] == "PROOF_SIZE_OVER_CHAR_BUDGET"


def test_red_team_certification_evidence_index_oversized_codes_blocks() -> None:
    """If a certification index lists too many blocking detail codes, block."""
    cei = {
        "artifact_type": "certification_evidence_index",
        "index_id": "cei-bloat",
        "trace_id": "tA",
        "status": "blocked",
        "references": {f"ref_{i}": f"art-{i}" for i in range(3)},
        "blocking_detail_codes": [f"CERT_X_{i}" for i in range(50)],
        "human_readable": "ok",
    }
    res = evaluate_proof_bundle_size(bundle=cei)
    assert res["decision"] == "block"


# ---- NT-06 deterministic compression ----


def test_compress_under_budget_returns_unchanged() -> None:
    one_page = "line1\nline2\nline3"
    res = compress_one_page_trace(one_page, max_lines=10, max_chars=1000)
    assert res["compressed"] is False
    assert res["output"] == one_page
    assert res["elided_lines"] == 0


def test_compress_oversized_trace_is_deterministic() -> None:
    one_page = "\n".join(f"line {i}" for i in range(200))
    a = compress_one_page_trace(one_page, max_lines=20, max_chars=4000)
    b = compress_one_page_trace(one_page, max_lines=20, max_chars=4000)
    assert a == b
    assert a["compressed"] is True
    assert "PROOF_SIZE_COMPRESSION" in a["output"]
    assert a["elided_lines"] > 0


def test_compress_keeps_head_and_tail_for_operator_diagnosis() -> None:
    one_page = "\n".join(f"line {i}" for i in range(100))
    res = compress_one_page_trace(one_page, max_lines=15, max_chars=4000)
    assert "line 0" in res["output"]
    assert "line 99" in res["output"]


def test_compress_respects_char_budget() -> None:
    one_page = "\n".join("x" * 200 for _ in range(50))
    res = compress_one_page_trace(one_page, max_lines=40, max_chars=300)
    assert len(res["output"]) <= 320  # close to budget with sentinel


def test_unknown_kind_raises() -> None:
    with pytest.raises(ProofBundleSizeError):
        evaluate_proof_bundle_size(
            bundle={"artifact_type": "not_a_known_proof_kind"}
        )


def test_blocked_result_carries_metrics() -> None:
    bundle = build_loop_proof_bundle(**_passing_loop_inputs())
    bundle["human_readable"] = "x" * 50_000
    res = evaluate_proof_bundle_size(bundle=bundle, kind="loop_proof_bundle")
    assert res["metrics"]["human_readable_chars"] == 50_000
    assert isinstance(res["metrics"]["max_depth"], int)
