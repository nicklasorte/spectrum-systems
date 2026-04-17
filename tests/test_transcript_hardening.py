from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.transcript_hardening import (
    TranscriptHardeningError,
    build_owner_handoffs,
    normalize_transcript_segments,
    run_transcript_hardening,
)


FIXTURES = Path(__file__).parent / "fixtures" / "transcript_hardening"


def _sample_payload() -> dict:
    return json.loads((FIXTURES / "sample_transcript.json").read_text(encoding="utf-8"))


def test_normalization_is_deterministic() -> None:
    payload = _sample_payload()
    first = normalize_transcript_segments(payload)
    second = normalize_transcript_segments(payload)
    assert first["replay_hash"] == second["replay_hash"]
    assert first["chunking"] == second["chunking"]


def test_fail_closed_when_missing_segments() -> None:
    with pytest.raises(TranscriptHardeningError):
        normalize_transcript_segments({"segments": []})


def test_handoff_signals_are_input_only() -> None:
    handoff = build_owner_handoffs(
        trace_id="trace-1",
        run_id="run-1",
        transcript_run_ref="trn-run-0123456789abcdef",
        replay_hash="a" * 64,
    )
    assert set(handoff.keys()) == {"eval_input", "control_input", "judgment_input", "certification_input"}
    assert "decision" not in json.dumps(handoff)


def test_run_artifact_validates_schema() -> None:
    artifact = run_transcript_hardening(_sample_payload(), trace_id="trace-trn02", run_id="run-trn02")
    validate_artifact(artifact, "transcript_hardening_run")
    assert artifact["processing_status"] == "processed"


def test_run_artifact_does_not_emit_protected_authority_outcomes() -> None:
    artifact = run_transcript_hardening(_sample_payload(), trace_id="trace-2", run_id="run-2")
    encoded = json.dumps(artifact)
    forbidden = {
        '"control":',
        '"judgment":',
        '"certification":',
        '"decision":',
        '"enforcement":',
    }
    assert not any(token in encoded for token in forbidden)


def test_observation_evidence_is_anchored() -> None:
    artifact = run_transcript_hardening(_sample_payload(), trace_id="trace-3", run_id="run-3")
    groups = artifact["observations"]
    for name in ("topics", "claims", "actions", "ambiguities"):
        for row in groups[name]:
            assert row["evidence"]
            anchor = row["evidence"][0]
            assert {"segment_id", "start_char", "end_char", "timestamp"}.issubset(anchor)


def test_normalization_is_stable_under_input_order_variation() -> None:
    payload = _sample_payload()
    reversed_payload = {**payload, "segments": list(reversed(payload["segments"]))}
    first = normalize_transcript_segments(payload, chunk_size=2)
    second = normalize_transcript_segments(reversed_payload, chunk_size=2)
    assert first["replay_hash"] != second["replay_hash"]
    assert first["segment_count"] == second["segment_count"]


def test_schema_compatibility_contract_for_run_artifact_family() -> None:
    artifact = run_transcript_hardening(_sample_payload(), trace_id="trace-compat", run_id="run-compat")
    assert artifact["schema_version"] == "1.0.0"
    assert artifact["processor_versions"]["normalizer"].startswith("trn-normalizer-")
    assert artifact["processor_versions"]["evidence_preparation"].startswith("trn-evidence-")
    validate_artifact(artifact, "transcript_hardening_run")
