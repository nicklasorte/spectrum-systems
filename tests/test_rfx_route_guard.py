"""Tests for RFX route guard — LOOP-01 through LOOP-03.

Covers:
  LOOP-01: phase_label: RFX in TLC route artifacts + AEX admission linkage
  LOOP-02: direct PQX without AEX/TLC lineage fails closed
  LOOP-03: missing EVL or TPA evidence blocks CDE/SEL progression

Also validates:
  - RFX roadmap hard gate references PRA and POL
  - GOV certification checklist includes PRA and POL
  - Red-team bypass vectors each produce deterministic fail-closed results
"""
from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.rfx_route_guard import (
    RFXRouteGuardError,
    assert_rfx_aex_admission_present,
    assert_rfx_evl_tpa_evidence_present,
    assert_rfx_pqx_lineage_present,
    build_rfx_tlc_route_artifact,
)

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_FULL_RFX_PATH = ["AEX", "RIL", "FRE", "PQX", "EVL", "TPA", "CDE", "SEL", "GOV"]

_VALID_ADMISSION = {
    "admission_id": "aex-rfx-001",
    "admission_status": "accepted",
    "execution_type": "repo_write",
}

_VALID_HANDOFF = {
    "handoff_id": "tlc-handoff-rfx-001",
    "handoff_status": "accepted",
    "target_subsystems": ["TPA", "PQX"],
}

_VALID_EVL = {
    "evaluation_status": "pass",
    "eval_id": "evl-rfx-001",
}

_VALID_TPA = {
    "discipline_status": "accepted",
    "tpa_decision_id": "tpa-rfx-001",
}


@pytest.fixture
def valid_route() -> dict:
    return build_rfx_tlc_route_artifact(
        run_id="rfx-run-001",
        trace_id="trace-rfx-001",
        aex_admission_id="aex-rfx-001",
        intended_path=_FULL_RFX_PATH,
        created_at="2026-04-25T00:00:00Z",
    )


@pytest.fixture
def rfx_roadmap_text() -> str:
    path = Path(__file__).resolve().parents[1] / "docs" / "roadmaps" / "rfx_cross_system_roadmap.md"
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# LOOP-01: phase_label: RFX in TLC route artifacts
# ---------------------------------------------------------------------------

def test_rfx_route_artifact_has_phase_label_rfx(valid_route: dict) -> None:
    assert valid_route["phase_label"] == "RFX"


def test_rfx_route_artifact_artifact_type(valid_route: dict) -> None:
    assert valid_route["artifact_type"] == "rfx_tlc_route_artifact"


def test_rfx_route_artifact_includes_required_overlays(valid_route: dict) -> None:
    assert set(valid_route["overlays"]) == {"REP", "LIN", "OBS", "SLO"}


def test_rfx_route_artifact_carries_aex_admission_ref(valid_route: dict) -> None:
    assert valid_route["aex_admission_ref"] == "build_admission_record:aex-rfx-001"


def test_rfx_route_artifact_carries_intended_path(valid_route: dict) -> None:
    assert valid_route["intended_path"] == _FULL_RFX_PATH


def test_rfx_route_artifact_deterministic() -> None:
    a = build_rfx_tlc_route_artifact(
        run_id="rfx-run-det",
        trace_id="trace-det",
        aex_admission_id="aex-det-001",
        intended_path=_FULL_RFX_PATH,
        created_at="2026-04-25T00:00:00Z",
    )
    b = build_rfx_tlc_route_artifact(
        run_id="rfx-run-det",
        trace_id="trace-det",
        aex_admission_id="aex-det-001",
        intended_path=_FULL_RFX_PATH,
        created_at="2026-04-25T00:00:00Z",
    )
    assert a == b


def test_rfx_route_artifact_missing_aex_admission_id_fails_closed() -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_route_missing_aex_admission_id"):
        build_rfx_tlc_route_artifact(
            run_id="rfx-run-001",
            trace_id="trace-rfx-001",
            aex_admission_id="",
            intended_path=_FULL_RFX_PATH,
            created_at="2026-04-25T00:00:00Z",
        )


