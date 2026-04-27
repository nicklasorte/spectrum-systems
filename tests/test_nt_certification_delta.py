from spectrum_systems.modules.governance.trust_compression import build_certification_delta


def test_delta_detects_swapped_refs() -> None:
    prev = {"status": "ready", "references": {"eval_summary_ref": "a", "replay_summary_ref": "r1"}}
    cur = {"status": "ready", "references": {"eval_summary_ref": "b", "replay_summary_ref": "r2"}}
    delta = build_certification_delta(current_index=cur, previous_index=prev)
    assert set(delta["changed_evidence_refs"]) == {"eval_summary_ref", "replay_summary_ref"}
    assert delta["overall_delta_risk"] in {"medium", "high"}
