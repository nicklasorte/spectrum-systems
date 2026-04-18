from __future__ import annotations

from datetime import datetime, timezone

from spectrum_systems.modules.wpg.context_governance import detect_context_contradictions, evaluate_context_admission


def test_context_contradiction_detection_finds_cross_source_conflict() -> None:
    contradictions = detect_context_contradictions(
        [
            {
                "component_type": "transcript",
                "source_ref": "transcript_artifact",
                "statements": [{"topic": "deployment", "polarity": "affirm", "text": "Deployment can start"}],
            },
            {
                "component_type": "critique_artifacts",
                "source_ref": "critique_artifact",
                "statements": [{"topic": "deployment", "polarity": "deny", "text": "Deployment cannot start"}],
            },
        ]
    )
    assert contradictions
    assert contradictions[0]["topic"] == "deployment"


def test_context_contradiction_detection_blocks_unresolved_conflict() -> None:
    bundle = {
        "artifact_type": "context_bundle_artifact",
        "schema_version": "1.0.0",
        "context_bundle_id": "ctxb-1",
        "trace": {"trace_id": "t", "run_id": "r"},
        "created_at": "2026-04-18T00:00:00Z",
        "components": [
            {
                "component_type": "transcript",
                "required": True,
                "source_type": "transcript",
                "source_ref": "transcript_artifact",
                "captured_at": "2026-04-18T00:00:00Z",
                "content_hash": "h1",
                "statements": [{"topic": "deployment", "polarity": "affirm", "text": "yes"}],
                "provenance": {"source_uri": "artifact://t", "source_system": "wpg", "collected_by": "t", "collected_at": "2026-04-18T00:00:00Z", "attribution": "t"},
            },
            {
                "component_type": "meeting_minutes",
                "required": True,
                "source_type": "meeting_minutes",
                "source_ref": "meeting_minutes_artifact",
                "captured_at": "2026-04-18T00:00:00Z",
                "content_hash": "h2",
                "provenance": {"source_uri": "artifact://m", "source_system": "wpg", "collected_by": "t", "collected_at": "2026-04-18T00:00:00Z", "attribution": "m"},
            },
            {
                "component_type": "slides",
                "required": True,
                "source_type": "slides",
                "source_ref": "slides_artifact",
                "captured_at": "2026-04-18T00:00:00Z",
                "content_hash": "h3",
                "provenance": {"source_uri": "artifact://s", "source_system": "wpg", "collected_by": "t", "collected_at": "2026-04-18T00:00:00Z", "attribution": "s"},
            },
            {
                "component_type": "critique_artifacts",
                "required": True,
                "source_type": "critique_artifacts",
                "source_ref": "critique_artifact",
                "captured_at": "2026-04-18T00:00:00Z",
                "content_hash": "h4",
                "statements": [{"topic": "deployment", "polarity": "deny", "text": "no"}],
                "provenance": {"source_uri": "artifact://c", "source_system": "wpg", "collected_by": "t", "collected_at": "2026-04-18T00:00:00Z", "attribution": "c"},
            },
            {
                "component_type": "prior_wpg_outputs",
                "required": True,
                "source_type": "prior_wpg_outputs",
                "source_ref": "prior",
                "captured_at": "2026-04-18T00:00:00Z",
                "content_hash": "h5",
                "provenance": {"source_uri": "artifact://p", "source_system": "wpg", "collected_by": "t", "collected_at": "2026-04-18T00:00:00Z", "attribution": "p"},
            },
            {
                "component_type": "eval_outputs",
                "required": True,
                "source_type": "eval_outputs",
                "source_ref": "eval",
                "captured_at": "2026-04-18T00:00:00Z",
                "content_hash": "h6",
                "provenance": {"source_uri": "artifact://e", "source_system": "wpg", "collected_by": "t", "collected_at": "2026-04-18T00:00:00Z", "attribution": "e"},
            },
        ],
    }
    result = evaluate_context_admission(bundle, now=datetime(2026, 4, 18, tzinfo=timezone.utc))
    assert result["admission_status"] == "fail"
    assert result["enforcement_action"] == "BLOCK"
    assert "unresolved_context_contradiction" in result["blocking_reasons"]