def test_rfx_route_artifact_invalid_path_step_fails_closed() -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_route_invalid_path"):
        build_rfx_tlc_route_artifact(
            run_id="rfx-run-001",
            trace_id="trace-rfx-001",
            aex_admission_id="aex-rfx-001",
            intended_path=["AEX", "UNKNOWN_SYSTEM", "PQX"],
            created_at="2026-04-25T00:00:00Z",
        )


# ---------------------------------------------------------------------------
# LOOP-01 / LOOP-02: AEX admission guard
# ---------------------------------------------------------------------------

def test_missing_aex_admission_blocks_repo_mutating_rfx(valid_route: dict) -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_missing_aex_admission"):
        assert_rfx_aex_admission_present(
            route_artifact=valid_route,
            build_admission_record=None,
        )


def test_empty_aex_admission_record_blocks_rfx(valid_route: dict) -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_missing_aex_admission"):
        assert_rfx_aex_admission_present(
            route_artifact=valid_route,
            build_admission_record={},
        )


def test_admission_missing_admission_id_blocks_rfx(valid_route: dict) -> None:
    incomplete = {"admission_status": "accepted"}
    with pytest.raises(RFXRouteGuardError, match="rfx_missing_aex_admission"):
        assert_rfx_aex_admission_present(
            route_artifact=valid_route,
            build_admission_record=incomplete,
        )


def test_rejected_aex_admission_blocks_rfx_execution(valid_route: dict) -> None:
    rejected = {**_VALID_ADMISSION, "admission_status": "rejected"}
    with pytest.raises(RFXRouteGuardError, match="rfx_admission_not_accepted"):
        assert_rfx_aex_admission_present(
            route_artifact=valid_route,
            build_admission_record=rejected,
        )


def test_mismatched_admission_ref_blocks_rfx(valid_route: dict) -> None:
    wrong_id = {**_VALID_ADMISSION, "admission_id": "aex-other-999"}
    with pytest.raises(RFXRouteGuardError, match="rfx_admission_ref_mismatch"):
        assert_rfx_aex_admission_present(
            route_artifact=valid_route,
            build_admission_record=wrong_id,
        )


def test_valid_aex_admission_passes(valid_route: dict) -> None:
    # Must not raise
    assert_rfx_aex_admission_present(
        route_artifact=valid_route,
        build_admission_record=_VALID_ADMISSION,
    )


# ---------------------------------------------------------------------------
# LOOP-02: TLC route lineage / direct PQX guard
# ---------------------------------------------------------------------------

def test_missing_tlc_route_artifact_blocks_pqx() -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_pqx_direct_invocation_blocked"):
        assert_rfx_pqx_lineage_present(
            route_artifact=None,
            tlc_handoff_record=_VALID_HANDOFF,
        )


def test_non_rfx_phase_label_blocks_pqx() -> None:
    non_rfx = {"phase_label": "OTHER", "artifact_type": "rfx_tlc_route_artifact"}
    with pytest.raises(RFXRouteGuardError, match="rfx_pqx_direct_invocation_blocked"):
        assert_rfx_pqx_lineage_present(
            route_artifact=non_rfx,
            tlc_handoff_record=_VALID_HANDOFF,
        )


def test_missing_tlc_handoff_record_blocks_pqx(valid_route: dict) -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_pqx_direct_invocation_blocked"):
        assert_rfx_pqx_lineage_present(
            route_artifact=valid_route,
            tlc_handoff_record=None,
        )


def test_empty_tlc_handoff_record_blocks_pqx(valid_route: dict) -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_pqx_direct_invocation_blocked"):
        assert_rfx_pqx_lineage_present(
            route_artifact=valid_route,
            tlc_handoff_record={},
        )


def test_pending_tlc_handoff_blocks_pqx(valid_route: dict) -> None:
    pending = {**_VALID_HANDOFF, "handoff_status": "pending"}
    with pytest.raises(RFXRouteGuardError, match="rfx_pqx_direct_invocation_blocked"):
        assert_rfx_pqx_lineage_present(
            route_artifact=valid_route,
            tlc_handoff_record=pending,
        )


def test_rejected_tlc_handoff_blocks_pqx(valid_route: dict) -> None:
    rejected = {**_VALID_HANDOFF, "handoff_status": "rejected"}
    with pytest.raises(RFXRouteGuardError, match="rfx_pqx_direct_invocation_blocked"):
        assert_rfx_pqx_lineage_present(
            route_artifact=valid_route,
            tlc_handoff_record=rejected,
        )


