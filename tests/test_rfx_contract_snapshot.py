from spectrum_systems.modules.runtime.rfx_contract_snapshot import compare_rfx_contract_snapshot


def test_rt_n05_contract_drift_without_migration_fails_then_revalidate():
    current = [{"module": "m", "artifact_type": "new", "fields": ["a"], "reason_codes": ["r1"]}]
    manifest = {"contracts": {"m": {"artifact_type": "old", "fields": ["a", "b"], "reason_codes": ["r1", "r2"]}}}

    bad = compare_rfx_contract_snapshot(current=current, manifest=manifest, migration_note=None)
    assert "rfx_contract_migration_missing" in bad["reason_codes_emitted"]

    fixed = compare_rfx_contract_snapshot(current=current, manifest=manifest, migration_note="v2 migration recorded")
    assert "rfx_contract_migration_missing" not in fixed["reason_codes_emitted"]
