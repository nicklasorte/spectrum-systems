import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]


class ArtifactEnvelopeTests(unittest.TestCase):
    def test_standard_doc_exists(self) -> None:
        standard_path = REPO_ROOT / "docs" / "artifact-envelope-standard.md"
        self.assertTrue(standard_path.exists(), "artifact-envelope standard document is missing")

    def test_schema_loads(self) -> None:
        schema_path = REPO_ROOT / "contracts" / "schemas" / "artifact_envelope.schema.json"
        schema = json.loads(schema_path.read_text())
        Draft202012Validator.check_schema(schema)

    def test_example_validates(self) -> None:
        schema_path = REPO_ROOT / "contracts" / "schemas" / "artifact_envelope.schema.json"
        example_path = REPO_ROOT / "contracts" / "examples" / "artifact_envelope.example.json"
        schema = json.loads(schema_path.read_text())
        example = json.loads(example_path.read_text())
        Draft202012Validator(schema).validate(example)

    def test_artifact_class_enum_matches_standard(self) -> None:
        schema_path = REPO_ROOT / "contracts" / "schemas" / "artifact_envelope.schema.json"
        registry_path = REPO_ROOT / "contracts" / "artifact-class-registry.json"
        schema = json.loads(schema_path.read_text())
        registry = json.loads(registry_path.read_text())
        schema_classes = set(schema["properties"]["artifact_class"]["enum"])
        registry_classes = {entry["name"] for entry in registry["artifact_classes"]}
        self.assertEqual(schema_classes, registry_classes, "artifact_class enum must match the classification standard")

    def test_lifecycle_stage_enum(self) -> None:
        schema_path = REPO_ROOT / "contracts" / "schemas" / "artifact_envelope.schema.json"
        schema = json.loads(schema_path.read_text())
        lifecycle_enum = set(schema["properties"]["lifecycle_stage"]["enum"])
        self.assertEqual(lifecycle_enum, {"raw", "processed", "final", "fixture"})


if __name__ == "__main__":
    unittest.main()