def test_valid_tlc_lineage_passes(valid_route: dict) -> None:
    # Must not raise
    assert_rfx_pqx_lineage_present(
        route_artifact=valid_route,
        tlc_handoff_record=_VALID_HANDOFF,
    )


# ---------------------------------------------------------------------------
# LOOP-03: EVL + TPA evidence gate before CDE/SEL progression
# ---------------------------------------------------------------------------

def test_missing_evl_evidence_blocks_cde_sel_progression() -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_missing_evl_evidence"):
        assert_rfx_evl_tpa_evidence_present(
            evl_evidence=None,
            tpa_evidence=_VALID_TPA,
        )


def test_empty_evl_evidence_blocks_cde_sel_progression() -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_missing_evl_evidence"):
        assert_rfx_evl_tpa_evidence_present(
            evl_evidence={},
            tpa_evidence=_VALID_TPA,
        )


def test_failing_evl_status_blocks_cde_sel_progression() -> None:
    failing = {**_VALID_EVL, "evaluation_status": "fail"}
    with pytest.raises(RFXRouteGuardError, match="rfx_evl_evidence_not_passing"):
        assert_rfx_evl_tpa_evidence_present(
            evl_evidence=failing,
            tpa_evidence=_VALID_TPA,
        )


def test_missing_tpa_evidence_blocks_cde_sel_progression() -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_missing_tpa_evidence"):
        assert_rfx_evl_tpa_evidence_present(
            evl_evidence=_VALID_EVL,
            tpa_evidence=None,
        )


def test_empty_tpa_evidence_blocks_cde_sel_progression() -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_missing_tpa_evidence"):
        assert_rfx_evl_tpa_evidence_present(
            evl_evidence=_VALID_EVL,
            tpa_evidence={},
        )


def test_blocked_tpa_discipline_status_blocks_cde_sel_progression() -> None:
    blocked = {**_VALID_TPA, "discipline_status": "blocked"}
    with pytest.raises(RFXRouteGuardError, match="rfx_tpa_evidence_not_accepted"):
        assert_rfx_evl_tpa_evidence_present(
            evl_evidence=_VALID_EVL,
            tpa_evidence=blocked,
        )


def test_both_evl_and_tpa_missing_raises_combined_reasons() -> None:
    with pytest.raises(RFXRouteGuardError) as exc_info:
        assert_rfx_evl_tpa_evidence_present(evl_evidence=None, tpa_evidence=None)
    msg = str(exc_info.value)
    assert "rfx_missing_evl_evidence" in msg
    assert "rfx_missing_tpa_evidence" in msg


def test_conditional_pass_evl_passes() -> None:
    conditional_evl = {**_VALID_EVL, "evaluation_status": "conditional_pass"}
    # Must not raise
    assert_rfx_evl_tpa_evidence_present(
        evl_evidence=conditional_evl,
        tpa_evidence=_VALID_TPA,
    )


def test_conditional_tpa_passes() -> None:
    conditional_tpa = {**_VALID_TPA, "discipline_status": "conditional"}
    # Must not raise
    assert_rfx_evl_tpa_evidence_present(
        evl_evidence=_VALID_EVL,
        tpa_evidence=conditional_tpa,
    )


def test_valid_evl_and_tpa_passes() -> None:
    # Must not raise
    assert_rfx_evl_tpa_evidence_present(
        evl_evidence=_VALID_EVL,
        tpa_evidence=_VALID_TPA,
    )


# ---------------------------------------------------------------------------
# Roadmap hard gate: PRA and POL presence
# ---------------------------------------------------------------------------

def test_rfx_roadmap_hard_gate_references_pra(rfx_roadmap_text: str) -> None:
    assert "PRA" in rfx_roadmap_text, "RFX roadmap GOV hard gate must reference PRA"


def test_rfx_roadmap_hard_gate_references_pol(rfx_roadmap_text: str) -> None:
    assert "POL" in rfx_roadmap_text, "RFX roadmap GOV hard gate must reference POL"


