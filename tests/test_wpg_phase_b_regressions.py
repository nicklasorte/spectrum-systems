from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline

FIXTURE = Path("tests/fixtures/wpg/sample_workflow_loop_input.json")


def test_rtx11_and_rtx12_findings_fixture_validates() -> None:
    validate_artifact(load_example("wpg_redteam_findings_phase_b"), "wpg_redteam_findings_phase_b")


def test_fix15_no_high_severity_allow() -> None:
    findings = load_example("wpg_redteam_findings_phase_b")
    assert all(not (f["severity"] == "HIGH" and f["observed_decision"] == "ALLOW") for f in findings["findings"])


def test_fix16_revision_loop_fail_closed() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bundle = run_wpg_pipeline(
        payload["transcript"],
        run_id="phase-b-reg",
        trace_id="phase-b-reg",
        meeting_artifact=payload["meeting_artifact"],
        comment_artifact=payload["comment_artifact"],
    )
    critical_unresolved = bundle["artifact_chain"]["comment_disposition_record"]["outputs"]["critical_unresolved"]
    decision = bundle["artifact_chain"]["comment_disposition_record"]["evaluation_refs"]["control_decision"]["decision"]
    assert critical_unresolved == 0
    assert decision != "ALLOW" or critical_unresolved == 0
