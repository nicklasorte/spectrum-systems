from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline
from tests.wpg_context_helpers import build_complete_context_bundle

FIXTURE = Path("tests/fixtures/wpg/sample_workflow_loop_input.json")


def test_crm10_revision_plan_generated_before_execution() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bundle = run_wpg_pipeline(
        payload["transcript"],
        run_id="crm-plan",
        trace_id="crm-plan",
        meeting_artifact=payload["meeting_artifact"],
        comment_artifact=payload["comment_artifact"],
        context_bundle_artifact=build_complete_context_bundle(trace_id="crm-plan", run_id="crm-plan"),
    )
    plan = bundle["artifact_chain"]["revision_plan_artifact"]
    assert isinstance(plan["outputs"]["tasks"], list)
