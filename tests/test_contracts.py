import unittest

from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import (
    list_supported_contracts,
    load_example,
    validate_artifact,
)


CONTRACTS = [
    "working_paper_input",
    "reviewer_comment_set",
    "comment_resolution_matrix",
    "standards_manifest",
    "provenance_record",
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


if __name__ == "__main__":
    unittest.main()
