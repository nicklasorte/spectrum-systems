from __future__ import annotations

from datetime import datetime, timezone

from spectrum_systems.modules.wpg.context_governance import evaluate_context_admission


def _base_component(component_type: str) -> dict:
    return {
        "component_type": component_type,
        "required": True,
        "source_type": component_type,
        "source_ref": f"{component_type}_artifact",
        "captured_at": "2026-04-18T00:00:00Z",
        "content_hash": "hash",
        "provenance": {
            "source_uri": f"artifact://{component_type}",
            "source_system": "wpg",
            "collected_by": "test",
            "collected_at": "2026-04-18T00:00:00Z",
            "attribution": component_type,
        },
    }


def test_context_regressions_repeated_missing_source_failure_remains_blocking() -> None:
    components = [
        _base_component("transcript"),
        _base_component("meeting_minutes"),
        _base_component("slides"),
        _base_component("critique_artifacts"),
        _base_component("prior_wpg_outputs"),
        _base_component("eval_outputs"),
    ]
    bundle = {
        "artifact_type": "context_bundle_artifact",
        "schema_version": "1.0.0",
        "context_bundle_id": "ctxb-r1",
        "trace": {"trace_id": "trace-r1", "run_id": "run-r1"},
        "created_at": "2026-04-18T00:00:00Z",
        "components": [c for c in components if c["component_type"] != "eval_outputs"],
    }
    first = evaluate_context_admission(bundle, now=datetime(2026, 4, 18, tzinfo=timezone.utc))
    second = evaluate_context_admission(bundle, now=datetime(2026, 4, 18, tzinfo=timezone.utc))

    assert first["enforcement_action"] == "BLOCK"
    assert second["enforcement_action"] == "BLOCK"
    assert "missing_required_component:eval_outputs" in second["blocking_reasons"]


def test_context_regressions_placeholder_source_failure_remains_blocking() -> None:
    components = [
        _base_component("transcript"),
        _base_component("meeting_minutes"),
        _base_component("slides"),
        _base_component("critique_artifacts"),
        _base_component("prior_wpg_outputs"),
        _base_component("eval_outputs"),
    ]
    for item in components:
        if item["component_type"] == "critique_artifacts":
            item["source_ref"] = "critique_artifacts_input"
            item["provenance"]["source_uri"] = "artifact://critique_artifacts_input"
    bundle = {
        "artifact_type": "context_bundle_artifact",
        "schema_version": "1.0.0",
        "context_bundle_id": "ctxb-r2",
        "trace": {"trace_id": "trace-r2", "run_id": "run-r2"},
        "created_at": "2026-04-18T00:00:00Z",
        "components": components,
    }
    result = evaluate_context_admission(bundle, now=datetime(2026, 4, 18, tzinfo=timezone.utc))
    assert result["enforcement_action"] == "BLOCK"
    assert "missing_required_component:critique_artifacts" in result["blocking_reasons"]
