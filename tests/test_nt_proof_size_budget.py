from spectrum_systems.modules.governance.trust_compression import enforce_proof_size_budget


def test_compact_proof_passes_size_budget() -> None:
    res = enforce_proof_size_budget(
        proof_bundle={"a_ref": "1", "b_ref": "2"},
        evidence_index={"references": {"a": "1"}},
        one_page_trace="ok\nline",
    )
    assert res["decision"] == "allow"


def test_bloated_proof_blocks_size_budget() -> None:
    proof = {f"ref_{i}_ref": str(i) for i in range(40)}
    res = enforce_proof_size_budget(proof_bundle=proof, evidence_index={"references": {}}, one_page_trace="x")
    assert res["decision"] == "block"
    assert "PROOF_BUNDLE_OVERSIZED_REFS" in res["reason_codes"]
