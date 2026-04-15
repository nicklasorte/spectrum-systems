from __future__ import annotations

from spectrum_systems.modules.wpg.governance_offload import build_governance_policy_pack


def test_governance_offload_pack_contains_required_policies() -> None:
    pack = build_governance_policy_pack(trace_id="t1")
    expected = {
        "eval_requirement_profile",
        "review_trigger_policy",
        "redteam_trigger_policy",
        "promotion_requirements",
        "override_policy",
        "reuse_policy",
        "context_admission_policy",
        "policy_canary",
    }
    assert expected.issubset(pack.keys())
