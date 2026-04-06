from __future__ import annotations

import copy

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.system_enforcement_layer import enforce_system_boundaries


def _valid_context() -> dict:
    return {
        "source_module": "spectrum_systems.modules.runtime.pqx_slice_runner",
        "caller_identity": "scripts/pqx_runner.py",
        "emitted_at": "2026-04-05T10:00:00Z",
        "execution_request": {
            "execution_context": "pqx_governed",
            "pqx_entry": True,
            "direct_cli": False,
            "ad_hoc_runtime": False,
            "direct_slice_execution": False,
            "tpa_required": True,
            "recovery_involved": False,
            "certification_required": True,
        },
        "artifact_references": {
            "execution_artifact": "artifacts/execution_result.json",
            "trace_refs": ["trace://pqx/run-001", "trace://pqx/run-001/control"],
            "lineage": {
                "lineage_id": "lineage-001",
                "parent_refs": ["artifact://pqx/request-001"],
            },
            "tpa_lineage_artifact": "artifacts/tpa_lineage.json",
            "tpa_artifact": "artifacts/tpa_prompt_bundle.json",
        },
        "trace_refs": ["trace://pqx/run-001", "trace://pqx/run-001/control"],
        "lineage": {
            "lineage_id": "lineage-001",
            "parent_refs": ["artifact://pqx/request-001"],
        },
        "governance_evidence": {
            "preflight_evidence": "evidence/preflight.json",
            "control_evidence": "evidence/control.json",
            "certification_evidence": "evidence/certification.json",
        },
        "downstream_consumption": {
            "consumed_artifact_types": ["review_projection_bundle_artifact"],
        },
    }


def _violation_codes(result: dict) -> set[str]:
    return {item["violation_code"] for item in result["violations"]}


def test_valid_governed_path_allows() -> None:
    result = enforce_system_boundaries(_valid_context())

    assert result["enforcement_status"] == "allow"
    assert result["violations"] == []
    assert result["violated_boundaries"] == []
    assert result["required_artifacts_present"] is True
    validate_artifact(result, "system_enforcement_result_artifact")


def test_direct_execution_bypass_blocks_with_pqx_violation() -> None:
    context = _valid_context()
    context["execution_request"]["pqx_entry"] = False
    context["execution_request"]["execution_context"] = "direct"
    context["execution_request"]["direct_cli"] = True

    result = enforce_system_boundaries(context)

    assert result["enforcement_status"] == "block"
    assert "pqx_entry_violation" in _violation_codes(result)


def test_missing_artifacts_blocks() -> None:
    context = _valid_context()
    context["artifact_references"].pop("execution_artifact")

    result = enforce_system_boundaries(context)

    assert result["enforcement_status"] == "block"
    assert result["required_artifacts_present"] is False
    assert "missing_artifact_violation" in _violation_codes(result)


def test_missing_governance_evidence_blocks() -> None:
    context = _valid_context()
    context["governance_evidence"].pop("preflight_evidence")

    result = enforce_system_boundaries(context)

    assert result["enforcement_status"] == "block"
    assert "governance_evidence_violation" in _violation_codes(result)


def test_ril_boundary_violation_blocks_raw_review_consumption() -> None:
    context = _valid_context()
    context["downstream_consumption"]["consumed_artifact_types"] = ["raw_review_markdown"]

    result = enforce_system_boundaries(context)

    assert result["enforcement_status"] == "block"
    assert "ril_boundary_violation" in _violation_codes(result)


def test_partial_recovery_path_blocks() -> None:
    context = _valid_context()
    context["execution_request"]["recovery_involved"] = True
    context["artifact_references"]["failure_diagnosis_artifact"] = "artifacts/failure_diagnosis_artifact.json"
    context["artifact_references"].pop("repair_prompt_artifact", None)
    context["artifact_references"].pop("recovery_result_artifact", None)

    result = enforce_system_boundaries(context)

    assert result["enforcement_status"] == "block"
    assert "fre_boundary_violation" in _violation_codes(result)


def test_determinism_same_input_same_output() -> None:
    context = _valid_context()

    first = enforce_system_boundaries(context)
    second = enforce_system_boundaries(copy.deepcopy(context))

    assert first == second


def test_traceability_violations_map_to_specific_input_fields() -> None:
    context = _valid_context()
    context["execution_request"]["direct_slice_execution"] = True
    context["governance_evidence"].pop("control_evidence")

    result = enforce_system_boundaries(context)

    assert result["enforcement_status"] == "block"
    violations_by_code = {item["violation_code"]: item for item in result["violations"]}

    assert violations_by_code["pqx_entry_violation"]["field"] == "execution_request"
    assert violations_by_code["governance_evidence_violation"]["field"] == "governance_evidence"
    assert "PQX" in result["violated_boundaries"]
    assert "GOVERNANCE_EVIDENCE" in result["violated_boundaries"]
