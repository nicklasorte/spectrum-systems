from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.governed_repair_foundation import (
    GovernedRepairFoundationError,
    build_bounded_repair_candidate,
    build_cde_repair_continuation_input,
    build_execution_failure_packet,
    build_tpa_repair_gating_input,
    evaluate_slice_artifact_readiness,
)
from spectrum_systems.modules.runtime.roadmap_slice_registry import RoadmapSliceRegistryError, load_slice_registry


_FIXTURE_ROOT = Path("tests/fixtures/roadmaps/aut_reg_05a")


def _load_slice(slice_id: str) -> dict:
    rows = load_slice_registry(Path("contracts/roadmap/slice_registry.json"))
    return next(row for row in rows if row["slice_id"] == slice_id)


def test_failure_surface_declaration_required_for_aut_seam() -> None:
    aut05 = _load_slice("AUT-05")
    assert aut05["failure_surface"]["runtime_seam"] == "review_control_decision_projection"


def test_invalid_failure_surface_owner_fails_closed(tmp_path: Path) -> None:
    payload = json.loads(Path("contracts/roadmap/slice_registry.json").read_text(encoding="utf-8"))
    row = next(item for item in payload["slices"] if item["slice_id"] == "AUT-05")
    row["failure_surface"]["owning_system"] = "NOT-A-SYSTEM"
    path = tmp_path / "slice_registry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RoadmapSliceRegistryError, match="owning_system"):
        load_slice_registry(path)


def test_invalid_failure_surface_repairability_class_fails_closed(tmp_path: Path) -> None:
    payload = json.loads(Path("contracts/roadmap/slice_registry.json").read_text(encoding="utf-8"))
    row = next(item for item in payload["slices"] if item["slice_id"] == "AUT-10")
    row["failure_surface"]["repairability_class"] = "full_autonomy"
    path = tmp_path / "slice_registry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RoadmapSliceRegistryError, match="repairability_class"):
        load_slice_registry(path)


def test_artifact_readiness_missing_artifact_blocks() -> None:
    result = evaluate_slice_artifact_readiness(
        slice_id="AUT-05",
        owning_system="RIL",
        runtime_seam="review_control_decision_projection",
        required_artifacts=[
            {
                "artifact_ref": "tests/fixtures/roadmaps/aut_reg_05a/review_control_signal.does_not_exist.json",
                "schema": "review_control_signal",
            }
        ],
        contract_invariants=["control_decision_shape"],
        expected_failure_classes=["missing_artifact"],
        command="python -c 'noop'",
    )
    assert result["status"] == "blocked"
    assert result["blocking_reasons"][0]["failure_class"] == "missing_artifact"


def test_artifact_readiness_invalid_shape_blocks(tmp_path: Path) -> None:
    broken = json.loads((_FIXTURE_ROOT / "review_control_signal.json").read_text(encoding="utf-8"))
    del broken["control_decision"]["system_response"]
    broken_path = tmp_path / "broken_review_control_signal.json"
    broken_path.write_text(json.dumps(broken), encoding="utf-8")

    result = evaluate_slice_artifact_readiness(
        slice_id="AUT-05",
        owning_system="RIL",
        runtime_seam="review_control_decision_projection",
        required_artifacts=[
            {"artifact_ref": str(broken_path), "schema": "review_control_signal"},
        ],
        contract_invariants=["control_decision_shape"],
        expected_failure_classes=["invalid_artifact_shape"],
        command="python -c 'noop'",
    )
    assert result["status"] == "blocked"
    assert result["blocking_reasons"][0]["failure_class"] == "invalid_artifact_shape"


def test_artifact_readiness_authenticity_and_lineage_mismatch_blocks(tmp_path: Path) -> None:
    adm = json.loads(Path("contracts/examples/build_admission_record.example.json").read_text(encoding="utf-8"))
    adm["authenticity"]["issuer"] = "PQX"
    adm["trace_id"] = "trace-mismatch-a"
    req = json.loads(Path("contracts/examples/normalized_execution_request.example.json").read_text(encoding="utf-8"))
    req["trace_id"] = "trace-mismatch-b"
    handoff = json.loads(Path("contracts/examples/tlc_handoff_record.example.json").read_text(encoding="utf-8"))
    handoff["trace_id"] = "trace-mismatch-c"

    adm_path = tmp_path / "build_admission_record.example.json"
    req_path = tmp_path / "normalized_execution_request.example.json"
    handoff_path = tmp_path / "tlc_handoff_record.example.json"
    adm_path.write_text(json.dumps(adm), encoding="utf-8")
    req_path.write_text(json.dumps(req), encoding="utf-8")
    handoff_path.write_text(json.dumps(handoff), encoding="utf-8")

    result = evaluate_slice_artifact_readiness(
        slice_id="AUT-07",
        owning_system="TPA",
        runtime_seam="repo_write_lineage_authenticity_guard",
        required_artifacts=[
            {"artifact_ref": str(adm_path), "schema": "build_admission_record", "authenticity_issuer": "AEX"},
            {"artifact_ref": str(req_path), "schema": "normalized_execution_request", "authenticity_issuer": "AEX"},
            {"artifact_ref": str(handoff_path), "schema": "tlc_handoff_record", "authenticity_issuer": "TLC"},
        ],
        contract_invariants=["lineage_trace_alignment"],
        expected_failure_classes=["authenticity_lineage_mismatch", "cross_artifact_mismatch"],
        command="python -c 'noop'",
    )
    classes = {row["failure_class"] for row in result["blocking_reasons"]}
    assert "authenticity_lineage_mismatch" in classes
    assert "cross_artifact_mismatch" in classes


