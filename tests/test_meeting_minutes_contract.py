import json
from pathlib import Path

from spectrum_systems.contracts import load_example, load_schema, validate_artifact


REPO_ROOT = Path(__file__).resolve().parents[1]
STANDARDS_MANIFEST = REPO_ROOT / "contracts" / "standards-manifest.json"
MANIFESTS_DIR = REPO_ROOT / "governance" / "examples" / "manifests"

MEETING_MINUTES_RECORD_CONSUMERS = {"meeting-minutes-engine", "spectrum-program-advisor"}


def test_meeting_minutes_record_example_validates() -> None:
    example = load_example("meeting_minutes_record")
    validate_artifact(example, "meeting_minutes_record")


def test_meeting_minutes_record_registered_in_manifest() -> None:
    manifest = STANDARDS_MANIFEST.read_text()
    manifest_data = json.loads(manifest)
    contracts = manifest_data.get("contracts", [])
    entry = next((c for c in contracts if c.get("artifact_type") == "meeting_minutes_record"), None)
    assert entry is not None, "meeting_minutes_record missing from standards-manifest"
    assert set(entry.get("intended_consumers", [])) == MEETING_MINUTES_RECORD_CONSUMERS


def test_meeting_minutes_record_schema_loads() -> None:
    schema = load_schema("meeting_minutes_record")
    assert schema["properties"]["artifact_type"]["const"] == "meeting_minutes_record"
    for field in ("meeting_id", "meeting_title", "date", "source_transcript", "provenance"):
        assert field in schema["required"]


def _load_governance_manifest(repo_name: str) -> dict:
    path = MANIFESTS_DIR / f"{repo_name}.spectrum-governance.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_meeting_minutes_engine_declares_meeting_minutes_record() -> None:
    """meeting-minutes-engine governance manifest must declare meeting_minutes_record."""
    manifest = _load_governance_manifest("meeting-minutes-engine")
    contracts = manifest.get("contracts", {})
    assert "meeting_minutes_record" in contracts, (
        "meeting-minutes-engine.spectrum-governance.json must declare meeting_minutes_record"
    )


def test_spectrum_program_advisor_declares_meeting_minutes_record() -> None:
    """spectrum-program-advisor governance manifest must declare meeting_minutes_record."""
    manifest = _load_governance_manifest("spectrum-program-advisor")
    contracts = manifest.get("contracts", {})
    assert "meeting_minutes_record" in contracts, (
        "spectrum-program-advisor.spectrum-governance.json must declare meeting_minutes_record"
    )


def test_meeting_minutes_record_version_pin_matches_canonical() -> None:
    """Both consumer manifests must pin meeting_minutes_record at the canonical version."""
    manifest_data = json.loads(STANDARDS_MANIFEST.read_text())
    contracts = manifest_data.get("contracts", [])
    entry = next(c for c in contracts if c.get("artifact_type") == "meeting_minutes_record")
    canonical_version = entry["schema_version"]

    for repo_name in MEETING_MINUTES_RECORD_CONSUMERS:
        manifest = _load_governance_manifest(repo_name)
        pinned = manifest.get("contracts", {}).get("meeting_minutes_record")
        assert pinned == canonical_version, (
            f"{repo_name} pins meeting_minutes_record@{pinned!r} "
            f"but canonical version is {canonical_version!r}"
        )


def test_all_intended_consumers_declare_meeting_minutes_record() -> None:
    """Every repo listed as intended_consumer of meeting_minutes_record must declare it."""
    manifest_data = json.loads(STANDARDS_MANIFEST.read_text())
    contracts = manifest_data.get("contracts", [])
    entry = next(c for c in contracts if c.get("artifact_type") == "meeting_minutes_record")
    intended = entry.get("intended_consumers", [])

    for repo_name in intended:
        manifest_path = MANIFESTS_DIR / f"{repo_name}.spectrum-governance.json"
        if not manifest_path.exists():
            continue  # not-yet-enforceable — skip
        repo_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        declared = repo_manifest.get("contracts", {})
        assert "meeting_minutes_record" in declared, (
            f"{repo_name} is an intended_consumer of meeting_minutes_record "
            f"but does not declare it in its governance manifest"
        )
