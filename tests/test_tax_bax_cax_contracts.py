from spectrum_systems.contracts import load_example, validate_artifact


def test_tax_bax_cax_contract_examples_validate() -> None:
    for name in (
        "termination_policy",
        "termination_signal_record",
        "termination_decision",
        "termination_audit_record",
        "system_budget_policy",
        "system_budget_status_v2",
        "budget_consumption_record",
        "budget_control_decision",
        "control_arbitration_policy",
        "control_arbitration_record",
        "control_arbitration_reason_bundle",
        "cde_arbitration_input_bundle",
    ):
        validate_artifact(load_example(name), name)
