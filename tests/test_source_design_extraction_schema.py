import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "source_design_extraction.schema.json"
SAMPLE_PATH = REPO_ROOT / "docs" / "source_structured" / "mapping_google_sre_reliability_principles_to_spectrum_systems.json"


def _load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_load(SCHEMA_PATH))


def test_schema_accepts_valid_structured_extraction_sample() -> None:
    payload = _load(SAMPLE_PATH)
    _validator().validate(payload)


def test_schema_rejects_missing_required_extraction_field() -> None:
    payload = copy.deepcopy(_load(SAMPLE_PATH))
    del payload["extraction"]["fail_closed_requirements"]

    with pytest.raises(Exception):
        _validator().validate(payload)


def test_schema_rejects_malformed_obligation_id() -> None:
    payload = copy.deepcopy(_load(SAMPLE_PATH))
    payload["source_traceability_rows"][0]["obligation_id"] = "BAD-OBLIGATION-ID"

    with pytest.raises(Exception):
        _validator().validate(payload)
