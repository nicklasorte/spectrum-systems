"""Schema-level tests for HOP artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.schemas import (
    HopSchemaError,
    list_hop_schemas,
    load_hop_schema,
    validate_hop_artifact,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
HOP_SCHEMA_DIR = REPO_ROOT / "contracts" / "schemas" / "hop"


REQUIRED_HOP_SCHEMAS = {
    "hop_harness_candidate",
    "hop_harness_run",
    "hop_harness_score",
    "hop_harness_trace",
    "hop_harness_frontier",
    "hop_harness_failure_hypothesis",
    "hop_harness_eval_case",
    "hop_harness_faq_output",
    "hop_harness_extraction_signal",
}


def test_all_required_schemas_are_registered() -> None:
    assert REQUIRED_HOP_SCHEMAS.issubset(set(list_hop_schemas()))


@pytest.mark.parametrize("name", sorted(REQUIRED_HOP_SCHEMAS))
def test_schema_files_exist_and_load(name: str) -> None:
    schema = load_hop_schema(name)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    required = set(schema.get("required", []))
    assert {"artifact_id", "schema_ref", "trace", "content_hash"} <= required


def test_validate_rejects_missing_required_field() -> None:
    payload = {
        "artifact_type": "hop_harness_candidate",
        "schema_ref": "hop/harness_candidate.schema.json",
        "schema_version": "1.0.0",
        "trace": {"primary": "t", "related": []},
        "candidate_id": "missing_hash",
        "harness_type": "transcript_to_faq",
        "code_module": "x.y",
        "code_entrypoint": "run",
        "code_source": "def run(t): return t",
        "declared_methods": ["run"],
        "created_at": "2026-04-25T00:00:00.000000Z",
    }
    with pytest.raises(HopSchemaError):
        validate_hop_artifact(payload, "hop_harness_candidate")


def test_validate_rejects_additional_properties() -> None:
    payload = {
        "artifact_type": "hop_harness_candidate",
        "schema_ref": "hop/harness_candidate.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary="t"),
        "candidate_id": "extra_props",
        "harness_type": "transcript_to_faq",
        "code_module": "x.y",
        "code_entrypoint": "run",
        "code_source": "def run(t): return t",
        "declared_methods": ["run"],
        "parent_candidate_id": None,
        "created_at": "2026-04-25T00:00:00.000000Z",
        "secret_extra": "leak",
    }
    finalize_artifact(payload, id_prefix="hop_candidate_")
    with pytest.raises(HopSchemaError):
        validate_hop_artifact(payload, "hop_harness_candidate")


def test_unknown_schema_raises() -> None:
    with pytest.raises(HopSchemaError):
        load_hop_schema("hop_unknown_artifact")


def test_validate_non_object_raises() -> None:
    with pytest.raises(HopSchemaError):
        validate_hop_artifact("not_a_dict", "hop_harness_candidate")  # type: ignore[arg-type]


def test_eval_cases_validate_against_schema() -> None:
    case_dir = REPO_ROOT / "contracts" / "evals" / "hop" / "cases"
    files = sorted(case_dir.glob("*.json"))
    assert len(files) >= 20, "must have at least 20 eval cases"
    assert len(files) <= 50, "must have no more than 50 eval cases"
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_hop_artifact(payload, "hop_harness_eval_case")
