"""Tests for the held-out certification eval set."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.hop.artifacts import compute_content_hash
from spectrum_systems.modules.hop.evaluator import (
    evaluate_candidate,
    load_eval_set_from_manifest,
)
from spectrum_systems.modules.hop.schemas import validate_hop_artifact
from tests.hop.conftest import HELDOUT_EVAL_DIR, EVAL_DIR, make_baseline_candidate


def test_heldout_manifest_loads():
    eval_set = load_eval_set_from_manifest(str(HELDOUT_EVAL_DIR / "manifest.json"))
    assert eval_set.eval_set_id == "hop_transcript_to_faq_heldout_v1"
    assert eval_set.eval_set_version == "1.0.0"
    assert eval_set.case_count >= 5


def test_heldout_disjoint_from_search_set():
    """Held-out cases must not share transcript_ids with the search set."""
    search_manifest = json.loads((EVAL_DIR / "manifest.json").read_text(encoding="utf-8"))
    heldout_manifest = json.loads(
        (HELDOUT_EVAL_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    search_tids: set[str] = set()
    for entry in search_manifest["cases"]:
        payload = json.loads((EVAL_DIR / entry["path"]).read_text(encoding="utf-8"))
        search_tids.add(payload["input"]["transcript_id"])
    for entry in heldout_manifest["cases"]:
        payload = json.loads(
            (HELDOUT_EVAL_DIR / entry["path"]).read_text(encoding="utf-8")
        )
        assert payload["input"]["transcript_id"] not in search_tids


def test_heldout_cases_are_schema_valid_and_hashed():
    heldout_manifest = json.loads(
        (HELDOUT_EVAL_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    for entry in heldout_manifest["cases"]:
        payload = json.loads(
            (HELDOUT_EVAL_DIR / entry["path"]).read_text(encoding="utf-8")
        )
        validate_hop_artifact(payload, "hop_harness_eval_case")
        assert payload["content_hash"] == compute_content_hash(payload)
        assert payload["content_hash"] == entry["content_hash"]


def test_heldout_disjoint_from_search_eval_set_ids():
    search = load_eval_set_from_manifest(str(EVAL_DIR / "manifest.json"))
    heldout = load_eval_set_from_manifest(str(HELDOUT_EVAL_DIR / "manifest.json"))
    assert search.eval_set_id != heldout.eval_set_id


def test_baseline_passes_held_out_set(heldout_eval_set):
    candidate = make_baseline_candidate()
    bundle = evaluate_candidate(candidate_payload=candidate, eval_set=heldout_eval_set)
    assert bundle["score"]["score"] == 1.0
    assert bundle["score"]["pass_count"] == heldout_eval_set.case_count


def test_heldout_tampered_manifest_rejected(tmp_path: Path):
    """If the manifest content_hash is mutated, loading must fail closed."""
    manifest = json.loads(
        (HELDOUT_EVAL_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    # Tamper with the first manifest entry's hash.
    manifest["cases"][0]["content_hash"] = "sha256:" + "0" * 64
    target_dir = tmp_path / "tampered"
    target_dir.mkdir()
    (target_dir / "cases").mkdir()
    for entry in manifest["cases"]:
        src = HELDOUT_EVAL_DIR / entry["path"]
        dst = target_dir / entry["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    (target_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="hop_evaluator_tampered_manifest"):
        load_eval_set_from_manifest(str(target_dir / "manifest.json"))
