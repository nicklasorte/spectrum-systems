from __future__ import annotations


def validate_hop_gate(state: dict) -> dict:
    reasons: list[str] = []
    if not state.get("met_measurement_exists"):
        reasons.append("hop_requires_met_measurement")
    if not state.get("met_gate_passed"):
        reasons.append("hop_requires_met_gate_pass")
    return {"ok": not reasons, "reason_codes": sorted(set(reasons))}
