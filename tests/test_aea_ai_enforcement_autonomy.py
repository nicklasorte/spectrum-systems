from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.aea_ai_enforcement_autonomy import (
    AEACompositionError,
    compose_owner_posture_refs,
    enforce_no_protected_authority_leaks,
    require_cde_decision,
)


def _owner_artifacts() -> dict[str, dict[str, object]]:
    return {
        "TLX": {"owner": "TLX", "artifact_type": "tlx_ai_dispatch_audit_record", "record_id": "REC-TLX-AUDIT"},
        "CON": {"owner": "CON", "artifact_type": "con_ai_wiring_compliance_report", "record_id": "REC-CON-WIRING"},
        "EVL": {"owner": "EVL", "artifact_type": "evl_ai_eval_coverage_completeness_result", "record_id": "REC-EVL-COV"},
        "EVD": {"owner": "EVD", "artifact_type": "evd_ai_evidence_strength_result", "record_id": "REC-EVD-STRENGTH"},
        "LIN": {"owner": "LIN", "artifact_type": "lin_ai_execution_lineage_completeness_report", "record_id": "REC-LIN-COMPLETE"},
        "REP": {"owner": "REP", "artifact_type": "rep_ai_replay_completeness_result", "record_id": "REC-REP-COMPLETE"},
        "OBS": {"owner": "OBS", "artifact_type": "obs_ai_call_coverage_report", "record_id": "REC-OBS-COVERAGE"},
        "PRM": {"owner": "PRM", "artifact_type": "prm_prompt_drift_report", "record_id": "REC-PRM-DRIFT"},
        "CTX": {"owner": "CTX", "artifact_type": "ctx_ai_context_integrity_result", "record_id": "REC-CTX-INTEGRITY"},
        "CAP": {"owner": "CAP", "artifact_type": "cap_ai_cost_overrun_guard_result", "record_id": "REC-CAP-BUDGET"},
        "SLO": {"owner": "SLO", "artifact_type": "slo_ai_reliability_threshold_result", "record_id": "REC-SLO-RELIABILITY"},
        "QOS": {"owner": "QOS", "artifact_type": "qos_ai_retry_storm_report", "record_id": "REC-QOS-RETRY"},
        "PRG": {"owner": "PRG", "artifact_type": "prg_ai_usage_anomaly_record", "record_id": "REC-PRG-ANOMALY"},
    }


def test_composition_is_reference_only_and_owner_exact() -> None:
    refs = compose_owner_posture_refs(owner_artifacts=_owner_artifacts())
    assert refs["owner_count"] == 13
    assert refs["composition_mode"] == "produce_reference_compose"
    assert refs["composed_owner_refs"]["TLX"] == "REC-TLX-AUDIT"


def test_composition_fails_closed_on_owner_mismatch() -> None:
    artifacts = _owner_artifacts()
    artifacts["EVL"]["owner"] = "CON"
    with pytest.raises(AEACompositionError, match="owner_mismatch"):
        compose_owner_posture_refs(owner_artifacts=artifacts)


def test_no_protected_authority_leak_outside_cde() -> None:
    artifacts = _owner_artifacts()
    artifacts["PRG"] = {
        "owner": "PRG",
        "artifact_type": "cde_ai_trust_posture_decision",
        "record_id": "REC-ILLEGAL",
    }
    with pytest.raises(AEACompositionError, match="protected_authority_leak"):
        enforce_no_protected_authority_leaks(owner_artifacts=artifacts)


def test_cde_is_only_final_authority_and_must_reference_upstream_outputs() -> None:
    artifacts = _owner_artifacts()
    enforce_no_protected_authority_leaks(owner_artifacts=artifacts)
    refs = compose_owner_posture_refs(owner_artifacts=artifacts)

    cde_decision = {
        "owner": "CDE",
        "artifact_type": "cde_ai_trust_posture_decision",
        "record_id": "REC-CDE-DECISION",
        "evidence_refs": list(refs["composed_owner_refs"].values()),
    }
    accepted = require_cde_decision(cde_decision=cde_decision, required_owner_refs=refs["composed_owner_refs"])
    assert accepted["owner"] == "CDE"


def test_cde_decision_fails_when_missing_composed_reference() -> None:
    refs = compose_owner_posture_refs(owner_artifacts=_owner_artifacts())
    cde_decision = {
        "owner": "CDE",
        "artifact_type": "cde_partial_disable_ai_decision",
        "record_id": "REC-CDE-DECISION",
        "evidence_refs": ["REC-TLX-AUDIT"],
    }
    with pytest.raises(AEACompositionError, match="missing_composed_refs"):
        require_cde_decision(cde_decision=cde_decision, required_owner_refs=refs["composed_owner_refs"])
