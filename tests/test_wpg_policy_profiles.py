from __future__ import annotations

from spectrum_systems.modules.wpg.policy_ops import build_study_policy_profile


def test_study_policy_profile_controls_on_missing_rules() -> None:
    blocked = build_study_policy_profile(study_id="s1", required_rules=[], trace_id="t1")
    assert blocked["evaluation_refs"]["control_decision"]["decision"] == "BLOCK"
