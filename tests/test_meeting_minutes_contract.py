import json
from pathlib import Path

from spectrum_systems.contracts import load_example, load_schema, validate_artifact


REPO_ROOT = Path(__file__).resolve().parents[1]
STANDARDS_MANIFEST = REPO_ROOT / "contracts" / "standards-manifest.json"


def test_meeting_minutes_record_example_validates() -> None:
    example = load_example("meeting_minutes_record")
    validate_artifact(example, "meeting_minutes_record")


def test_meeting_minutes_record_registered_in_manifest() -> None:
    manifest = STANDARDS_MANIFEST.read_text()
    manifest_data = json.loads(manifest)
    contracts = manifest_data.get("contracts", [])
    entry = next((c for c in contracts if c.get("artifact_type") == "meeting_minutes_record"), None)
    assert entry is not None, "meeting_minutes_record missing from standards-manifest"
    assert set(entry.get("intended_consumers", [])) == {
        "meeting-minutes-engine",
        "spectrum-program-advisor",
    }


def test_meeting_minutes_record_schema_loads() -> None:
    schema = load_schema("meeting_minutes_record")
    assert schema["properties"]["artifact_type"]["const"] == "meeting_minutes_record"
    for field in ("meeting_id", "meeting_title", "date", "source_transcript", "provenance"):
        assert field in schema["required"]
