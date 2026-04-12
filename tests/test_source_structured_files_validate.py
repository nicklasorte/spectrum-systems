import json
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "source_design_extraction.schema.json"
STRUCTURED_DIR = REPO_ROOT / "docs" / "source_structured"


def _load(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_all_structured_source_files_validate_against_schema() -> None:
    validator = Draft202012Validator(_load(SCHEMA_PATH))
    files = sorted(STRUCTURED_DIR.glob("*.json"))
    assert len(files) >= 20

    for path in files:
        payload = _load(path)
        validator.validate(payload)


def test_structured_source_files_have_unique_obligation_ids_by_default() -> None:
    files = sorted(STRUCTURED_DIR.glob("*.json"))
    obligation_to_rows: dict[str, list[str]] = {}

    for path in files:
        payload = _load(path)
        source_id = payload["source_document"]["source_id"]
        for row in payload["source_traceability_rows"]:
            obligation_to_rows.setdefault(row["obligation_id"], []).append(f"{source_id}:{row['trace_id']}")

    duplicates = {obligation: refs for obligation, refs in obligation_to_rows.items() if len(refs) > 1}
    assert not duplicates, f"Unexpected duplicate obligations: {duplicates}"
