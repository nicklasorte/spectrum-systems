from __future__ import annotations

from spectrum_systems.modules.runtime.rmp.rmp_hop_gate import validate_hop_gate
from spectrum_systems.modules.runtime.rmp.rmp_met_gate import validate_met_gate
from spectrum_systems.modules.runtime.rmp.rmp_pre_h01_gate import validate_pre_h01_gate
from spectrum_systems.modules.runtime.rmp.rmp_rfx_placement import ensure_rfx_placement


def test_h01_gate_blocks_without_prerequisites() -> None:
    blocked = validate_pre_h01_gate({"blf_01_complete": False, "rfx_04_merged": False, "roadmap_sync_valid": False})
    assert not blocked["ok"]
    assert "h01_requires_blf_01_complete" in blocked["reason_codes"]


def test_met_hop_gates_fail_closed() -> None:
    assert not validate_met_gate({"fix_integrity_proof_valid": False})["ok"]
    assert not validate_hop_gate({"met_measurement_exists": False, "met_gate_passed": False})["ok"]


def test_rfx_placement_inserts_required_loops() -> None:
    base = {"batches": [{"batch_id": "LOOP-08", "depends_on": []}]}
    result = ensure_rfx_placement(base)
    ids = {b["batch_id"] for b in result["roadmap"]["batches"]}
    assert {"LOOP-09", "LOOP-10"}.issubset(ids)
