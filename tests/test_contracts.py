import csv
import sys
from pathlib import Path
import unittest

from jsonschema.exceptions import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import (  # noqa: E402
    list_supported_contracts,
    load_example,
    load_schema,
    validate_artifact,
)


CONTRACTS = [
    "working_paper_input",
    "reviewer_comment_set",
    "comment_resolution_matrix",
    "meeting_agenda_contract",
    "meeting_minutes_record",
    "comment_resolution_matrix_spreadsheet_contract",
    "pdf_anchored_docx_comment_injection_contract",
    "standards_manifest",
    "provenance_record",
    "program_brief",
    "study_readiness_assessment",
    "next_best_action_memo",
    "decision_log",
    "risk_register",
    "assumption_register",
    "milestone_plan",
]

BASE_DIR = Path(__file__).resolve().parents[1]
CRM_SPREADSHEET_HEADERS = [
    "Comment Number",
    "Reviewer Initials",
    "Agency",
    "Report Version",
    "Section",
    "Page",
    "Line",
    "Comment Type: Editorial/Grammar, Clarification, Technical",
    "Agency Notes",
    "Agency Suggested Text Change",
    "NTIA Comments",
    "Comment Disposition",
    "Resolution",
]
CRM_SPREADSHEET_KEYS = [
    "comment_number",
    "reviewer_initials",
    "agency",
    "report_version",
    "section",
    "page",
    "line",
    "comment_type",
    "agency_notes",
    "agency_suggested_text_change",
    "ntia_comments",
    "comment_disposition",
    "resolution",
]


