from spectrum_systems.contracts import load_example, validate_artifact


RGP02_CONTRACTS = (
    "slice_trend_report",
    "correction_mining_report",
    "canary_analysis_record",
    "canary_rollback_record",
    "freeze_record",
    "queue_governance_record",
    "backpressure_signal",
    "cap_budget_status_record",
    "slo_budget_status_artifact",
    "sec_guardrail_event_record",
    "sec_control_integration_signal",
    "dependency_integrity_report",
    "schema_compatibility_result",
    "translation_artifact",
    "normalized_artifact",
    "test_asset_governance_record",
)


def test_rgp02_examples_validate() -> None:
    for contract in RGP02_CONTRACTS:
        validate_artifact(load_example(contract), contract)


def test_rgp02_contracts_fail_closed_when_required_field_missing() -> None:
    for contract in RGP02_CONTRACTS:
        sample = load_example(contract)
        sample.pop("trace_id", None)
        try:
            validate_artifact(sample, contract)
        except Exception:
            continue
        raise AssertionError(f"{contract} unexpectedly accepted malformed artifact")
