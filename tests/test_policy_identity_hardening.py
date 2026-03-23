from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from spectrum_systems.modules.runtime.control_chain import (
    _resolve_policy_for_stage,
    build_control_chain_decision,
)
from spectrum_systems.modules.runtime.decision_gating import build_slo_gating_decision
from spectrum_systems.modules.runtime.replay_decision_engine import compare_decisions
from spectrum_systems.modules.runtime.replay_governance import (
    ReplayGovernancePolicyError,
    build_replay_governance_decision,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas"


def _schema_errors(schema_name: str, payload: dict) -> list[str]:
    schema = json.loads((_SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [e.message for e in validator.iter_errors(payload)]


def test_policy_resolution_fails_closed_on_missing_binding() -> None:
    with pytest.raises(Exception):
        _resolve_policy_for_stage(None)


def test_decision_artifact_requires_policy_identity() -> None:
    gating = build_slo_gating_decision(
        source_decision_id="ENF-1",
        artifact_id="artifact-1",
        stage="recommend",
        enforcement_policy="decision_grade",
        policy_id="policy-1",
        policy_version="1.0.0",
        enforcement_decision_status="allow",
        gating_outcome="proceed",
        gating_reason_code="enforcement_allow",
        ti_value=1.0,
        lineage_mode="strict",
        lineage_defaulted=False,
        lineage_valid=True,
        warnings=[],
        errors=[],
        recommended_action="proceed",
    )
    gating.pop("policy_id")
    assert _schema_errors("slo_gating_decision.schema.json", gating)


def test_no_placeholder_policy_values_allowed() -> None:
    gating = build_slo_gating_decision(
        source_decision_id="ENF-1",
        artifact_id="artifact-1",
        stage="recommend",
        enforcement_policy="decision_grade",
        policy_id="(unknown)",
        policy_version="(unknown)",
        enforcement_decision_status="allow",
        gating_outcome="proceed",
        gating_reason_code="enforcement_allow",
        ti_value=1.0,
        lineage_mode="strict",
        lineage_defaulted=False,
        lineage_valid=True,
        warnings=[],
        errors=[],
        recommended_action="proceed",
    )
    assert _schema_errors("slo_gating_decision.schema.json", gating)


def test_replay_detects_policy_drift() -> None:
    original = {
        "decision_status": "allow",
        "decision_reason_code": "strict_valid_lineage",
        "enforcement_policy": "decision_grade",
        "policy_id": "policy-a",
        "policy_version": "1.0.0",
        "recommended_action": "proceed",
    }
    replay = {
        "decision_status": "allow",
        "decision_reason_code": "strict_valid_lineage",
        "enforcement_policy": "decision_grade",
        "policy_id": "policy-b",
        "policy_version": "2.0.0",
        "recommended_action": "proceed",
    }
    consistency = compare_decisions(original, replay)
    assert consistency["status"] == "drifted"
    diff_fields = {d["field"] for d in consistency["differences"]}
    assert {"policy_id", "policy_version"}.issubset(diff_fields)


def test_no_default_policy_used_in_decision_paths() -> None:
    analysis = {
        "analysis_id": "analysis-1",
        "decision_consistency": {"status": "consistent", "differences": []},
        "reproducibility_score": 1.0,
    }
    with pytest.raises(ReplayGovernancePolicyError):
        build_replay_governance_decision(analysis, run_id="run-1", governance_policy=None)


def test_policy_identity_consistent_across_layers() -> None:
    gating = build_slo_gating_decision(
        source_decision_id="ENF-1",
        artifact_id="artifact-1",
        stage="recommend",
        enforcement_policy="decision_grade",
        policy_id="policy-decision-grade",
        policy_version="1.0.0",
        enforcement_decision_status="allow",
        gating_outcome="proceed",
        gating_reason_code="enforcement_allow",
        ti_value=1.0,
        lineage_mode="strict",
        lineage_defaulted=False,
        lineage_valid=True,
        warnings=[],
        errors=[],
        recommended_action="proceed",
    )
    control = build_control_chain_decision(
        artifact_id="artifact-1",
        stage="recommend",
        input_kind="gating",
        enforcement_decision_id="ENF-1",
        gating_decision_id="GATE-1",
        enforcement_policy="decision_grade",
        policy_id=gating["policy_id"],
        policy_version=gating["policy_version"],
        enforcement_decision_status="allow",
        gating_outcome="proceed",
        continuation_allowed=True,
        blocking_layer="none",
        primary_reason_code="control_chain_continue",
        ti_value=1.0,
        lineage_mode="strict",
        lineage_defaulted=False,
        lineage_valid=True,
        warnings=[],
        errors=[],
        recommended_action="continue",
        control_signals={
            "continuation_mode": "continue",
            "required_inputs": [],
            "required_validators": [],
            "repair_actions": [],
            "rerun_recommended": False,
            "human_review_required": False,
            "escalation_required": False,
            "publication_allowed": True,
            "decision_grade_allowed": True,
            "traceability_required": False,
            "control_signal_reason_codes": [],
        },
    )
    assert control["policy_id"] == gating["policy_id"]
    assert control["policy_version"] == gating["policy_version"]
