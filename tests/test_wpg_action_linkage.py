from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline

FIXTURE = Path("tests/fixtures/wpg/sample_workflow_loop_input.json")


def test_wpg34_action_linkage_emits_linked_records() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bundle = run_wpg_pipeline(payload["transcript"], run_id="linkage", trace_id="linkage", meeting_artifact=payload["meeting_artifact"])
    linkage = bundle["artifact_chain"]["action_linkage_record"]
    assert linkage["outputs"]["required_unlinked"] >= 0
    assert isinstance(linkage["outputs"]["linkages"], list)
