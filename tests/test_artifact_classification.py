import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from spectrum_systems.contracts.artifact_class_taxonomy import load_allowed_artifact_classes


REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_CLASSES = set(load_allowed_artifact_classes())
KEY_CONTRACT_CLASSES = {
    "meeting_minutes_record": "coordination",
    "reviewer_comment_set": "review",
    "comment_resolution_matrix": "review",
    "comment_resolution_matrix_spreadsheet_contract": "review",
    "working_paper_input": "work",
    "program_brief": "coordination",
    "study_readiness_assessment": "coordination",
    "next_best_action_memo": "coordination",
    "stage_contract": "governance",
}


class ArtifactClassificationTests(unittest.TestCase):
    def test_standard_doc_exists(self) -> None:
        standard_path = REPO_ROOT / "docs" / "artifact-classification-standard.md"
        self.assertTrue(standard_path.exists(), "artifact-classification standard document is missing")

    def test_registry_validates_against_schema(self) -> None:
        registry_path = REPO_ROOT / "contracts" / "artifact-class-registry.json"
        schema_path = REPO_ROOT / "contracts" / "schemas" / "artifact_class_registry.schema.json"
        registry = json.loads(registry_path.read_text())
        schema = json.loads(schema_path.read_text())
        Draft202012Validator(schema).validate(registry)

    def test_manifest_artifact_classes_are_allowed(self) -> None:
        manifest_path = REPO_ROOT / "contracts" / "standards-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        for contract in manifest["contracts"]:
            artifact_class = contract.get("artifact_class")
            self.assertIsNotNone(artifact_class, f"artifact_class missing for {contract['artifact_type']}")
            self.assertIn(artifact_class, ALLOWED_CLASSES, f"Unexpected class for {contract['artifact_type']}")

    def test_key_contracts_have_expected_classes(self) -> None:
        manifest_path = REPO_ROOT / "contracts" / "standards-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest_map = {entry["artifact_type"]: entry for entry in manifest["contracts"]}
        for contract_type, expected_class in KEY_CONTRACT_CLASSES.items():
            self.assertIn(contract_type, manifest_map, f"{contract_type} missing from standards manifest")
            self.assertEqual(
                manifest_map[contract_type].get("artifact_class"),
                expected_class,
                f"{contract_type} has incorrect artifact_class",
            )


if __name__ == "__main__":
    unittest.main()
