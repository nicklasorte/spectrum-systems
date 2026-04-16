from __future__ import annotations

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.aea_ai_enforcement_autonomy import (
    AEAEnforcementError,
    AICallSite,
    build_compliance_bundle,
    cde_authority,
    detect_ai_call_sites,
    enforce_tlx_wiring,
    execute_aea001,
    run_red_team_rounds,
)


def _safe_call_sites() -> list[AICallSite]:
    return [
        AICallSite(path="spectrum_systems/modules/runtime/tlx.py", line=10, code="dispatch_via_tlx(model='mock-1')"),
        AICallSite(path="spectrum_systems/modules/runtime/ai_governed_integration.py", line=40, code="tlx_dispatch(request, provider_result)"),
    ]


def test_tlx_invariant_passes_when_all_ai_paths_use_tlx() -> None:
    detection = detect_ai_call_sites(_safe_call_sites())
    enforce = enforce_tlx_wiring(detection)
    validate_artifact(detection, "tlx_ai_call_site_detection_report")
    validate_artifact(enforce, "tlx_ai_wiring_enforcement_result")
    assert enforce["status"] == "pass"


def test_bypass_detection_fails_closed() -> None:
    call_sites = _safe_call_sites() + [
        AICallSite(path="spectrum_systems/modules/runtime/raw_adapter.py", line=5, code="openai.responses.create(model='gpt-x')"),
    ]
    detection = detect_ai_call_sites(call_sites)
    enforce = enforce_tlx_wiring(detection)
    validate_artifact(detection, "tlx_ai_call_site_detection_report")
    validate_artifact(enforce, "tlx_ai_wiring_enforcement_result")
    assert enforce["status"] == "fail"

    try:
        execute_aea001(call_sites=call_sites)
    except AEAEnforcementError as exc:
        assert "TLX-only invariant" in str(exc)
    else:
        raise AssertionError("expected fail-closed bypass rejection")


def test_compliance_visibility_reports_fail_on_missing_obs_lin_rep() -> None:
    detection = detect_ai_call_sites(_safe_call_sites())
    enforce = enforce_tlx_wiring(detection)
    bundle = build_compliance_bundle(
        detection_report=detection,
        tlx_enforcement=enforce,
        missing_traces=2,
        missing_lineage_links=1,
        missing_replay_fields=1,
    )
    for artifact_type, artifact in (
        ("con_forbidden_direct_ai_call_report", bundle["forbidden"]),
        ("con_ai_wiring_compliance_report", bundle["compliance"]),
        ("obs_ai_call_coverage_report", bundle["obs"]),
        ("lin_ai_execution_lineage_completeness_report", bundle["lin"]),
        ("rep_ai_replay_completeness_result", bundle["rep"]),
    ):
        validate_artifact(artifact, artifact_type)
    assert bundle["obs"]["status"] == "fail"
    assert bundle["lin"]["status"] == "fail"
    assert bundle["rep"]["status"] == "fail"


def test_cde_authority_decides_halt_or_partial_disable() -> None:
    fail_input = {
        "lin": {
            "artifact_type": "lin_ai_execution_lineage_completeness_report",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "record_id": "REC-LIN",
            "run_id": "run-aea-001",
            "owner": "LIN",
            "status": "fail",
            "evidence_refs": ["x"],
            "payload": {},
        }
    }
    decisions = cde_authority(bypass_detected=True, trust_inputs=fail_input, disable_routes=["task.ai.codegen"])
    validate_artifact(decisions["kill"], "cde_ai_bypass_kill_switch_decision")
    validate_artifact(decisions["trust"], "cde_ai_trust_posture_decision")
    validate_artifact(decisions["partial"], "cde_partial_disable_ai_decision")
    assert decisions["kill"]["status"] == "halt"
    assert decisions["partial"]["status"] == "degraded"


def test_all_red_team_rounds_and_fix_packs_execute() -> None:
    rounds = run_red_team_rounds()
    assert len(rounds) == 14
    for idx in range(0, len(rounds), 2):
        red = rounds[idx]
        fix = rounds[idx + 1]
        validate_artifact(red, red["artifact_type"])
        validate_artifact(fix, fix["artifact_type"])
        for exploit in red["payload"]["exploit_codes"]:
            assert f"fixed:{exploit}" in fix["payload"]["exploit_codes"]


def test_full_execution_emits_final_audits_and_coverage() -> None:
    result = execute_aea001(call_sites=_safe_call_sites())

    artifact_types = [
        "tlx_ai_dispatch_audit_record",
        "evl_ai_eval_coverage_completeness_result",
        "evl_stale_ai_eval_report",
        "evd_ai_evidence_strength_result",
        "ctx_ai_context_integrity_result",
        "prm_prompt_shadow_detection_report",
        "prm_prompt_drift_report",
        "cap_ai_cost_overrun_guard_result",
        "slo_ai_reliability_threshold_result",
        "qos_ai_retry_storm_report",
        "prg_ai_usage_anomaly_record",
        "tst_ai_bypass_fixture_suite",
        "tst_ai_schema_enforcement_test_pack",
        "tst_ai_replay_eval_chain_test_pack",
        "final_ai_tlx_enforcement_audit_report",
        "final_ai_coverage_100_validation_report",
        "final_ai_full_system_rerun_report",
    ]
    artifact_map = {
        "tlx_ai_dispatch_audit_record": result["dispatch"],
        "evl_ai_eval_coverage_completeness_result": result["hardening"]["evl_coverage"],
        "evl_stale_ai_eval_report": result["hardening"]["evl_stale"],
        "evd_ai_evidence_strength_result": result["hardening"]["evd"],
        "ctx_ai_context_integrity_result": result["hardening"]["ctx"],
        "prm_prompt_shadow_detection_report": result["hardening"]["prm_shadow"],
        "prm_prompt_drift_report": result["hardening"]["prm_drift"],
        "cap_ai_cost_overrun_guard_result": result["control"]["cap"],
        "slo_ai_reliability_threshold_result": result["control"]["slo"],
        "qos_ai_retry_storm_report": result["control"]["qos"],
        "prg_ai_usage_anomaly_record": result["control"]["prg"],
        "tst_ai_bypass_fixture_suite": result["fixtures"]["tst_bypass"],
        "tst_ai_schema_enforcement_test_pack": result["fixtures"]["tst_schema"],
        "tst_ai_replay_eval_chain_test_pack": result["fixtures"]["tst_chain"],
        "final_ai_tlx_enforcement_audit_report": result["finals"]["final_tlx"],
        "final_ai_coverage_100_validation_report": result["finals"]["coverage"],
        "final_ai_full_system_rerun_report": result["finals"]["rerun"],
    }
    for artifact_type in artifact_types:
        validate_artifact(artifact_map[artifact_type], artifact_type)

    assert result["finals"]["final_tlx"]["status"] == "pass"
    assert result["finals"]["coverage"]["status"] == "pass"


def test_examples_validate_for_new_contracts() -> None:
    for name in (
        "tlx_ai_wiring_enforcement_result",
        "con_forbidden_direct_ai_call_report",
        "cde_ai_bypass_kill_switch_decision",
        "fre_tpa_sel_pqx_ai_fix_pack_h7",
        "final_ai_full_system_rerun_report",
    ):
        validate_artifact(load_example(name), name)
