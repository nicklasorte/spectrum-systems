"""RFX flow integration helper — wires LOOP-01..LOOP-06 guards in order.

RFX path (canonical):

    RIL → FRE → PQX → EVL → TPA → CDE
        → assert_rfx_cde_sel_decision_bridge   (LOOP-04)
        → assert_rfx_integrity_bundle          (LOOP-05)
        → assert_rfx_certification_ready       (LOOP-06)
        → SEL enforcement step
        → GOV certification record

This module composes the existing guards as a non-owning phase-label support
helper. It does not introduce or redefine roles; canonical roles are recorded
in ``docs/architecture/system_registry.md``.
"""

from __future__ import annotations

from typing import Any

from spectrum_systems.modules.runtime.rfx_certification_gate import (
    assert_rfx_certification_ready,
)
from spectrum_systems.modules.runtime.rfx_decision_bridge_guard import (
    assert_rfx_cde_sel_decision_bridge,
)
from spectrum_systems.modules.runtime.rfx_integrity_bundle import (
    assert_rfx_integrity_bundle,
)
from spectrum_systems.modules.runtime.rfx_route_guard import (
    assert_rfx_aex_admission_present,
    assert_rfx_evl_tpa_evidence_present,
    assert_rfx_pqx_lineage_present,
)


def assert_rfx_promotion_ready(
    *,
    route_artifact: dict[str, Any] | None,
    build_admission_record: dict[str, Any] | None,
    tlc_handoff_record: dict[str, Any] | None,
    evl: dict[str, Any] | None,
    tpa: dict[str, Any] | None,
    cde: dict[str, Any] | None,
    sel: dict[str, Any] | None,
    lin: dict[str, Any] | None,
    rep: dict[str, Any] | None,
    obs: dict[str, Any] | None,
    slo: dict[str, Any] | None,
    pra: dict[str, Any] | None,
    pol: dict[str, Any] | None,
) -> None:
    """Run all RFX guards in canonical order, fail-closed at the first break.

    LOOP-01..LOOP-03 ensure routing/admission/lineage and EVL+TPA evidence.
    LOOP-04 bridges CDE → SEL. LOOP-05 enforces LIN+REP integrity. LOOP-06
    enforces the GOV certification hard gate including PRA and POL.

    No path may reach GOV certification packaging without passing every guard.
    """
    # LOOP-01 / LOOP-02: AEX admission + TLC route lineage
    assert_rfx_aex_admission_present(
        route_artifact=route_artifact or {},
        build_admission_record=build_admission_record,
    )
    assert_rfx_pqx_lineage_present(
        route_artifact=route_artifact,
        tlc_handoff_record=tlc_handoff_record,
    )

    # LOOP-03: EVL + TPA evidence before CDE/SEL progression
    assert_rfx_evl_tpa_evidence_present(evl_evidence=evl, tpa_evidence=tpa)

    # LOOP-04: CDE → SEL decision bridge
    assert_rfx_cde_sel_decision_bridge(cde_decision=cde, sel_context=sel)

    # LOOP-05: LIN + REP integrity bundle
    assert_rfx_integrity_bundle(lineage_record=lin, replay_record=rep)

    # LOOP-06: GOV certification hard gate (includes PRA + POL)
    assert_rfx_certification_ready(
        evl=evl, tpa=tpa, cde=cde, sel=sel,
        lin=lin, rep=rep, obs=obs, slo=slo,
        pra=pra, pol=pol,
    )


__all__ = ["assert_rfx_promotion_ready"]
