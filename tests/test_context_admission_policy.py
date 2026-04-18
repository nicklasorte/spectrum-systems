from __future__ import annotations

from datetime import datetime, timezone

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.wpg.context_governance import evaluate_context_admission


def _bundle() -> dict:
    return {
        "artifact_type": "context_bundle_artifact",
        "schema_version": "1.0.0",
        "context_bundle_id": "ctxb-001",
        "trace": {"trace_id": "trace-1", "run_id": "run-1"},
        "created_at": "2026-04-18T00:00:00Z",
        "components": [
            {
                "component_type": "transcript",
                "required": True,
                "source_type": "transcript",
                "source_ref": "transcript_artifact",
                "captured_at": "2026-04-18T00:00:00Z",
                "content_hash": "h1",
                "provenance": {
                    "source_uri": "artifact://transcript_artifact",
                    "source_system": "wpg",
                    "collected_by": "test",
                    "collected_at": "2026-04-18T00:00:00Z",
                    "attribution": "transcript_artifact",
                },
            },
            {
                "component_type": "meeting_minutes",
                "required": True,
                "source_type": "meeting_minutes",
                "source_ref": "meeting_minutes_artifact",
                "captured_at": "2026-04-18T00:00:00Z",
                "content_hash": "h2",
                "provenance": {
                    "source_uri": "artifact://meeting_minutes_artifact",
                    "source_system": "wpg",
                    "collected_by": "test",
                    "collected_at": "2026-04-18T00:00:00Z",
                    "attribution": "meeting_minutes_artifact",
                },
            },
            {
                "component_type": "slides",
                "required": True,
                "source_type": "slides",
                "source_ref": "slides_artifact",
                "captured_at": "2026-04-18T00:00:00Z",
                "content_hash": "h3",
                "provenance": {
                    "source_uri": "artifact://slides_artifact",
                    "source_system": "wpg",
                    "collected_by": "test",
                    "collected_at": "2026-04-18T00:00:00Z",
                    "attribution": "slides_artifact",
                },
            },
            {
                "component_type": "critique_artifacts",
                "required": True,
                "source_type": "critique_artifacts",
                "source_ref": "critique_artifact",
                "captured_at": "2026-04-18T00:00:00Z",
                "content_hash": "h4",
                "provenance": {
                    "source_uri": "artifact://critique_artifact",
                    "source_system": "wpg",
                    "collected_by": "test",
                    "collected_at": "2026-04-18T00:00:00Z",
                    "attribution": "critique_artifact",
                },
            },
            {
                "component_type": "prior_wpg_outputs",
                "required": True,
                "source_type": "prior_wpg_outputs",
                "source_ref": "prior_output",
                "captured_at": "2026-04-10T00:00:00Z",
                "content_hash": "h5",
                "provenance": {
                    "source_uri": "artifact://prior_output",
                    "source_system": "wpg",
                    "collected_by": "test",
                    "collected_at": "2026-04-10T00:00:00Z",
                    "attribution": "prior_output",
                },
            },
            {
                "component_type": "eval_outputs",
                "required": True,
                "source_type": "eval_outputs",
                "source_ref": "eval_output",
                "captured_at": "2026-04-18T00:00:00Z",
                "content_hash": "h6",
                "provenance": {
                    "source_uri": "artifact://eval_output",
                    "source_system": "wpg",
                    "collected_by": "test",
                    "collected_at": "2026-04-18T00:00:00Z",
                    "attribution": "eval_output",
                },
            },
        ],
    }


def test_context_admission_result_example_validates() -> None:
    validate_artifact(load_example("context_admission_result"), "context_admission_result")


def test_context_admission_policy_passes_for_complete_fresh_traceable_bundle() -> None:
    result = evaluate_context_admission(_bundle(), now=datetime(2026, 4, 18, tzinfo=timezone.utc))
    assert result["admission_status"] == "pass"
    assert result["enforcement_action"] == "ALLOW"


def test_context_admission_policy_freezes_for_stale_critical_source() -> None:
    bundle = _bundle()
    bundle["components"][0]["captured_at"] = "2026-04-10T00:00:00Z"
    result = evaluate_context_admission(bundle, now=datetime(2026, 4, 18, tzinfo=timezone.utc))
    assert result["admission_status"] == "fail"
    assert result["enforcement_action"] == "FREEZE"
