from __future__ import annotations


def validate_met_gate(state: dict) -> dict:
    if state.get("fix_integrity_proof_valid"):
        return {"ok": True, "reason_codes": []}
    return {"ok": False, "reason_codes": ["met_requires_fix_integrity_proof"]}
