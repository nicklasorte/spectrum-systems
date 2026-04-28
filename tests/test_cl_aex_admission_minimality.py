"""CL-04 / CL-05 / CL-06: AEX admission minimality, bypass red team, fix pass."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.core_loop_admission_minimality import (
    ALLOWED_ADMISSION_CLASSES,
    AdmissionMinimalityError,
    REASON_BYPASS_ATTEMPT,
    REASON_MISSING_CLASS,
    REASON_MISSING_FIELD,
    REASON_MISSING_PROOF,
    REASON_OK,
    REASON_UNKNOWN_CLASS,
    build_minimal_admission_packet,
    detect_admission_bypass,
    validate_admission_packet,
)


# --- CL-04 minimality fields --------------------------------------------


def test_cl04_minimal_repo_mutation_packet_validates() -> None:
    packet = build_minimal_admission_packet(
        admission_class="repo_mutation",
        trace_id="t1",
        run_id="r1",
        aex_admission_ref="adm-1",
    )
    result = validate_admission_packet(packet)
    assert result["ok"], result["violations"]
    assert result["primary_reason"] == REASON_OK


def test_cl04_minimal_non_mutating_packet_validates_without_proof() -> None:
    packet = build_minimal_admission_packet(
        admission_class="non_mutating_query",
        trace_id="t1",
        run_id="r1",
    )
    result = validate_admission_packet(packet)
    assert result["ok"], result["violations"]


def test_cl04_missing_admission_class_blocks() -> None:
    packet = {"trace_id": "t1", "run_id": "r1"}
    result = validate_admission_packet(packet)
    assert not result["ok"]
    assert result["primary_reason"] == REASON_MISSING_CLASS


def test_cl04_unknown_admission_class_blocks() -> None:
    packet = {"admission_class": "freeform_anything", "trace_id": "t1", "run_id": "r1"}
    result = validate_admission_packet(packet)
    assert not result["ok"]
    assert any(v["reason_code"] == REASON_UNKNOWN_CLASS for v in result["violations"])


def test_cl04_repo_mutation_without_proof_blocks() -> None:
    packet = {"admission_class": "repo_mutation", "trace_id": "t1", "run_id": "r1"}
    result = validate_admission_packet(packet)
    assert not result["ok"]
    assert any(v["reason_code"] == REASON_MISSING_PROOF for v in result["violations"])


def test_cl04_missing_run_id_blocks() -> None:
    packet = {"admission_class": "non_mutating_query", "trace_id": "t1"}
    result = validate_admission_packet(packet)
    assert not result["ok"]
    assert any(
        v["reason_code"] == REASON_MISSING_FIELD and v.get("field") == "run_id"
        for v in result["violations"]
    )


def test_cl04_validator_rejects_non_mapping() -> None:
    with pytest.raises(AdmissionMinimalityError):
        validate_admission_packet(["not a packet"])  # type: ignore[arg-type]


def test_cl04_allowed_admission_classes_are_bounded() -> None:
    assert "repo_mutation" in ALLOWED_ADMISSION_CLASSES
    assert "non_mutating_query" in ALLOWED_ADMISSION_CLASSES
    assert len(ALLOWED_ADMISSION_CLASSES) >= 3


# --- CL-05 red team: PQX entry without admission ------------------------


def test_cl05_empty_packet_at_pqx_blocks_with_bypass_attempt() -> None:
    result = detect_admission_bypass({}, downstream_stage="PQX")
    assert not result["ok"]
    assert result["primary_reason"] == REASON_BYPASS_ATTEMPT


def test_cl05_repo_mutation_without_proof_at_pqx_blocks_with_bypass_attempt() -> None:
    packet = {"admission_class": "repo_mutation", "trace_id": "t1", "run_id": "r1"}
    result = detect_admission_bypass(packet, downstream_stage="PQX")
    assert not result["ok"]
    assert result["primary_reason"] == REASON_BYPASS_ATTEMPT
    # Supporting reason preserved
    assert any(
        v.get("supporting_reason") == REASON_MISSING_PROOF for v in result["violations"]
    )


# --- CL-06 fix pass ------------------------------------------------------


def test_cl06_valid_admission_packet_does_not_trigger_bypass() -> None:
    packet = build_minimal_admission_packet(
        admission_class="repo_mutation",
        trace_id="t1",
        run_id="r1",
        aex_admission_ref="adm-1",
    )
    result = detect_admission_bypass(packet, downstream_stage="PQX")
    assert result["ok"]


def test_cl06_unknown_class_at_pqx_still_blocks() -> None:
    packet = {"admission_class": "freeform", "trace_id": "t1", "run_id": "r1"}
    result = detect_admission_bypass(packet, downstream_stage="PQX")
    assert not result["ok"]
    assert result["primary_reason"] == REASON_BYPASS_ATTEMPT
