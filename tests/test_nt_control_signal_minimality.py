from spectrum_systems.modules.runtime.slo_budget_gate import evaluate_slo_signal_diet


def _signals():
    return {
        "required_eval_pass_status": "pass",
        "replay_match_status": "match",
        "lineage_completeness_status": "healthy",
        "context_admissibility_status": "allow",
        "authority_shape_preflight_status": "pass",
        "registry_validation_status": "pass",
        "certification_evidence_index_status": "ready",
    }


def test_observation_hijack_does_not_block() -> None:
    res = evaluate_slo_signal_diet(signals=_signals(), observation_only={"report_count": 9999, "dashboard_freshness": "stale"})
    assert res["decision"] == "allow"


def test_hard_signal_degrade_blocks() -> None:
    s = _signals()
    s["replay_match_status"] = "mismatch"
    res = evaluate_slo_signal_diet(signals=s)
    assert res["decision"] == "block"
