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
        example_path = REPO_ROOT / "contracts" / "examples" / "artifact_envelope.json"
        schema = json.loads(schema_path.read_text())
        example = json.loads(example_path.read_text())
        Draft202012Validator(schema).validate(example)

    def test_required_envelope_fields_present(self) -> None:
        schema_path = REPO_ROOT / "contracts" / "schemas" / "artifact_envelope.schema.json"
        schema = json.loads(schema_path.read_text())
        required = set(schema["required"])
        self.assertEqual(required, {"id", "timestamp", "schema_version", "trace_refs"})

    def test_trace_refs_shape_requires_primary_and_related(self) -> None:
        schema_path = REPO_ROOT / "contracts" / "schemas" / "artifact_envelope.schema.json"
        schema = json.loads(schema_path.read_text())
        trace_schema = schema["$defs"]["trace_refs"]
        self.assertEqual(set(trace_schema["required"]), {"primary", "related"})
        self.assertFalse(trace_schema["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
