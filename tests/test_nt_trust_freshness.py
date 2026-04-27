from spectrum_systems.modules.governance.trust_compression import audit_trust_artifact_freshness


def test_freshness_audit_detects_stale_and_unknown() -> None:
    result = audit_trust_artifact_freshness(
        artifacts={
            "certification_evidence_index": {
                "source_digest": "a",
                "producer_input_digest": "b",
                "generated_at": "2026-04-26T00:00:00Z",
            },
            "reason_code_aliases": {"generated_at": "2026-04-27T00:00:00Z"},
        },
        now_iso="2026-04-27T01:00:00Z",
    )
    assert result["results"]["certification_evidence_index"]["status"] == "stale"
    assert result["results"]["reason_code_aliases"]["status"] == "unknown"
