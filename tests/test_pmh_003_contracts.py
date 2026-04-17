from spectrum_systems.contracts import load_example, validate_artifact


PMH_003_CONTRACTS = (
    "final_pm11_full_stack_parity_validation_report",
    "pmh_003_delivery_report",
)


def test_pmh_003_contract_examples_validate() -> None:
    for artifact_type in PMH_003_CONTRACTS:
        validate_artifact(load_example(artifact_type), artifact_type)
