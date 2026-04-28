from __future__ import annotations


def compare_rfx_contract_snapshot(*, current: list[dict], manifest: dict, migration_note: str | None = None) -> dict:
    reason: list[str] = []
    prior = manifest.get("contracts", {})

    for contract in current:
        module = contract.get("module")
        previous = prior.get(module)
        if not previous:
            continue

        if contract.get("artifact_type") != previous.get("artifact_type"):
            reason.append("rfx_contract_snapshot_mismatch")

        removed_fields = set(previous.get("fields", [])) - set(contract.get("fields", []))
        if removed_fields:
            reason.append("rfx_contract_field_removed")

        removed_reasons = set(previous.get("reason_codes", [])) - set(contract.get("reason_codes", []))
        if removed_reasons:
            reason.append("rfx_contract_reason_removed")

    migration_required = bool(reason)
    if migration_required and not (isinstance(migration_note, str) and migration_note.strip()):
        reason.append("rfx_contract_migration_missing")

    return {
        "artifact_type": "rfx_contract_snapshot_result",
        "schema_version": "1.0.0",
        "status": "match" if not reason else "mismatch",
        "reason_codes_emitted": sorted(set(reason)),
        "signals": {
            "contract_drift_count": len(set(reason)),
            "migration_note_present": bool(isinstance(migration_note, str) and migration_note.strip()),
        },
        "manifest": manifest,
    }
