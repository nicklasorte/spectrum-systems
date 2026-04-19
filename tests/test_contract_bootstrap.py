import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STANDARDS_MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"
SCHEMAS_DIR = REPO_ROOT / "contracts" / "schemas"

STRATEGIC_SCHEMAS = {
    "strategic_knowledge_source_ref",
    "strategic_knowledge_artifact_ref",
    "book_intelligence_pack",
    "transcript_intelligence_pack",
    "story_bank_entry",
    "tactic_register",
    "viewpoint_pack",
    "evidence_map",
}

# Existing repository convention: meeting_minutes artifact metadata is published
# in standards manifest, while module-level meeting_minutes schemas live under
# contracts/schemas/meeting_minutes/*.schema.json.
LEGACY_NON_CANONICAL_SCHEMA_LAYOUT = {"meeting_minutes"}


def test_manifest_declared_schema_paths_exist_and_are_json() -> None:
    manifest = json.loads(STANDARDS_MANIFEST_PATH.read_text(encoding="utf-8"))
    declared = {entry["artifact_type"] for entry in manifest.get("contracts", [])}

    missing_paths = []
    invalid_json = []

    for artifact_type in declared:
        if artifact_type in LEGACY_NON_CANONICAL_SCHEMA_LAYOUT:
            continue

        schema_path = SCHEMAS_DIR / f"{artifact_type}.schema.json"
        if not schema_path.is_file():
            missing_paths.append(str(schema_path.relative_to(REPO_ROOT)))
            continue
        try:
            json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            invalid_json.append(f"{schema_path.relative_to(REPO_ROOT)}: {exc}")

    assert not missing_paths, f"Declared schema files are missing: {missing_paths}"
    assert not invalid_json, f"Declared schema files contain invalid JSON: {invalid_json}"


def test_manifest_declared_schema_artifact_type_consts_match() -> None:
    artifact_type = "preflight_repair_result_record"
    schema_path = SCHEMAS_DIR / f"{artifact_type}.schema.json"
    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    properties = payload.get("properties") if isinstance(payload, dict) else {}
    artifact_prop = properties.get("artifact_type") if isinstance(properties, dict) else {}
    schema_const = str((artifact_prop or {}).get("const") or "").strip()
    assert schema_const == artifact_type


def test_strategic_schema_files_are_registered() -> None:
    manifest = json.loads(STANDARDS_MANIFEST_PATH.read_text(encoding="utf-8"))
    declared = {entry["artifact_type"] for entry in manifest.get("contracts", [])}

    strategic_files_on_disk = {
        path.name.replace(".schema.json", "")
        for path in SCHEMAS_DIR.glob("*.schema.json")
        if path.name.replace(".schema.json", "") in STRATEGIC_SCHEMAS
    }

    missing_from_manifest = sorted(strategic_files_on_disk - declared)
    assert not missing_from_manifest, (
        "Strategic Knowledge schemas exist on disk but are not registered in standards-manifest: "
        f"{missing_from_manifest}"
    )
