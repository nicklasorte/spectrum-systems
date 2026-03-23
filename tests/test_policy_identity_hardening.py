from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.control_chain import run_control_chain  # noqa: E402
from spectrum_systems.modules.runtime.decision_gating import STAGE_SYNTHESIS  # noqa: E402
from spectrum_systems.modules.runtime.replay_governance import (  # noqa: E402
    REPLAY_STATUS_CONSISTENT,
    ReplayGovernancePolicyError,
    build_replay_governance_decision,
)


def _explicit_governance_policy(**overrides: Any) -> Dict[str, Any]:
    policy = {
        "policy_name": "bas_replay_governance",
        "policy_version": "1.0.0",
        "drift_action": "quarantine",
        "indeterminate_action": "require_review",
        "missing_replay_action": "allow",
        "require_replay": False,
    }
    policy.update(overrides)
    return policy


def _replay_analysis() -> Dict[str, Any]:
    return {
        "analysis_id": "analysis-001",
        "trace_id": "trace-001",
        "replay_result_id": "replay-001",
        "original_decision": {"decision_status": "allow", "decision_reason_code": "slo_pass"},
        "replay_decision": {"decision_status": "allow", "decision_reason_code": "slo_pass"},
        "decision_consistency": {"status": REPLAY_STATUS_CONSISTENT, "differences": []},
        "reproducibility_score": 1.0,
        "explanation": "policy hardening test",
        "created_at": "2026-01-01T00:00:00+00:00",
    }


def test_decision_grade_artifact_missing_policy_identity_fails() -> None:
    analysis = _replay_analysis()
    bad_policy = _explicit_governance_policy()
    bad_policy.pop("policy_version")
    with pytest.raises(ReplayGovernancePolicyError, match="policy_version"):
        build_replay_governance_decision(
            analysis,
            run_id="run-policy-hardening-1",
            governance_policy=bad_policy,
        )


def test_control_chain_producer_does_not_emit_unknown_policy() -> None:
    enforcement_input = {
        "artifact_type": "slo_enforcement_decision",
        "artifact_id": "art-policy-hardening-1",
        "decision_id": "ENF-POLICY-001",
        "decision_status": "allow",
        "traceability_integrity_sli": 1.0,
        "lineage_validation_mode": "strict",
        "lineage_defaulted": False,
        "lineage_valid": True,
        "warnings": [],
        "errors": [],
        "recommended_action": "proceed",
        "evaluated_at": "2026-01-01T00:00:00+00:00",
        "contract_version": "1.0.0",
        # intentionally omitted: enforcement_policy
    }

    result = run_control_chain(enforcement_input, stage=STAGE_SYNTHESIS)
    decision = result["control_chain_decision"]

    assert result["continuation_allowed"] is False
    assert decision["enforcement_policy"] != "(unknown)"
    assert any("enforcement_policy" in err for err in decision["errors"])


def test_build_replay_governance_requires_explicit_policy() -> None:
    analysis = _replay_analysis()
    with pytest.raises(
        ReplayGovernancePolicyError,
        match="governance_policy is required",
    ):
        build_replay_governance_decision(analysis, run_id="run-policy-hardening-2")


def test_explicit_governance_policy_produces_valid_replay_governance() -> None:
    analysis = _replay_analysis()
    artifact = build_replay_governance_decision(
        analysis,
        run_id="run-policy-hardening-3",
        governance_policy=_explicit_governance_policy(),
    )
    assert artifact["governance_policy"]["policy_version"] == "1.0.0"
    assert artifact["decision"]["system_response"] == "allow"
