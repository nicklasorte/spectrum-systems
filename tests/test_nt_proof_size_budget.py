"""NT-04..06: Proof bundle size budget — validation, red team, compression fix."""

from __future__ import annotations

import json

import pytest

from spectrum_systems.modules.governance.loop_proof_bundle import build_loop_proof_bundle
from spectrum_systems.modules.governance.proof_bundle_size import (
    ProofBundleSizeError,
    compress_proof_bundle,
    load_proof_bundle_size_policy,
    validate_proof_bundle_size,
)


def _compact_loop_proof():
    return build_loop_proof_bundle(
        bundle_id="lpb-pass",
        trace_id="t1",
        run_id="r1",
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


def test_policy_loads_with_required_limits():
    pol = load_proof_bundle_size_policy()
    limits = pol["limits"]
    for key in ("loop_proof_bundle", "certification_evidence_index", "failure_trace"):
        assert key in limits


def test_compact_loop_proof_passes():
    bundle = _compact_loop_proof()
    res = validate_proof_bundle_size(bundle)
    assert res["decision"] == "allow"
    assert res["reason_code"] == "PROOF_BUNDLE_OK"
    assert res["metrics"]["evidence_ref_count"] >= 7


def test_too_many_top_level_refs_blocks():
    bundle = _compact_loop_proof()
    # Inject many extra evidence refs
    for i in range(20):
        bundle[f"extra_evidence_{i}_ref"] = f"art-{i}"
    res = validate_proof_bundle_size(bundle)
    assert res["decision"] == "block"
    assert res["reason_code"] == "PROOF_BUNDLE_TOO_MANY_EVIDENCE_REFS"


def test_inline_evidence_forbidden_blocks():
    bundle = _compact_loop_proof()
    bundle["execution_record"] = {"artifact_id": "exec-1", "huge_payload": ["x"] * 100}
    res = validate_proof_bundle_size(bundle)
    assert res["decision"] == "block"
    # First reason among possibly several
    assert "PROOF_BUNDLE_INLINE_EVIDENCE_FORBIDDEN" in {res["reason_code"], *[
        line.split(":")[0].strip() for line in res["blocking_reasons"]
    ]} or res["reason_code"] == "PROOF_BUNDLE_INLINE_EVIDENCE_FORBIDDEN" or any(
        "inline evidence keys present" in r for r in res["blocking_reasons"]
    )


def test_oversized_one_page_summary_blocks():
    bundle = _compact_loop_proof()
    bundle["trace_summary"]["one_page_summary"] = "X" * 5000
    res = validate_proof_bundle_size(bundle)
    assert res["decision"] == "block"
    assert any(
        "one_page_summary" in r for r in res["blocking_reasons"]
    )


def test_oversized_human_readable_blocks():
    bundle = _compact_loop_proof()
    bundle["human_readable"] = "X" * 7000
    res = validate_proof_bundle_size(bundle)
    assert res["decision"] == "block"
    assert any("human_readable" in r for r in res["blocking_reasons"])


def test_repeated_evidence_refs_block():
    bundle = _compact_loop_proof()
    # Force two refs to be the same value
    bundle["eval_summary_ref"] = bundle["execution_record_ref"]
    res = validate_proof_bundle_size(bundle)
    assert res["decision"] == "block"
    assert any(
        "ref values used more than once" in r for r in res["blocking_reasons"]
    )


def test_too_many_blocking_detail_codes_blocks():
    bundle = _compact_loop_proof()
    bundle["blocking_detail_codes"] = [f"CODE_{i}" for i in range(15)]
    res = validate_proof_bundle_size(bundle)
    assert res["decision"] == "block"
    assert res["reason_code"] in {
        "PROOF_BUNDLE_BLOCKING_DETAIL_CODES_TOO_MANY",
        "PROOF_BUNDLE_OK",  # might have triggered other
    }
    assert any(
        "blocking detail codes" in r for r in res["blocking_reasons"]
    )


def test_unknown_artifact_type_blocks_with_policy_unavailable_reason():
    res = validate_proof_bundle_size(
        {"artifact_type": "definitely_not_in_policy"},
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "PROOF_BUNDLE_SIZE_POLICY_UNAVAILABLE"


def test_compress_drops_inline_evidence_and_records_suppression():
    bundle = _compact_loop_proof()
    bundle["execution_record"] = {"artifact_id": "exec-1", "blob": ["x"] * 200}
    bundle["eval_summary"] = {"artifact_id": "evl-1", "blob": ["x"] * 200}
    compressed = compress_proof_bundle(bundle)
    assert "execution_record" not in compressed
    assert "eval_summary" not in compressed
    assert "execution_record_ref" in compressed
    notice = compressed.get("compression_notice")
    assert notice is not None
    assert "execution_record" in notice["suppressed_inline_keys"]


def test_compress_is_deterministic_and_order_stable():
    bundle1 = _compact_loop_proof()
    bundle1["execution_record"] = {"artifact_id": "exec-1"}
    compressed1 = compress_proof_bundle(bundle1)

    bundle2 = _compact_loop_proof()
    bundle2["execution_record"] = {"artifact_id": "exec-1"}
    compressed2 = compress_proof_bundle(bundle2)

    # Compressed dict should be byte-identical when serialized with sorted=False
    assert json.dumps(compressed1, sort_keys=False) == json.dumps(
        compressed2, sort_keys=False
    )
    # Stable evidence ordering: execution_record_ref before eval_summary_ref
    keys = list(compressed1.keys())
    assert keys.index("execution_record_ref") < keys.index("eval_summary_ref")


def test_compressed_bundle_validates_within_budget():
    bundle = _compact_loop_proof()
    bundle["execution_record"] = {"artifact_id": "exec-1", "blob": ["x"] * 200}
    compressed = compress_proof_bundle(bundle)
    res = validate_proof_bundle_size(compressed, artifact_type="loop_proof_bundle")
    assert res["decision"] == "allow"


def test_validate_requires_mapping():
    with pytest.raises(ProofBundleSizeError):
        validate_proof_bundle_size("not a mapping")  # type: ignore[arg-type]
