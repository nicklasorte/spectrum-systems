from __future__ import annotations

import copy

import pytest

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.runtime.rqx_redteam_orchestrator import (
    RQXRedTeamError,
    build_fix_slice_request,
    build_redteam_finding_record,
    route_finding_owner,
    run_redteam_cycle,
    verify_closure_proof,
)


def _review_request() -> dict:
    return load_example("redteam_review_request")


def _round_config() -> dict:
    return load_example("redteam_round_config")


def _exploit_bundle() -> dict:
    return load_example("redteam_exploit_bundle")


def _finding(*, finding_class: str = "enforcement_mismatch") -> dict:
    finding = load_example("redteam_finding_record")
    finding["finding_class"] = finding_class
    return finding


def _closure_request() -> dict:
    return load_example("redteam_closure_request")


def test_rqx_roundtrip_orchestration_happy_path() -> None:
    request = _review_request()
    config = _round_config()
    exploit = _exploit_bundle()
    finding = _finding()
    closure = _closure_request()

    result = run_redteam_cycle(
        review_request=request,
        round_config=config,
        findings=[finding],
        exploit_bundle=exploit,
        closure_requests=[closure],
    )

    assert result["status"] == "completed"
    assert len(result["fix_slice_requests"]) == 1
    assert result["fix_slice_requests"][0]["owner"] == "SEL"
    assert result["closure_results"][0]["status"] == "pass"


def test_rqx_owner_routing_maps_required_classes() -> None:
    expected = {
        "interpretation": "RIL",
        "repair_planning": "FRE",
        "decision_quality": "CDE",
        "enforcement_mismatch": "SEL",
        "execution_trace": "PQX",
        "trust_policy": "TPA",
    }
    for finding_class, owner in expected.items():
        finding = _finding(finding_class=finding_class)
        routed = route_finding_owner(finding_record=finding)
        assert routed["owner"] == owner


def test_rqx_unmappable_finding_fails_closed() -> None:
    finding = _finding()
    finding["finding_class"] = "unknown"

    with pytest.raises(Exception):
        route_finding_owner(finding_record=finding)


def test_rqx_closure_proof_gate_blocks_without_required_proof() -> None:
    finding = _finding()
    closure = _closure_request()
    closure["proof_refs"] = ["eval_case:only"]

    proof = verify_closure_proof(closure_request=closure, finding_record=finding)

    assert proof["status"] == "fail"
    assert "missing_regression_test_proof" in proof["blocking_reasons"]
    assert "missing_hardening_proof" in proof["blocking_reasons"]


def test_rqx_fix_slice_builder_is_bounded_and_non_authoritative() -> None:
    finding = build_redteam_finding_record(
        trace_id="trace-rqx-001",
        finding_class="interpretation",
        finding_statement="Ambiguous interpretation branch allows contradictory judgments.",
        exploit_refs=["exploit:exp-02"],
        bounded_scope="normalize interpretation conflict edge",
    )
    request = build_fix_slice_request(finding_record=finding, round_config=_round_config())

    assert request["owner"] == "RIL"
    assert "rqx_must_not_reinterpret_semantics" in request["non_authority_assertions"]


def test_rqx_cycle_routes_unmappable_to_operator_handoff() -> None:
    request = _review_request()
    config = _round_config()
    exploit = _exploit_bundle()
    finding = _finding()
    finding["finding_class"] = "execution_trace"
    bad = copy.deepcopy(finding)
    bad["finding_id"] = "rqx-find-fedcba9876543210"
    bad["finding_class"] = "unknown_class"
    bad["finding_statement"] = "unknown"

    with pytest.raises(Exception):
        run_redteam_cycle(
            review_request=request,
            round_config=config,
            findings=[finding, bad],
            exploit_bundle=exploit,
            closure_requests=[],
        )
