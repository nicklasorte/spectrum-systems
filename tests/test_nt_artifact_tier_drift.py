from spectrum_systems.modules.observability.artifact_tier_audit import validate_promotion_evidence_tiers


def test_tier_escape_via_wrapper_blocks_transitively() -> None:
    res = validate_promotion_evidence_tiers(
        [{"artifact_id": "wrapper", "artifact_type": "eval_slice_summary", "evidence_refs": ["bad"]}],
        validation_id="v1",
        evidence_graph={"bad": {"artifact_id": "bad", "artifact_path": "outputs/reports/x.md"}},
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "TIER_REPORT_AS_AUTHORITY"
