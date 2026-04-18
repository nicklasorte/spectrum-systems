from __future__ import annotations

from datetime import datetime, timezone

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.wpg.context_governance import build_context_bundle_artifact, evaluate_context_admission


def test_context_bundle_artifact_example_validates() -> None:
    validate_artifact(load_example("context_bundle_artifact"), "context_bundle_artifact")


def test_context_bundle_artifact_blocks_when_required_component_missing() -> None:
    bundle = build_context_bundle_artifact(
        trace_id="trace-ctx-001",
        run_id="run-ctx-001",
        components={
            "transcript": {"content": {"segments": []}},
        },
        created_at="2026-04-18T00:00:00Z",
    )
    bundle["components"] = [c for c in bundle["components"] if c["component_type"] != "slides"]
    result = evaluate_context_admission(bundle, now=datetime(2026, 4, 18, tzinfo=timezone.utc))
    assert result["admission_status"] == "fail"
    assert "missing_required_component:slides" in result["blocking_reasons"]
