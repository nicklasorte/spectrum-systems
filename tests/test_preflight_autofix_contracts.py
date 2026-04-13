from spectrum_systems.contracts import load_example, validate_artifact


def test_preflight_autofix_contract_examples_validate() -> None:
    for name in (
        "preflight_block_diagnosis_record",
        "preflight_repair_plan_record",
        "preflight_repair_attempt_record",
        "preflight_repair_validation_record",
        "preflight_repair_result_record",
    ):
        validate_artifact(load_example(name), name)
