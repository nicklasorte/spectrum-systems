from __future__ import annotations


def validate_pre_h01_gate(state: dict) -> dict:
    reasons: list[str] = []
    if not state.get("blf_01_complete"):
        reasons.append("h01_requires_blf_01_complete")
    if not state.get("rfx_04_merged"):
        reasons.append("h01_requires_rfx_04_merged")
    if not state.get("roadmap_sync_valid"):
        reasons.append("h01_requires_roadmap_sync")

    return {"ok": not reasons, "reason_codes": sorted(set(reasons))}
