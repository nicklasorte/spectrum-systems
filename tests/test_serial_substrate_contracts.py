from spectrum_systems.contracts import load_example, validate_artifact


def test_ctx_tlx_jsx_drx_examples_validate() -> None:
    for name in (
        "context_recipe",
        "context_bundle",
        "context_manifest",
        "context_conflict_record",
        "context_preflight_result",
        "tool_registry_entry",
        "tool_contract",
        "tool_output_envelope",
        "tool_permission_profile",
        "tool_dispatch_record",
        "judgment_status_record",
        "judgment_supersession_record",
        "judgment_active_set_record",
        "judgment_conflict_record",
        "judgment_policy_extraction_record",
        "drift_signal_record",
        "drift_response_plan",
        "maintain_cycle_record",
        "invariant_gap_record",
        "eval_expansion_record",
    ):
        validate_artifact(load_example(name), name)
