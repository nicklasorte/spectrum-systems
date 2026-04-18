from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline
from tests.wpg_context_helpers import build_complete_context_bundle

FIXTURE = Path("tests/fixtures/wpg/sample_workflow_loop_input.json")


def test_crm11_revision_application_controlled_and_replayable() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bundle = run_wpg_pipeline(
        payload["transcript"],
        run_id="crm-apply",
        trace_id="crm-apply",
        meeting_artifact=payload["meeting_artifact"],
        comment_artifact=payload["comment_artifact"],
        context_bundle_artifact=build_complete_context_bundle(trace_id="crm-apply", run_id="crm-apply"),
    )
    applied = bundle["artifact_chain"]["revision_application_record"]
    assert "revised_content" in applied["outputs"]
    assert applied["evaluation_refs"]["control_decision"]["decision"] in {"ALLOW", "WARN", "BLOCK", "FREEZE"}
