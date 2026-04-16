from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.transcript_hardening import (
    TranscriptHardeningError,
    assert_compatible_version,
    assert_registered_artifact_type,
    normalize_transcript_deterministically,
    run_red_team_loop,
    run_transcript_hardening,
)


FIXTURES = Path(__file__).parent / "fixtures" / "transcript_hardening"


def _sample_payload() -> dict:
    return json.loads((FIXTURES / "sample_transcript.json").read_text(encoding="utf-8"))


def test_normalization_is_deterministic() -> None:
    payload = _sample_payload()
    first = normalize_transcript_deterministically(payload)
    second = normalize_transcript_deterministically(payload)
    assert first["replay_hash"] == second["replay_hash"]
    assert first["chunking"] == second["chunking"]


def test_artifact_type_registration_and_compatibility_rules() -> None:
    assert_registered_artifact_type("transcript_artifact", "1.0.0")
    assert_compatible_version(producer_version="1.0.0", consumer_version="1.2.1")
    with pytest.raises(TranscriptHardeningError):
        assert_registered_artifact_type("transcript_artifact", "2.0.0")
    with pytest.raises(TranscriptHardeningError):
        assert_compatible_version(producer_version="2.0.0", consumer_version="1.9.9")


def test_fail_closed_when_missing_segments() -> None:
    with pytest.raises(TranscriptHardeningError):
        normalize_transcript_deterministically({"segments": []})


def test_hardening_run_validates_contract_and_control_flow() -> None:
    artifact = run_transcript_hardening(_sample_payload(), trace_id="trace-trn02", run_id="run-trn02")
    validate_artifact(artifact, "transcript_hardening_run")
    assert artifact["eval"]["pass"] is True
    assert artifact["control"]["decision"] in {"ALLOW", "BLOCK"}
    assert artifact["ai"]["grounding_enforced"] is True
    assert all(review["unresolved_s2_plus"] == 0 for review in artifact["red_team_reviews"])


def test_red_team_loop_applies_fix_each_review() -> None:
    reviews = run_red_team_loop()
    assert len(reviews) == 7
    assert all(review["fixes_applied"] for review in reviews)
    assert all(review["unresolved_s2_plus"] == 0 for review in reviews)


def test_feedback_loop_derives_evals_from_failures() -> None:
    payload = {
        "segments": [
            {
                "segment_id": "seg-1",
                "speaker": "Lead",
                "timestamp": "2026-04-16T10:00:00Z",
                "text": "Claim indicates approval is expected.",
            }
        ]
    }
    artifact = run_transcript_hardening(payload, trace_id="trace-failure", run_id="run-failure")
    assert artifact["control"]["decision"] == "BLOCK"
    derived = artifact["feedback_loop"]["failure_derived_evals"]
    assert derived
    assert any(row["generated_from"] in {"parse", "schema", "evidence", "contradiction", "replay", "policy", "drift"} for row in derived)