class ContractSchemaTests(unittest.TestCase):
    def test_example_payloads_validate(self) -> None:
        for name in CONTRACTS:
            instance = load_example(name)
            validate_artifact(instance, name)

    def test_missing_required_field_fails(self) -> None:
        instance = load_example("working_paper_input")
        instance.pop("schema_version", None)
        with self.assertRaises(ValidationError):
            validate_artifact(instance, "working_paper_input")

    def test_version_fields_present_in_examples(self) -> None:
        for name in CONTRACTS:
            instance = load_example(name)
            for field in ("artifact_version", "schema_version", "standards_version"):
                self.assertIn(field, instance, f"{field} missing in {name}")

    def test_contract_registry_lists_expected(self) -> None:
        discovered = list_supported_contracts()
        for name in CONTRACTS:
            self.assertIn(name, discovered)

    def test_spreadsheet_contract_has_canonical_headers_and_mapping(self) -> None:
        instance = load_example("comment_resolution_matrix_spreadsheet_contract")
        self.assertEqual(instance["ordered_headers"], CRM_SPREADSHEET_HEADERS)
        self.assertEqual(list(instance["normalized_key_map"].keys()), CRM_SPREADSHEET_HEADERS)
        self.assertEqual(list(instance["normalized_key_map"].values()), CRM_SPREADSHEET_KEYS)

        headers = instance["headers"]
        self.assertEqual([entry["header"] for entry in headers], CRM_SPREADSHEET_HEADERS)
        for entry in headers:
            header = entry["header"]
            self.assertEqual(instance["normalized_key_map"][header], entry["normalized_key"])

    def test_spreadsheet_example_csv_preserves_header_order(self) -> None:
        csv_path = BASE_DIR / "examples" / "comment-resolution-matrix-spreadsheet.csv"
        with csv_path.open(newline="") as handle:
            reader = csv.reader(handle)
            header_row = next(reader)
        self.assertEqual(header_row, CRM_SPREADSHEET_HEADERS)



    def test_bbc_eval_governance_examples_validate(self) -> None:
        for name in (
            "eval_case",
            "eval_dataset",
            "eval_admission_policy",
            "eval_canonicalization_policy",
            "eval_registry_snapshot",
            "eval_coverage_summary",
            "eval_slice_summary",
        ):
            instance = load_example(name)
            validate_artifact(instance, name)




    def test_eval_governance_release_gate_examples_validate(self) -> None:
        for name in (
            "evaluation_ci_gate_result",
            "evaluation_release_record",
            "evaluation_control_chaos_summary",
            "control_loop_certification_pack",
        ):
            instance = load_example(name)
            validate_artifact(instance, name)

    def test_roadmap_eligibility_contract_examples_validate(self) -> None:
        for name in ("governed_roadmap_artifact", "roadmap_eligibility_artifact", "pqx_strategy_status_artifact"):
            instance = load_example(name)
            validate_artifact(instance, name)



    def test_program_layer_contract_examples_validate(self) -> None:
        for name in (
            "program_artifact",
            "program_progress",
            "program_constraint_signal",
            "program_roadmap_alignment_result",
            "program_drift_signal",
            "program_feedback_record",
        ):
            instance = load_example(name)
            validate_artifact(instance, name)

    def test_enforcement_result_example_validates(self) -> None:
        instance = load_example("enforcement_result")
        validate_artifact(instance, "enforcement_result")


    def test_replay_result_example_validates(self) -> None:
        instance = load_example("replay_result")
        validate_artifact(instance, "replay_result")

    def test_drift_and_baseline_gate_contract_examples_validate(self) -> None:
        for name in ("drift_detection_result", "baseline_gate_decision", "baseline_gate_policy"):
            instance = load_example(name)
            validate_artifact(instance, name)

    def test_prompt_queue_review_findings_example_validates(self) -> None:
        instance = load_example("prompt_queue_review_findings")
        validate_artifact(instance, "prompt_queue_review_findings")


    def test_prompt_queue_repair_prompt_example_validates(self) -> None:
        instance = load_example("prompt_queue_repair_prompt")
        validate_artifact(instance, "prompt_queue_repair_prompt")


    def test_review_governance_observability_contract_examples_validate(self) -> None:
        for name in (
            "review_request",
            "review_failure_summary",
            "review_hotspot_report",
            "review_eval_generation_report",
        ):
            instance = load_example(name)
            validate_artifact(instance, name)

    def test_prompt_queue_review_trigger_example_validates(self) -> None:
        instance = load_example("prompt_queue_review_trigger")
        validate_artifact(instance, "prompt_queue_review_trigger")

    def test_prompt_queue_review_invocation_result_example_validates(self) -> None:
        instance = load_example("prompt_queue_review_invocation_result")
        validate_artifact(instance, "prompt_queue_review_invocation_result")




    def test_prompt_queue_step_decision_example_validates(self) -> None:
        instance = load_example("prompt_queue_step_decision")
        validate_artifact(instance, "prompt_queue_step_decision")

    def test_prompt_queue_replay_resume_examples_validate(self) -> None:
        for name in ("prompt_queue_resume_checkpoint", "prompt_queue_replay_record"):
            instance = load_example(name)
            validate_artifact(instance, name)

    def test_prompt_queue_certification_record_example_validates(self) -> None:
        instance = load_example("prompt_queue_certification_record")
        validate_artifact(instance, "prompt_queue_certification_record")



    def test_pqx_bundle_execution_record_example_validates(self) -> None:
        instance = load_example("pqx_bundle_execution_record")
        validate_artifact(instance, "pqx_bundle_execution_record")

    def test_pqx_bundle_state_example_validates(self) -> None:
        instance = load_example("pqx_bundle_state")
        validate_artifact(instance, "pqx_bundle_state")

    def test_pqx_review_result_example_validates(self) -> None:
        instance = load_example("pqx_review_result")
        validate_artifact(instance, "pqx_review_result")

    def test_pqx_triage_plan_record_example_validates(self) -> None:
        instance = load_example("pqx_triage_plan_record")
        validate_artifact(instance, "pqx_triage_plan_record")

    def test_control_surface_gap_result_example_validates(self) -> None:
        instance = load_example("control_surface_gap_result")
        validate_artifact(instance, "control_surface_gap_result")

    def test_control_surface_gap_packet_example_validates(self) -> None:
        instance = load_example("control_surface_gap_packet")
        validate_artifact(instance, "control_surface_gap_packet")

    def test_codex_pqx_task_wrapper_example_validates(self) -> None:
        instance = load_example("codex_pqx_task_wrapper")
        validate_artifact(instance, "codex_pqx_task_wrapper")

    def test_prompt_queue_sequence_run_example_validates(self) -> None:
        instance = load_example("prompt_queue_sequence_run")
        validate_artifact(instance, "prompt_queue_sequence_run")

    def test_pqx_sequential_execution_trace_example_validates(self) -> None:
        instance = load_example("pqx_sequential_execution_trace")
        validate_artifact(instance, "pqx_sequential_execution_trace")

    def test_prompt_queue_audit_bundle_example_validates(self) -> None:
        instance = load_example("prompt_queue_audit_bundle")
        validate_artifact(instance, "prompt_queue_audit_bundle")

    def test_prompt_queue_policy_backtest_report_example_validates(self) -> None:
        instance = load_example("prompt_queue_policy_backtest_report")
        validate_artifact(instance, "prompt_queue_policy_backtest_report")

    def test_pqx_slice_continuation_record_example_validates(self) -> None:
        instance = load_example("pqx_slice_continuation_record")
        validate_artifact(instance, "pqx_slice_continuation_record")

    def test_batch_continuation_record_example_validates(self) -> None:
        instance = load_example("batch_continuation_record")
        validate_artifact(instance, "batch_continuation_record")

    def test_adaptive_execution_policy_review_example_validates(self) -> None:
        instance = load_example("adaptive_execution_policy_review")
        validate_artifact(instance, "adaptive_execution_policy_review")

    def test_system_mvp_validation_report_example_validates(self) -> None:
        instance = load_example("system_mvp_validation_report")
        validate_artifact(instance, "system_mvp_validation_report")

    def test_mvp_20_slice_execution_report_example_validates(self) -> None:
        instance = load_example("mvp_20_slice_execution_report")
        validate_artifact(instance, "mvp_20_slice_execution_report")


    def test_context_pipeline_contract_examples_validate(self) -> None:
        for name in ("context_bundle_v2", "build_report", "next_slice_handoff"):
            instance = load_example(name)
            validate_artifact(instance, name)

    def test_tpa_slice_artifact_example_validates(self) -> None:
        instance = load_example("tpa_slice_artifact")
        validate_artifact(instance, "tpa_slice_artifact")

    def test_pqx_sequence_budget_example_validates(self) -> None:
        instance = load_example("pqx_sequence_budget")
        validate_artifact(instance, "pqx_sequence_budget")

    def test_roadmap_multi_batch_run_result_example_validates(self) -> None:
        instance = load_example("roadmap_multi_batch_run_result")
        validate_artifact(instance, "roadmap_multi_batch_run_result")

    def test_operator_shakeout_contract_examples_validate(self) -> None:
        for name in ("operator_friction_report", "operator_backlog_handoff"):
            instance = load_example(name)
            validate_artifact(instance, name)

    def test_pqx_chain_and_bundle_contract_examples_validate(self) -> None:
        for name in (
            "pqx_chain_certification_record",
            "pqx_bundle_certification_record",
            "pqx_bundle_audit_record",
            "pqx_execution_closure_record",
            "pqx_hard_gate_falsification_record",
        ):
            instance = load_example(name)
            validate_artifact(instance, name)

    def test_contract_impact_artifact_example_validates(self) -> None:
        instance = load_example("contract_impact_artifact")
        validate_artifact(instance, "contract_impact_artifact")

    def test_contract_preflight_result_artifact_example_validates(self) -> None:
        instance = load_example("contract_preflight_result_artifact")
        validate_artifact(instance, "contract_preflight_result_artifact")
        required_context = instance["pqx_required_context_enforcement"]
        assert required_context["status"] in {"allow", "block"}
        assert isinstance(required_context["blocking_reasons"], list)
        assert required_context["authority_state"] in {
            "authoritative_governed_pqx",
            "non_authoritative_direct_run",
            "unknown_pending_execution",
        }
        assert isinstance(required_context["requires_pqx_execution"], bool)
        assert required_context["enforcement_decision"] in {"allow", "block"}

    def test_control_surface_obedience_result_example_validates(self) -> None:
        instance = load_example("control_surface_obedience_result")
        validate_artifact(instance, "control_surface_obedience_result")

    def test_trust_spine_evidence_cohesion_result_example_validates(self) -> None:
        instance = load_example("trust_spine_evidence_cohesion_result")
        validate_artifact(instance, "trust_spine_evidence_cohesion_result")

    def test_execution_change_impact_artifact_example_validates(self) -> None:
        instance = load_example("execution_change_impact_artifact")
        validate_artifact(instance, "execution_change_impact_artifact")

    def test_pqx_g5_contract_examples_validate(self) -> None:
        for name in (
            "pqx_bundle_schedule_decision",
            "pqx_canary_decision_record",
            "pqx_canary_evaluation_record",
            "pqx_judgment_record",
            "pqx_n_slice_validation_record",
        ):
            instance = load_example(name)
            validate_artifact(instance, name)

    def test_judgment_layer_contract_examples_validate(self) -> None:
        for name in (
            "judgment_policy",
            "judgment_record",
            "judgment_application_record",
            "judgment_eval_result",
            "judgment_outcome_label",
            "judgment_calibration_result",
            "judgment_drift_signal",
            "judgment_error_budget_status",
            "judgment_control_escalation_record",
            "judgment_enforcement_action_record",
            "judgment_enforcement_outcome_record",
            "judgment_operator_remediation_record",
            "judgment_remediation_closure_record",
            "judgment_progression_reinstatement_record",
            "judgment_remediation_readiness_status",
            "judgment_reinstatement_readiness_status",
            "judgment_policy_rollout_record",
            "judgment_policy_lifecycle_record",
        ):
            instance = load_example(name)
            validate_artifact(instance, name)

    def test_recovery_bridge_contract_examples_validate(self) -> None:
        for name in (
            "drift_remediation_policy",
            "drift_remediation_artifact",
            "fix_plan_artifact",
        ):
            instance = load_example(name)
            validate_artifact(instance, name)


    def test_prompt_registry_examples_validate(self) -> None:
        for name in ("prompt_registry_entry", "prompt_alias_map", "routing_policy", "routing_decision", "agent_execution_trace"):
            instance = load_example(name)
            validate_artifact(instance, name)

    def test_model_adapter_contract_examples_validate(self) -> None:
        for name in ("ai_model_request", "ai_model_response"):
            instance = load_example(name)
            validate_artifact(instance, name)

    def test_prompt_injection_assessment_example_validates(self) -> None:
        instance = load_example("prompt_injection_assessment")
        validate_artifact(instance, "prompt_injection_assessment")

    def test_multi_pass_generation_record_example_validates(self) -> None:
        instance = load_example("multi_pass_generation_record")
        validate_artifact(instance, "multi_pass_generation_record")

    def test_evidence_binding_record_example_validates(self) -> None:
        instance = load_example("evidence_binding_record")
        validate_artifact(instance, "evidence_binding_record")

    def test_grounding_factcheck_eval_example_validates(self) -> None:
        instance = load_example("grounding_factcheck_eval")
        validate_artifact(instance, "grounding_factcheck_eval")

    def test_replay_execution_record_example_validates(self) -> None:
        instance = load_example("replay_execution_record")
        validate_artifact(instance, "replay_execution_record")

    def test_observability_record_example_validates(self) -> None:
        instance = load_example("observability_record")
        validate_artifact(instance, "observability_record")

    def test_artifact_lineage_example_validates(self) -> None:
        instance = load_example("artifact_lineage")
        validate_artifact(instance, "artifact_lineage")

    def test_grounding_control_decision_example_validates(self) -> None:
        instance = load_example("grounding_control_decision")
        validate_artifact(instance, "grounding_control_decision")

    def test_sre_observability_contract_examples_validate(self) -> None:
        for name in ("service_level_objective", "observability_metrics", "error_budget_policy", "error_budget_status", "alert_trigger_policy", "alert_trigger"):
            instance = load_example(name)
            validate_artifact(instance, name)

    def test_risk_register_category_enum_covers_required_categories(self) -> None:
        schema = load_schema("risk_register")
        categories = schema["$defs"]["risk"]["properties"]["category"]["enum"]
        self.assertEqual(
            categories,
            ["technical", "data", "schedule", "stakeholder", "process_legal", "coordination", "narrative"],
        )


if __name__ == "__main__":
    unittest.main()
