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
        ):
            instance = load_example(name)
            validate_artifact(instance, name)

    def test_enforcement_result_example_validates(self) -> None:
        instance = load_example("enforcement_result")
        validate_artifact(instance, "enforcement_result")


    def test_replay_result_example_validates(self) -> None:
        instance = load_example("replay_result")
        validate_artifact(instance, "replay_result")

    def test_prompt_queue_review_findings_example_validates(self) -> None:
        instance = load_example("prompt_queue_review_findings")
        validate_artifact(instance, "prompt_queue_review_findings")


    def test_prompt_queue_repair_prompt_example_validates(self) -> None:
        instance = load_example("prompt_queue_repair_prompt")
        validate_artifact(instance, "prompt_queue_repair_prompt")

    def test_prompt_queue_review_trigger_example_validates(self) -> None:
        instance = load_example("prompt_queue_review_trigger")
        validate_artifact(instance, "prompt_queue_review_trigger")

    def test_prompt_queue_review_invocation_result_example_validates(self) -> None:
        instance = load_example("prompt_queue_review_invocation_result")
        validate_artifact(instance, "prompt_queue_review_invocation_result")




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

    def test_risk_register_category_enum_covers_required_categories(self) -> None:
        schema = load_schema("risk_register")
        categories = schema["$defs"]["risk"]["properties"]["category"]["enum"]
        self.assertEqual(
            categories,
            ["technical", "data", "schedule", "stakeholder", "process_legal", "coordination", "narrative"],
        )


if __name__ == "__main__":
    unittest.main()
