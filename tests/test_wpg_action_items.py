from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline
from tests.wpg_context_helpers import build_complete_context_bundle

FIXTURE = Path("tests/fixtures/wpg/sample_workflow_loop_input.json")


def test_wpg33_action_items_structured_and_traceable() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bundle = run_wpg_pipeline(
        payload["transcript"],
        run_id="actions",
        trace_id="actions",
        meeting_artifact=payload["meeting_artifact"],
        context_bundle_artifact=build_complete_context_bundle(trace_id="actions", run_id="actions"),
    )
    actions = bundle["artifact_chain"]["action_item_artifact"]["outputs"]
    assert isinstance(actions["action_items"], list)
    assert actions["explicit_empty"] is False
    assert all("action_id" in item for item in actions["action_items"])
