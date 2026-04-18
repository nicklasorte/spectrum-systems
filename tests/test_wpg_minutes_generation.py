from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline
from tests.wpg_context_helpers import build_complete_context_bundle

FIXTURE = Path("tests/fixtures/wpg/sample_workflow_loop_input.json")


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_wpg32_minutes_generation_has_required_sections() -> None:
    payload = _payload()
    bundle = run_wpg_pipeline(
        payload["transcript"],
        run_id="minutes",
        trace_id="minutes",
        meeting_artifact=payload["meeting_artifact"],
        context_bundle_artifact=build_complete_context_bundle(trace_id="minutes", run_id="minutes"),
    )
    minutes = bundle["artifact_chain"]["meeting_minutes_artifact"]
    assert minutes["outputs"]["summary"]
    assert minutes["outputs"]["decisions"]
    assert minutes["outputs"]["open_questions"]
    assert minutes["evaluation_refs"]["control_decision"]["decision"] in {"ALLOW", "WARN", "BLOCK", "FREEZE"}
