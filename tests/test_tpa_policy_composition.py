from __future__ import annotations

from spectrum_systems.modules.governance.tpa_policy_composition import (
    load_tpa_policy_composition,
    resolve_tpa_policy_decision,
)


def test_policy_composition_deterministic_for_same_inputs() -> None:
    composition = load_tpa_policy_composition()
    inputs = {
        "required_scope": True,
        "tpa_lineage_present": True,
        "execution_mode": "feature_build",
        "complexity_decision": "freeze",
        "simplicity_decision": "allow",
        "promotion_ready_requested": True,
        "tpa_mode": "full",
        "lightweight_eligible": True,
    }
    first = resolve_tpa_policy_decision(inputs, composition=composition)
    second = resolve_tpa_policy_decision(inputs, composition=composition)
    assert first == second
    assert first["final_decision"] == "freeze"
    assert first["promotion_ready"] is False


def test_cleanup_only_and_review_conflicts_resolve_to_block() -> None:
    composition = load_tpa_policy_composition()
    decision = resolve_tpa_policy_decision(
        {
            "required_scope": True,
            "tpa_lineage_present": True,
            "execution_mode": "cleanup_only",
            "cleanup_only_validation": {"mode_enabled": True, "equivalence_proven": False, "replay_ref": ""},
            "complexity_decision": "warn",
            "simplicity_decision": "freeze",
            "promotion_ready_requested": True,
            "tpa_mode": "lightweight",
            "lightweight_eligible": True,
        },
        composition=composition,
    )
    assert decision["final_decision"] == "block"
    assert "cleanup_only_missing_equivalence" in decision["blocking_reasons"]
    assert "cleanup_only_missing_replay_ref" in decision["blocking_reasons"]
    assert "simplicity_review_freeze" in decision["blocking_reasons"]
    assert decision["promotion_ready"] is False


def test_lightweight_constraints_are_composed() -> None:
    composition = load_tpa_policy_composition()
    decision = resolve_tpa_policy_decision(
        {
            "required_scope": False,
            "tpa_lineage_present": True,
            "execution_mode": "feature_build",
            "complexity_decision": "allow",
            "simplicity_decision": "allow",
            "promotion_ready_requested": True,
            "tpa_mode": "lightweight",
            "lightweight_eligible": False,
        },
        composition=composition,
    )
    assert decision["final_decision"] == "block"
    assert "lightweight_mode_not_eligible" in decision["blocking_reasons"]


def test_lightweight_allowlisted_evidence_omission_passes() -> None:
    composition = load_tpa_policy_composition()
    decision = resolve_tpa_policy_decision(
        {
            "required_scope": False,
            "tpa_lineage_present": True,
            "execution_mode": "feature_build",
            "complexity_decision": "allow",
            "simplicity_decision": "allow",
            "promotion_ready_requested": True,
            "tpa_mode": "lightweight",
            "lightweight_eligible": True,
            "lightweight_evidence_omissions": ["tpa_gate.selection_metrics.simplify_delta"],
        },
        composition=composition,
    )
    assert decision["final_decision"] in {"allow", "warn"}


def test_lightweight_non_allowlisted_evidence_omission_blocks() -> None:
    composition = load_tpa_policy_composition()
    decision = resolve_tpa_policy_decision(
        {
            "required_scope": False,
            "tpa_lineage_present": True,
            "execution_mode": "feature_build",
            "complexity_decision": "allow",
            "simplicity_decision": "allow",
            "promotion_ready_requested": True,
            "tpa_mode": "lightweight",
            "lightweight_eligible": True,
            "lightweight_evidence_omissions": ["tpa_gate.selection_metrics.build"],
        },
        composition=composition,
    )
    assert decision["final_decision"] == "block"
    assert any("lightweight_evidence_omission_not_allowlisted" in reason for reason in decision["blocking_reasons"])
