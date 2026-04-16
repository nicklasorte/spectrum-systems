import copy

import pytest

from spectrum_systems.contracts import load_example, validate_artifact


MAL_CONTRACTS = (
    "prm_step_template_registry_record",
    "prm_prompt_minimalism_profile",
    "prm_owner_scope_expansion_record",
    "prm_authority_language_scrubber_result",
    "rdx_prompt_to_plan_record",
    "rdx_step_render_record",
    "rdx_change_budget_record",
    "rdx_narrowest_owner_resolution_record",
    "tlc_review_fix_cycle_record",
    "tlc_validation_ladder_result",
    "tlc_rerun_cycle_record",
    "ril_review_type_selection_record",
    "ril_red_team_package_record",
    "fre_fix_compilation_record",
    "fre_fix_pack_record",
    "con_composition_only_result",
    "cde_review_completion_decision",
    "cde_fix_completion_decision",
    "ril_prompt_minimalism_red_team_report",
    "fre_fix_pack_m1",
    "final_minimal_prompt_scenario",
    "final_auto_review_fix_scenario",
    "final_rerun_report",
)


def test_mal_001_contract_examples_validate() -> None:
    for contract in MAL_CONTRACTS:
        validate_artifact(load_example(contract), contract)


def test_prm_prompt_minimalism_profile_rejects_verbose_prompt_fields() -> None:
    profile = copy.deepcopy(load_example("prm_prompt_minimalism_profile"))
    profile["sequencing"] = ["manual"]
    with pytest.raises(Exception):
        validate_artifact(profile, "prm_prompt_minimalism_profile")


def test_tlc_validation_ladder_enforces_required_order() -> None:
    record = copy.deepcopy(load_example("tlc_validation_ladder_result"))
    record["executed_order"] = ["contracts", "registry", "owner_tests", "integration"]
    with pytest.raises(Exception):
        validate_artifact(record, "tlc_validation_ladder_result")
