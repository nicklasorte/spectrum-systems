"""Tests for the red-team fix pass (F-02 ... F-07)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.hop.artifacts import compute_content_hash
from spectrum_systems.modules.hop.evaluator import (
    EvalSet,
    evaluate_candidate,
    load_eval_set_from_manifest,
)
from spectrum_systems.modules.hop.experience_store import ExperienceStore, HopStoreError
from spectrum_systems.modules.hop import baseline_harness
from spectrum_systems.modules.hop.safety_checks import scan_candidate
from spectrum_systems.modules.hop.schemas import HopSchemaError, load_hop_schema
from tests.hop.conftest import make_baseline_candidate

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "contracts" / "evals" / "hop" / "manifest.json"


# ---- F-02: manifest loader integrity --------------------------------------

def test_manifest_loader_returns_eval_set() -> None:
    es = load_eval_set_from_manifest(str(MANIFEST_PATH))
    assert isinstance(es, EvalSet)
    assert es.case_count >= 20


def test_manifest_loader_rejects_tampered_case(tmp_path: Path) -> None:
    # Copy the eval set into tmp and tamper with a case file's content_hash.
    src_dir = REPO_ROOT / "contracts" / "evals" / "hop"
    dst_dir = tmp_path / "hop"
    (dst_dir / "cases").mkdir(parents=True)
    for src in (src_dir / "cases").glob("*.json"):
        (dst_dir / "cases" / src.name).write_text(
            src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    manifest = json.loads((src_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest_path = dst_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    # Tamper with a single case payload (mutate transcript text without
    # updating its content_hash).
    target = dst_dir / "cases" / manifest["cases"][0]["path"].split("/")[-1]
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["input"]["turns"][0]["text"] = payload["input"]["turns"][0]["text"] + " EXTRA"
    target.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="tampered_case"):
        load_eval_set_from_manifest(str(manifest_path))


def test_manifest_loader_rejects_manifest_hash_mismatch(tmp_path: Path) -> None:
    src_dir = REPO_ROOT / "contracts" / "evals" / "hop"
    dst_dir = tmp_path / "hop"
    (dst_dir / "cases").mkdir(parents=True)
    for src in (src_dir / "cases").glob("*.json"):
        (dst_dir / "cases" / src.name).write_text(
            src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    manifest = json.loads((src_dir / "manifest.json").read_text(encoding="utf-8"))
    # Tamper with the manifest's recorded content_hash for one entry.
    manifest["cases"][0]["content_hash"] = "sha256:" + "0" * 64
    manifest_path = dst_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="tampered_manifest"):
        load_eval_set_from_manifest(str(manifest_path))


# ---- F-03: store recomputes content_hash ----------------------------------

def test_store_rejects_inconsistent_content_hash(store: ExperienceStore) -> None:
    candidate = make_baseline_candidate()
    candidate["content_hash"] = "sha256:" + "0" * 64
    with pytest.raises(HopStoreError, match="content_hash_mismatch"):
        store.write_artifact(candidate)


def test_store_recomputes_content_hash_on_read(store: ExperienceStore) -> None:
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    target = store._path_for("hop_harness_candidate", candidate["artifact_id"])  # type: ignore[attr-defined]
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["code_source"] = payload["code_source"] + "\n# tampered\n"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(HopStoreError, match="hash_mismatch"):
        store.read_artifact("hop_harness_candidate", candidate["artifact_id"])


# ---- F-04: trace incomplete on any failure --------------------------------

def test_trace_marked_incomplete_on_malformed_output(store, eval_set) -> None:
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)

    def bad_runner(_):
        return {"not": "a_valid_faq"}

    result = evaluate_candidate(
        candidate_payload=candidate,
        runner=bad_runner,
        eval_set=eval_set,
        store=store,
    )
    assert all(t["complete"] is False for t in result["traces"])
    assert all(t["incomplete_reason"] for t in result["traces"])


# ---- F-05: long transcript_id leakage --------------------------------------

def test_long_transcript_id_leakage_is_detected() -> None:
    case = {
        "artifact_type": "hop_harness_eval_case",
        "schema_ref": "hop/harness_eval_case.schema.json",
        "schema_version": "1.0.0",
        "trace": {"primary": "t", "related": []},
        "eval_case_id": "hop_case_long_transcript_test",
        "eval_case_version": "1.0.0",
        "category": "golden",
        "input": {"transcript_id": "transcript_super_long_unique_id_xyz", "turns": []},
        "pass_criteria": {"judge": "structural", "rules": {}},
        "failure_modes_targeted": [],
        "content_hash": "sha256:" + "0" * 64,
        "artifact_id": "hop_eval_case_test",
    }
    leaky = make_baseline_candidate(
        code_source=(
            "def run(t):\n"
            "    if 'transcript_super_long_unique_id_xyz' in t.get('transcript_id', ''):\n"
            "        return {}\n"
            "    return {}\n"
        )
    )
    ok, failures = scan_candidate(leaky, [case])
    assert not ok
    assert any(f["failure_class"] == "eval_dataset_leakage" for f in failures)


# ---- F-07: schema dialect enforcement -------------------------------------

def test_schema_loader_enforces_2020_12_dialect(tmp_path, monkeypatch) -> None:
    from spectrum_systems.modules.hop import schemas as hop_schemas

    bad_path = tmp_path / "harness_candidate.schema.json"
    bad_path.write_text(
        json.dumps(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "additionalProperties": False,
                "type": "object",
            }
        ),
        encoding="utf-8",
    )

    real_paths = {**hop_schemas._SCHEMA_FILES}
    monkeypatch.setattr(hop_schemas, "_HOP_SCHEMA_DIR", tmp_path)
    monkeypatch.setattr(
        hop_schemas, "_SCHEMA_FILES", {"hop_harness_candidate": "harness_candidate.schema.json"}
    )

    with pytest.raises(HopSchemaError, match="unsupported_dialect"):
        load_hop_schema("hop_harness_candidate")

    # Restore for subsequent tests in the same session.
    monkeypatch.setattr(hop_schemas, "_SCHEMA_FILES", real_paths)


def test_schema_loader_enforces_additional_properties_false(tmp_path, monkeypatch) -> None:
    from spectrum_systems.modules.hop import schemas as hop_schemas

    bad_path = tmp_path / "harness_candidate.schema.json"
    bad_path.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": True,
            }
        ),
        encoding="utf-8",
    )

    real_paths = {**hop_schemas._SCHEMA_FILES}
    monkeypatch.setattr(hop_schemas, "_HOP_SCHEMA_DIR", tmp_path)
    monkeypatch.setattr(
        hop_schemas, "_SCHEMA_FILES", {"hop_harness_candidate": "harness_candidate.schema.json"}
    )

    with pytest.raises(HopSchemaError, match="must_forbid_additional_properties"):
        load_hop_schema("hop_harness_candidate")

    monkeypatch.setattr(hop_schemas, "_SCHEMA_FILES", real_paths)
