from __future__ import annotations

from spectrum_systems.governance.manifest_validator import validate_manifest_completeness


def _base_manifest() -> dict:
    return {
        "contracts": [
            {
                "artifact_type": "pqx_slice_execution_record",
                "artifact_class": "governance",
                "schema_path": "contracts/schemas/pqx_slice_execution_record.schema.json",
                "example_path": "contracts/examples/pqx_slice_execution_record.json",
                "intended_consumers": ["spectrum-systems"],
            }
        ]
    }


def test_missing_artifact_class_fails() -> None:
    manifest = _base_manifest()
    manifest["contracts"][0].pop("artifact_class")

    result = validate_manifest_completeness(manifest)

    assert result["valid"] is False
    assert "contracts[0].artifact_class" in result["missing_fields"]


def test_null_field_fails() -> None:
    manifest = _base_manifest()
    manifest["contracts"][0]["schema_path"] = None

    result = validate_manifest_completeness(manifest)

    assert result["valid"] is False
    assert "contracts[0].schema_path" in result["missing_fields"]


def test_invalid_artifact_class_fails() -> None:
    manifest = _base_manifest()
    manifest["contracts"][0]["artifact_class"] = "invalid_class"

    result = validate_manifest_completeness(manifest)

    assert result["valid"] is False
    assert any(entry["field"] == "artifact_class" for entry in result["invalid_entries"])


def test_valid_manifest_passes() -> None:
    result = validate_manifest_completeness(_base_manifest())

    assert result["valid"] is True
    assert result["errors"] == []
    assert result["missing_fields"] == []
    assert result["invalid_entries"] == []
