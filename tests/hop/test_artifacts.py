"""Tests for the artifact finalization helpers (deterministic hashing/id)."""

from __future__ import annotations

from spectrum_systems.modules.hop.artifacts import (
    canonical_json,
    compute_content_hash,
    derive_artifact_id,
    finalize_artifact,
    make_trace,
)


def _payload() -> dict:
    return {
        "artifact_type": "hop_harness_candidate",
        "schema_ref": "hop/harness_candidate.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary="t"),
        "candidate_id": "deterministic_test",
        "harness_type": "transcript_to_faq",
        "code_module": "x",
        "code_entrypoint": "run",
        "code_source": "def run(t): return t",
        "declared_methods": ["run"],
        "parent_candidate_id": None,
        "created_at": "2026-04-25T00:00:00.000000Z",
    }


def test_content_hash_is_deterministic_under_key_reordering() -> None:
    payload_a = _payload()
    payload_b = {k: payload_a[k] for k in reversed(list(payload_a.keys()))}
    assert compute_content_hash(payload_a) == compute_content_hash(payload_b)


def test_content_hash_changes_when_payload_changes() -> None:
    base = _payload()
    h1 = compute_content_hash(base)
    base["code_source"] = base["code_source"] + "\n# noop"
    h2 = compute_content_hash(base)
    assert h1 != h2


def test_artifact_id_is_derived_from_content_hash() -> None:
    payload = _payload()
    finalize_artifact(payload, id_prefix="hop_candidate_")
    assert payload["artifact_id"] == derive_artifact_id(
        "hop_candidate_", payload["content_hash"]
    )


def test_canonical_json_is_sorted_and_compact() -> None:
    payload = {"b": 1, "a": [3, 2, 1]}
    assert canonical_json(payload) == '{"a":[3,2,1],"b":1}'


def test_make_trace_dedupes_and_sorts_related() -> None:
    trace = make_trace(primary="p", related=["b", "a", "a", "c", "b"])
    assert trace == {"primary": "p", "related": ["a", "b", "c"]}