def test_rfx_roadmap_loop06_includes_pra(rfx_roadmap_text: str) -> None:
    # Match the row that *starts* the LOOP-06 table entry (begins with "| LOOP-06")
    loop06_line = next(
        (line for line in rfx_roadmap_text.splitlines() if line.lstrip().startswith("| LOOP-06")), None
    )
    assert loop06_line is not None, "LOOP-06 row must be present in roadmap table"
    assert "PRA" in loop06_line, "LOOP-06 row must reference PRA in its certification requirements"


def test_rfx_roadmap_loop06_includes_pol(rfx_roadmap_text: str) -> None:
    loop06_line = next(
        (line for line in rfx_roadmap_text.splitlines() if line.lstrip().startswith("| LOOP-06")), None
    )
    assert loop06_line is not None, "LOOP-06 row must be present in roadmap table"
    assert "POL" in loop06_line, "LOOP-06 row must reference POL in its certification requirements"


def test_rfx_roadmap_promotion_checklist_includes_pra(rfx_roadmap_text: str) -> None:
    assert "PRA promotion-readiness artifact" in rfx_roadmap_text, (
        "Promotion/Certification Hard Gates section must include PRA promotion-readiness artifact"
    )


def test_rfx_roadmap_promotion_checklist_includes_pol(rfx_roadmap_text: str) -> None:
    assert "POL policy registry" in rfx_roadmap_text, (
        "Promotion/Certification Hard Gates section must include POL policy posture requirement"
    )


def test_rfx_roadmap_is_non_owner_phase_label(rfx_roadmap_text: str) -> None:
    assert "non-owning" in rfx_roadmap_text or "phase label" in rfx_roadmap_text, (
        "RFX roadmap must declare RFX as a phase label, not a system owner"
    )
    assert "not a new system" in rfx_roadmap_text or "phase label" in rfx_roadmap_text


# ---------------------------------------------------------------------------
# Red-team bypass verification
# ---------------------------------------------------------------------------

def test_redteam_gov_without_pra_fails_closed() -> None:
    """RT-bypass: GOV without PRA — missing EVL/TPA upstream of PRA must fail closed."""
    with pytest.raises(RFXRouteGuardError, match="rfx_missing_evl_evidence|rfx_missing_tpa_evidence"):
        assert_rfx_evl_tpa_evidence_present(evl_evidence=None, tpa_evidence=None)


def test_redteam_gov_without_pol_fails_closed() -> None:
    """RT-bypass: GOV without POL — blocked TPA (policy adjudication) must fail closed."""
    blocked_tpa = {**_VALID_TPA, "discipline_status": "blocked"}
    with pytest.raises(RFXRouteGuardError, match="rfx_tpa_evidence_not_accepted"):
        assert_rfx_evl_tpa_evidence_present(evl_evidence=_VALID_EVL, tpa_evidence=blocked_tpa)


def test_redteam_direct_pqx_without_aex_tlc_fails_closed() -> None:
    """RT-bypass: direct PQX without AEX/TLC lineage must fail closed."""
    with pytest.raises(RFXRouteGuardError, match="rfx_pqx_direct_invocation_blocked"):
        assert_rfx_pqx_lineage_present(route_artifact=None, tlc_handoff_record=None)


def test_redteam_cde_sel_without_evl_fails_closed() -> None:
    """RT-bypass: CDE/SEL without EVL evidence must fail closed."""
    with pytest.raises(RFXRouteGuardError, match="rfx_missing_evl_evidence"):
        assert_rfx_evl_tpa_evidence_present(evl_evidence=None, tpa_evidence=_VALID_TPA)


def test_redteam_cde_sel_without_tpa_fails_closed() -> None:
    """RT-bypass: CDE/SEL without TPA evidence must fail closed."""
    with pytest.raises(RFXRouteGuardError, match="rfx_missing_tpa_evidence"):
        assert_rfx_evl_tpa_evidence_present(evl_evidence=_VALID_EVL, tpa_evidence=None)


def test_redteam_pqx_with_wrong_phase_label_fails_closed() -> None:
    """RT-bypass: PQX invoked with a non-RFX route artifact must fail closed."""
    wrong_label = {"phase_label": "UNKNOWN", "artifact_type": "rfx_tlc_route_artifact"}
    with pytest.raises(RFXRouteGuardError, match="rfx_pqx_direct_invocation_blocked"):
        assert_rfx_pqx_lineage_present(route_artifact=wrong_label, tlc_handoff_record=_VALID_HANDOFF)
