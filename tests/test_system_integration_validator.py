from __future__ import annotations

import copy

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.system_integration_validator import validate_core_system_integration


def _baseline_inputs() -> dict:
    return {
        "program_artifact": {
            "program_id": "PRG-QUALITY-CERTIFICATION",
            "schema_version": "1.0.0",
            "batches": ["BATCH-Z"],
        },
        "review_control_signal": {
            "signal_id": "rcs-001",
            "gate_assessment": "PASS",
        },
        "eval_result": {
            "run_id": "run-eval-001",
            "result_status": "pass",
        },
        "context_bundle": {
            "context_id": "ctx2-001",
        },
        "tpa_gate": {
            "context_bundle_ref": "context_bundle_v2:ctx2-001",
            "speculative_expansion_detected": False,
            "gate_replaces_control": False,
        },
        "roadmap_loop_validation": {
            "validation_id": "RLV-001",
            "determinism_status": "deterministic",
        },
        "roadmap_multi_batch_result": {
            "run_id": "RMB-001",
            "batches_executed_count": 0,
            "stop_reason": "authorization_block",
            "program_constraints_applied": True,
        },
        "control_decision": {
            "decision": "block",
            "review_eval_ingested": True,
        },
        "certification_pack": {
            "certification_status": "complete",
        },
        "validation_scope": {
            "batch_id": "BATCH-Z",
            "run_id": "run-batch-z-001",
            "mode": "governed_integration",
        },
        "trace_id": "trace-batch-z-001",
        "source_refs": {
            "program_artifact": "program_artifact:PRG-QUALITY-CERTIFICATION",
            "review_control_signal": "review_control_signal:rcs-001",
            "eval_result": "eval_result:run-eval-001",
            "context_bundle_v2": "context_bundle_v2:ctx2-001",
            "tpa_gate": "tpa_gate:AI-01-G",
            "roadmap_execution_loop_validation": "roadmap_execution_loop_validation:RLV-001",
            "roadmap_multi_batch_run_result": "roadmap_multi_batch_run_result:RMB-001",
            "control_decision": "control_execution_result:ctrl-001",
            "certification_pack": "control_loop_certification_pack:cert-001",
        },
        "created_at": "2026-04-03T23:30:00Z",
    }


def test_contract_example_validates() -> None:
    validate_artifact(load_example("core_system_integration_validation"), "core_system_integration_validation")


def test_full_integration_path_is_deterministic_and_replayable() -> None:
    kwargs = _baseline_inputs()
    first = validate_core_system_integration(**kwargs)
    second = validate_core_system_integration(**kwargs)
    assert first == second
    validate_artifact(first, "core_system_integration_validation")
    assert first["authority_boundary_status"] == "bounded"
    assert first["determinism_status"] == "deterministic"
    assert first["replay_status"] == "replayable"
    assert first["blocking_conditions"] == []
    assert first["trace_navigation"]["trace_id"] == first["trace_id"]
    assert first["trace_navigation"]["execution_path"][0] == first["source_refs"]["program_artifact"]
    assert first["trace_navigation"]["execution_path"][-1] == first["source_refs"]["certification_pack"]
    assert first["trace_navigation"]["layer_transitions"] == ["PRG->RVW", "RVW->CTX", "CTX->TPA", "TPA->RDX", "RDX->CONTROL", "CONTROL->CERT"]
    assert first["trace_navigation"] == second["trace_navigation"]
    for key in ("replay_from_context", "replay_from_plan", "replay_from_execution", "replay_from_failure"):
        entry = first["trace_navigation"]["replay_entry_points"][key]
        assert entry["required_artifacts"]
        assert first["trace_id"] in entry["trace_refs"]
    assert sorted(first["upstream_refs"]) == sorted(set(first["source_refs"].values()))
    assert first["related_artifacts"] == sorted(set(first["source_refs"].values()))


def test_failure_probe_program_allows_but_control_blocks_stays_fail_closed() -> None:
    kwargs = _baseline_inputs()
    kwargs["roadmap_multi_batch_result"]["batches_executed_count"] = 1
    artifact = validate_core_system_integration(**kwargs)
    assert artifact["deterministic_outcome"] == "failed_closed"
    assert "AUTH_CONTROL_BYPASS" in artifact["blocking_conditions"]


def test_failure_probe_tpa_requires_context_but_missing_ref_fails_closed() -> None:
    kwargs = _baseline_inputs()
    kwargs["tpa_gate"]["context_bundle_ref"] = ""
    artifact = validate_core_system_integration(**kwargs)
    assert "PROP_CTX_TO_TPA_MISSING" in artifact["blocking_conditions"]


def test_failure_probe_replay_chain_incomplete_fails_closed() -> None:
    kwargs = _baseline_inputs()
    kwargs["source_refs"].pop("certification_pack")
    artifact = validate_core_system_integration(**kwargs)
    assert artifact["replay_status"] == "not_replayable"
    assert "REPLAY_CHAIN_INCOMPLETE" in artifact["blocking_conditions"]
    assert artifact["trace_navigation"]["replay_ready"] is False
    assert "missing:certification_pack" in artifact["trace_navigation"]["execution_path"]


def test_failure_probe_review_authorization_path_is_rejected() -> None:
    kwargs = _baseline_inputs()
    kwargs["review_control_signal"]["authorizes_execution"] = True
    artifact = validate_core_system_integration(**kwargs)
    assert artifact["authority_boundary_status"] == "violated"
    assert "AUTH_REVIEW_DIRECT_AUTHORIZATION" in artifact["blocking_conditions"]


def test_failure_probe_missing_review_eval_ingestion_and_program_constraint_propagation() -> None:
    kwargs = copy.deepcopy(_baseline_inputs())
    kwargs["control_decision"]["review_eval_ingested"] = False
    kwargs["roadmap_multi_batch_result"]["program_constraints_applied"] = False
    artifact = validate_core_system_integration(**kwargs)
    assert "PROP_REVIEW_EVAL_NOT_INGESTED" in artifact["blocking_conditions"]
    assert "PROP_PROGRAM_CONSTRAINTS_MISSING" in artifact["blocking_conditions"]
