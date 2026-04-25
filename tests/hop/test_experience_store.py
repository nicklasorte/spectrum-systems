"""Experience store tests — write/read, append-only, fail-closed."""

from __future__ import annotations

import json

import pytest

from spectrum_systems.modules.hop.experience_store import ExperienceStore, HopStoreError
from tests.hop.conftest import make_baseline_candidate


def test_write_and_read_candidate(store: ExperienceStore) -> None:
    candidate = make_baseline_candidate()
    path = store.write_artifact(candidate)
    assert path.exists()
    loaded = store.read_artifact("hop_harness_candidate", candidate["artifact_id"])
    assert loaded == candidate


def test_index_is_appended(store: ExperienceStore) -> None:
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    lines = store.index_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["artifact_type"] == "hop_harness_candidate"
    assert record["artifact_id"] == candidate["artifact_id"]
    assert "candidate_id" in record["fields"]


def test_idempotent_rewrite_of_identical_payload(store: ExperienceStore) -> None:
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    # Identical payload — should not raise, should not append a second index line.
    store.write_artifact(candidate)
    lines = store.index_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


def test_overwrite_with_forged_artifact_id_is_rejected(store: ExperienceStore) -> None:
    """A second valid payload that forges an existing artifact_id is rejected.

    Because artifact_id is derived from content_hash, a real collision is
    cryptographically infeasible. This test simulates the adversarial case by
    writing a valid second candidate then retargeting its artifact_id onto
    the first candidate's slot. The store rejects the duplicate.
    """
    from spectrum_systems.modules.hop.artifacts import finalize_artifact

    first = make_baseline_candidate()
    store.write_artifact(first)

    second = make_baseline_candidate(code_source=first["code_source"] + "\n# variant\n")
    second["candidate_id"] = "forged_collision"
    second.pop("content_hash", None)
    second.pop("artifact_id", None)
    finalize_artifact(second, id_prefix="hop_candidate_")

    # Now retarget the second payload's artifact_id onto first's slot,
    # invalidating the hash binding. The store must refuse.
    second["artifact_id"] = first["artifact_id"]
    with pytest.raises(HopStoreError):
        store.write_artifact(second)


def test_malformed_payload_is_rejected_before_write(store: ExperienceStore) -> None:
    bad = {"artifact_type": "hop_harness_candidate", "garbage": True}
    with pytest.raises(HopStoreError, match="schema_violation"):
        store.write_artifact(bad)
    # Nothing written — index empty, candidates dir empty.
    assert store.index_path.read_text(encoding="utf-8") == ""
    assert not list((store.root / "candidates").iterdir())


def test_unsupported_artifact_type_is_rejected(store: ExperienceStore) -> None:
    with pytest.raises(HopStoreError, match="invalid_payload"):
        store.write_artifact({"artifact_type": "not_a_hop_artifact"})


def test_iter_index_streams_and_filters(store: ExperienceStore) -> None:
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    records = list(store.iter_index(artifact_type="hop_harness_candidate"))
    assert len(records) == 1
    none_records = list(store.iter_index(artifact_type="hop_harness_run"))
    assert none_records == []


def test_read_missing_artifact_raises(store: ExperienceStore) -> None:
    with pytest.raises(HopStoreError, match="missing_artifact"):
        store.read_artifact("hop_harness_candidate", "hop_candidate_does_not_exist")


def test_corrupted_index_line_fails_closed(store: ExperienceStore) -> None:
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    with store.index_path.open("a", encoding="utf-8") as h:
        h.write("not_json\n")
    with pytest.raises(HopStoreError, match="corrupted_index"):
        list(store.iter_index())
