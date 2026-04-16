from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.aea_ai_enforcement_autonomy import (
    AEACompositionError,
    compose_owner_posture_refs,
    detect_tlx_mediation,
    enforce_no_protected_authority_leaks,
    final_ai_full_system_rerun_status,
    require_cde_decision,
)


def _owner_artifacts() -> dict[str, dict[str, object]]:
    return {
        "TLX": {"owner": "TLX", "artifact_type": "tlx_ai_dispatch_audit_record", "record_id": "REC-TLX"},
        "CON": {"owner": "CON", "artifact_type": "con_ai_wiring_compliance_report", "record_id": "REC-CON"},
        "EVL": {"owner": "EVL", "artifact_type": "evl_ai_eval_coverage_completeness_result", "record_id": "REC-EVL"},
        "EVD": {"owner": "EVD", "artifact_type": "evd_ai_evidence_strength_result", "record_id": "REC-EVD"},
        "LIN": {"owner": "LIN", "artifact_type": "lin_ai_execution_lineage_completeness_report", "record_id": "REC-LIN"},
        "REP": {"owner": "REP", "artifact_type": "rep_ai_replay_completeness_result", "record_id": "REC-REP"},
        "OBS": {"owner": "OBS", "artifact_type": "obs_ai_call_coverage_report", "record_id": "REC-OBS"},
        "PRM": {"owner": "PRM", "artifact_type": "prm_prompt_drift_report", "record_id": "REC-PRM"},
        "CTX": {"owner": "CTX", "artifact_type": "ctx_ai_context_integrity_result", "record_id": "REC-CTX"},
        "CAP": {"owner": "CAP", "artifact_type": "cap_ai_cost_overrun_guard_result", "record_id": "REC-CAP"},
        "SLO": {"owner": "SLO", "artifact_type": "slo_ai_reliability_threshold_result", "record_id": "REC-SLO"},
        "QOS": {"owner": "QOS", "artifact_type": "qos_ai_retry_storm_report", "record_id": "REC-QOS"},
        "PRG": {"owner": "PRG", "artifact_type": "prg_ai_usage_anomaly_record", "record_id": "REC-PRG"},
    }


def test_tlx_bypass_rejected_when_tlx_only_appears_in_comment_text() -> None:
    spoofed = {
        "direct_provider_call": True,
        "raw_code": "openai.responses.create(model='x') # tlx",
        "mediation": {
            "owner": "TLX",
            "dispatch_record_ref": "REC-TLX",
            "call_path": ["openai.responses.create"],
        },
    }
    assert detect_tlx_mediation(spoofed) is False


def test_tlx_structural_mediation_passes() -> None:
    mediated = {
        "direct_provider_call": False,
        "raw_code": "dispatch_via_governed_adapter()",
        "mediation": {
            "owner": "TLX",
            "dispatch_record_ref": "REC-TLX",
            "call_path": ["ctx_preflight", "prm_admission", "tlx_dispatch", "tlx_ai_adapter_dispatch_record"],
        },
    }
    assert detect_tlx_mediation(mediated) is True


def test_rerun_fails_when_trust_is_halt_even_if_kill_is_continue() -> None:
    status = final_ai_full_system_rerun_status(
        final_tlx_status="pass",
        coverage_status="pass",
        cde_bundle={"kill": {"status": "continue"}, "trust": {"status": "halt"}},
    )
    assert status == "fail"


def test_rerun_passes_only_when_kill_and_trust_are_non_blocking() -> None:
    status = final_ai_full_system_rerun_status(
        final_tlx_status="pass",
        coverage_status="pass",
        cde_bundle={"kill": {"status": "continue"}, "trust": {"status": "continue"}},
    )
    assert status == "pass"


def test_missing_required_owner_fails_composition() -> None:
    partial = _owner_artifacts()
    partial.pop("OBS")
    with pytest.raises(AEACompositionError, match="missing_required_owners"):
        compose_owner_posture_refs(owner_artifacts=partial)


def test_require_cde_decision_fails_with_incomplete_required_refs() -> None:
    refs = compose_owner_posture_refs(owner_artifacts=_owner_artifacts())["composed_owner_refs"]
    refs.pop("QOS")
    with pytest.raises(AEACompositionError, match="incomplete_required_owner_refs"):
        require_cde_decision(
            cde_decision={
                "owner": "CDE",
                "artifact_type": "cde_ai_trust_posture_decision",
                "evidence_refs": ["REC-TLX"],
            },
            required_owner_refs=refs,
        )


def test_payload_owner_mismatch_under_cde_key_fails() -> None:
    with pytest.raises(AEACompositionError, match="map_key_owner_mismatch"):
        enforce_no_protected_authority_leaks(
            owner_artifacts={
                "CDE": {
                    "owner": "PRG",
                    "artifact_type": "cde_ai_trust_posture_decision",
                    "record_id": "REC-BAD",
                }
            }
        )


def test_cde_decision_accepts_correct_owner_and_complete_evidence() -> None:
    refs = compose_owner_posture_refs(owner_artifacts=_owner_artifacts())["composed_owner_refs"]
    enforce_no_protected_authority_leaks(owner_artifacts={**_owner_artifacts(), "CDE": {"owner": "CDE", "artifact_type": "cde_ai_trust_posture_decision", "record_id": "REC-CDE"}})
    decision = require_cde_decision(
        cde_decision={
            "owner": "CDE",
            "artifact_type": "cde_ai_trust_posture_decision",
            "evidence_refs": list(refs.values()),
        },
        required_owner_refs=refs,
    )
    assert decision["owner"] == "CDE"