def test_artifact_readiness_command_wiring_mismatch_blocks() -> None:
    result = evaluate_slice_artifact_readiness(
        slice_id="AUT-10",
        owning_system="RIL",
        runtime_seam="review_control_decision_command_wiring",
        required_artifacts=[
            {
                "artifact_ref": "contracts/examples/review_control_signal_artifact.json",
                "schema": "review_control_signal_artifact",
            },
        ],
        contract_invariants=["control_decision_payload_nested"],
        expected_failure_classes=["slice_contract_mismatch"],
        command="python -c \"build_review_roadmap(snapshot=snapshot, control_decision=decision)\"",
    )
    assert result["status"] == "blocked"
    assert {row["failure_class"] for row in result["blocking_reasons"]} == {"slice_contract_mismatch"}


def test_failure_packetization_and_repair_candidate_and_inputs() -> None:
    readiness = evaluate_slice_artifact_readiness(
        slice_id="AUT-10",
        owning_system="RIL",
        runtime_seam="review_control_decision_command_wiring",
        required_artifacts=[
            {
                "artifact_ref": "contracts/examples/review_control_signal_artifact.json",
                "schema": "review_control_signal_artifact",
            },
        ],
        contract_invariants=["control_decision_payload_nested"],
        expected_failure_classes=["slice_contract_mismatch"],
        command="python -c \"build_review_roadmap(snapshot=snapshot, control_decision=decision)\"",
    )

    packet = build_execution_failure_packet(
        readiness_result=readiness,
        execution_refs=["slice_execution:AUT-10"],
        trace_refs=["trace:aut-10"],
        enforcement_refs=["system_enforcement_result_artifact:sel-aut-10"],
        validation_refs=["pytest_failure:tests/test_review_roadmap_generator.py::test_requires_nested_control_decision"],
        batch_id="BATCH-AUT",
        umbrella_id="AUTONOMY_EXECUTION",
        roadmap_context_ref="contracts/roadmap/roadmap_structure.json",
    )
    assert packet["classified_failure_type"] == "slice_contract_mismatch"

    candidate = build_bounded_repair_candidate(failure_packet=packet)
    assert candidate["repairability_class"] == "slice_metadata"

    cde_input = build_cde_repair_continuation_input(failure_packet=packet, repair_candidate=candidate)
    assert cde_input["recommended_continuation"] == "continue_repair_bounded"

    tpa_input = build_tpa_repair_gating_input(
        failure_packet=packet,
        repair_candidate=candidate,
        retry_budget_remaining=1,
        complexity_score=2,
        risk_level="medium",
    )
    assert tpa_input["retry_budget_remaining"] == 1


def test_oversized_scope_is_rejected() -> None:
    packet = json.loads(Path("contracts/examples/execution_failure_packet.json").read_text(encoding="utf-8"))
    packet["affected_artifact_refs"] = [f"contracts/examples/a{i}.json" for i in range(8)]
    with pytest.raises(GovernedRepairFoundationError, match="scope exceeds bounded authority"):
        build_bounded_repair_candidate(failure_packet=packet, max_scope_refs=2)


def test_no_ownership_bleed_in_artifact_outputs() -> None:
    packet = json.loads(Path("contracts/examples/execution_failure_packet.json").read_text(encoding="utf-8"))
    candidate = build_bounded_repair_candidate(failure_packet=packet)
    cde_input = build_cde_repair_continuation_input(failure_packet=packet, repair_candidate=candidate)
    tpa_input = build_tpa_repair_gating_input(
        failure_packet=packet,
        repair_candidate=candidate,
        retry_budget_remaining=1,
        complexity_score=1,
        risk_level="low",
    )
    assert "candidate_id" not in cde_input
    assert "recommended_continuation" in cde_input
    assert "repair_scope_refs" in tpa_input
