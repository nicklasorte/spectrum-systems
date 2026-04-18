from __future__ import annotations


def build_complete_context_bundle(*, trace_id: str, run_id: str) -> dict:
    return {
        "artifact_type": "context_bundle_artifact",
        "schema_version": "1.0.0",
        "context_bundle_id": f"ctxb-{run_id}",
        "trace": {"trace_id": trace_id, "run_id": run_id},
        "created_at": "2026-04-18T00:00:00Z",
        "components": [
            {"component_type": "transcript", "required": True, "source_type": "transcript", "source_ref": "transcript_artifact", "captured_at": "2026-04-18T00:00:00Z", "content_hash": "h1", "provenance": {"source_uri": "artifact://transcript_artifact", "source_system": "wpg", "collected_by": "test", "collected_at": "2026-04-18T00:00:00Z", "attribution": "transcript_artifact"}},
            {"component_type": "meeting_minutes", "required": True, "source_type": "meeting_minutes", "source_ref": "meeting_minutes_artifact", "captured_at": "2026-04-18T00:00:00Z", "content_hash": "h2", "provenance": {"source_uri": "artifact://meeting_minutes_artifact", "source_system": "wpg", "collected_by": "test", "collected_at": "2026-04-18T00:00:00Z", "attribution": "meeting_minutes_artifact"}},
            {"component_type": "slides", "required": True, "source_type": "slides", "source_ref": "slides_artifact", "captured_at": "2026-04-18T00:00:00Z", "content_hash": "h3", "provenance": {"source_uri": "artifact://slides_artifact", "source_system": "wpg", "collected_by": "test", "collected_at": "2026-04-18T00:00:00Z", "attribution": "slides_artifact"}},
            {"component_type": "critique_artifacts", "required": True, "source_type": "critique_artifacts", "source_ref": "critique_artifact", "captured_at": "2026-04-18T00:00:00Z", "content_hash": "h4", "provenance": {"source_uri": "artifact://critique_artifact", "source_system": "wpg", "collected_by": "test", "collected_at": "2026-04-18T00:00:00Z", "attribution": "critique_artifact"}},
            {"component_type": "prior_wpg_outputs", "required": True, "source_type": "prior_wpg_outputs", "source_ref": "prior_working_paper_artifact", "captured_at": "2026-04-18T00:00:00Z", "content_hash": "h5", "provenance": {"source_uri": "artifact://prior_working_paper_artifact", "source_system": "wpg", "collected_by": "test", "collected_at": "2026-04-18T00:00:00Z", "attribution": "prior_working_paper_artifact"}},
            {"component_type": "eval_outputs", "required": True, "source_type": "eval_outputs", "source_ref": "eval_outputs_artifact", "captured_at": "2026-04-18T00:00:00Z", "content_hash": "h6", "provenance": {"source_uri": "artifact://eval_outputs_artifact", "source_system": "wpg", "collected_by": "test", "collected_at": "2026-04-18T00:00:00Z", "attribution": "eval_outputs_artifact"}},
        ],
    }
