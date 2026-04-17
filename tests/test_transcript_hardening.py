from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.trace_engine import clear_trace_store, get_trace, start_trace
from spectrum_systems.modules.transcript_hardening import (
    TranscriptHardeningError,
    build_hardening_failure_artifact,
    build_owner_handoffs,
    normalize_transcript_segments,
    run_transcript_family_certification_checks,
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
    for signal in handoff.values():
        assert signal["replay_hash"] == "a" * 64
    assert "decision" not in json.dumps(handoff)
    assert "certification_status" not in json.dumps(handoff)


def test_handoff_schema_requires_replay_hash() -> None:
    handoff = build_owner_handoffs(
        trace_id="trace-1",
        run_id="run-1",
        transcript_run_ref="trn-run-0123456789abcdef",
        replay_hash="a" * 64,
    )["control_input"]
    handoff.pop("replay_hash")
    with pytest.raises(Exception):
        validate_artifact(
            {
                "artifact_type": "transcript_hardening_run",
                "schema_version": "1.1.0",
                "artifact_id": "trn-run-0123456789abcdef",
                "trace_id": "trace-1",
                "run_id": "run-1",
                "generated_at": "2026-04-17T00:00:00+00:00",
                "source_refs": [],
                "processor_versions": {"normalizer": "n", "evidence_preparation": "e"},
                "normalization": {
                    "segment_count": 1,
                    "segments": [{"segment_id": "s1", "speaker": "spk", "text": "text", "timestamp": "", "ordinal": 1}],
                    "replay_hash": "a" * 64,
                    "chunking": {"chunk_size": 1, "chunk_count": 1, "chunk_hashes": ["b" * 64]},
                },
                "observations": {
                    "topics": [],
                    "claims": [],
                    "actions": [],
                    "ambiguities": [],
                    "classification_mode": "deterministic_preparatory",
                    "eval_hook_refs": ["eval:x"],
                    "non_authority_assertions": ["preparatory_only"],
                    "evidence_anchor_count": 0,
                },
                "handoff_artifacts": {
                    "eval_input": {
                        "artifact_type": "transcript_eval_input_signal",
                        "trace_id": "trace-1",
                        "run_id": "run-1",
                        "transcript_run_ref": "trn-run-0123456789abcdef",
                        "replay_hash": "a" * 64,
                    },
                    "control_input": handoff,
                    "judgment_input": {
                        "artifact_type": "transcript_judgment_input_signal",
                        "trace_id": "trace-1",
                        "run_id": "run-1",
                        "transcript_run_ref": "trn-run-0123456789abcdef",
                        "replay_hash": "a" * 64,
                    },
                    "certification_input": {
                        "artifact_type": "transcript_certification_input_signal",
                        "trace_id": "trace-1",
                        "run_id": "run-1",
                        "transcript_run_ref": "trn-run-0123456789abcdef",
                        "replay_hash": "a" * 64,
                    },
                },
                "lineage": {"input_hash": "a" * 64, "output_hash": "b" * 64, "replay_hash": "a" * 64},
                "processing_status": "processed",
            },
            "transcript_hardening_run",
        )


def test_run_artifact_validates_schema() -> None:
    clear_trace_store()
    trace_id = start_trace({"trace_id": "trace-trn02", "run_id": "run-trn02"})
    artifact = run_transcript_hardening(_sample_payload(), trace_id=trace_id, run_id="run-trn02")
    validate_artifact(artifact, "transcript_hardening_run")
    assert artifact["processing_status"] == "processed"
    replay_hash = artifact["normalization"]["replay_hash"]
    for handoff in artifact["handoff_artifacts"].values():
        assert handoff["replay_hash"] == replay_hash


def test_run_artifact_does_not_emit_protected_authority_outcomes() -> None:
    clear_trace_store()
    trace_id = start_trace({"trace_id": "trace-2", "run_id": "run-2"})
    artifact = run_transcript_hardening(_sample_payload(), trace_id=trace_id, run_id="run-2")
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
    clear_trace_store()
    trace_id = start_trace({"trace_id": "trace-3", "run_id": "run-3"})
    artifact = run_transcript_hardening(_sample_payload(), trace_id=trace_id, run_id="run-3")
    groups = artifact["observations"]
    for name in ("topics", "claims", "actions", "ambiguities"):
        for row in groups[name]:
            assert row["evidence"]
            assert row["classification_confidence"] > 0.0
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
    clear_trace_store()
    trace_id = start_trace({"trace_id": "trace-compat", "run_id": "run-compat"})
    artifact = run_transcript_hardening(_sample_payload(), trace_id=trace_id, run_id="run-compat")
    assert artifact["schema_version"] == "1.1.0"
    assert artifact["processor_versions"]["normalizer"].startswith("trn-normalizer-")
    assert artifact["processor_versions"]["evidence_preparation"].startswith("trn-evidence-")
    validate_artifact(artifact, "transcript_hardening_run")


def test_missing_or_invalid_trace_returns_failure_artifact() -> None:
    clear_trace_store()
    failure = run_transcript_hardening(_sample_payload(), trace_id="missing-trace", run_id="run-missing")
    validate_artifact(failure, "transcript_hardening_failure")
    assert failure["processing_status"] == "failed"


def test_trace_span_and_events_are_recorded_for_classification() -> None:
    clear_trace_store()
    trace_id = start_trace({"trace_id": "trace-observation", "run_id": "run-observation"})
    artifact = run_transcript_hardening(_sample_payload(), trace_id=trace_id, run_id="run-observation")
    assert artifact["processing_status"] == "processed"
    trace = get_trace(trace_id)
    events = [event for span in trace["spans"] for event in span.get("events", [])]
    assert any(event["event_type"] == "transcript_observation_classified" for event in events)


def test_failure_artifact_builder_validates_schema() -> None:
    failure = build_hardening_failure_artifact(
        trace_id="trace-failure",
        run_id="run-failure",
        failure_reason="invalid transcript payload",
    )
    validate_artifact(failure, "transcript_hardening_failure")


def test_transcript_family_certification_checks_pass_on_valid_run() -> None:
    clear_trace_store()
    trace_id = start_trace({"trace_id": "trace-cert-check", "run_id": "run-cert-check"})
    artifact = run_transcript_hardening(_sample_payload(), trace_id=trace_id, run_id="run-cert-check")
    result = run_transcript_family_certification_checks(artifact)
    assert result["status"] == "pass"


def test_transcript_family_certification_checks_block_on_replay_mismatch() -> None:
    clear_trace_store()
    trace_id = start_trace({"trace_id": "trace-cert-check-fail", "run_id": "run-cert-check-fail"})
    artifact = run_transcript_hardening(_sample_payload(), trace_id=trace_id, run_id="run-cert-check-fail")
    artifact["handoff_artifacts"]["control_input"]["replay_hash"] = "0" * 64
    result = run_transcript_family_certification_checks(artifact)
    assert result["status"] == "block"
    assert any(item.startswith("replay_hash_mismatch:control_input") for item in result["failures"])
