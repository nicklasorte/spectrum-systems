from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline, run_wpg_pipeline_from_file


FIXTURE = Path("tests/fixtures/wpg/sample_transcript.json")


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_pipeline_outputs_all_artifacts() -> None:
    payload = _load()
    bundle = run_wpg_pipeline(
        payload["transcript"],
        run_id=payload["run_id"],
        trace_id=payload["trace_id"],
        mode="working_paper",
        resolved_comments=payload["resolved_comments"],
    )
    expected = {
        "question_set_artifact",
        "faq_artifact",
        "faq_report_artifact",
        "faq_cluster_artifact",
        "faq_conflict_artifact",
        "faq_confidence_artifact",
        "working_section_artifact",
        "working_paper_artifact",
        "unknowns_artifact",
        "wpg_delta_artifact",
    }
    assert expected.issubset(bundle["artifact_chain"].keys())


def test_replay_is_deterministic() -> None:
    payload = _load()
    a = run_wpg_pipeline(payload["transcript"], run_id="r1", trace_id="t1", mode="working_paper")
    b = run_wpg_pipeline(payload["transcript"], run_id="r1", trace_id="t1", mode="working_paper")
    assert a["replay"]["signature"] == b["replay"]["signature"]


def test_output_modes_supported() -> None:
    payload = _load()
    for mode in ("working_paper", "executive_summary", "FAQ_brief", "slide_outline"):
        bundle = run_wpg_pipeline(payload["transcript"], run_id="r2", trace_id=f"t-{mode}", mode=mode)
        assert bundle["artifact_chain"]["working_paper_artifact"]["outputs"]["mode"] == mode


def test_control_and_enforcement_on_each_stage() -> None:
    payload = _load()
    bundle = run_wpg_pipeline(payload["transcript"], run_id="r3", trace_id="t3")
    for artifact in bundle["artifact_chain"].values():
        decision = artifact.get("evaluation_refs", {}).get("control_decision")
        if not decision:
            continue
        assert decision["decision"] in {"ALLOW", "WARN", "BLOCK", "FREEZE"}
        assert decision["enforcement"]["action"] in {"proceed", "annotate", "trigger_repair", "halt"}


def test_confidence_and_unknowns_present() -> None:
    payload = _load()
    bundle = run_wpg_pipeline(payload["transcript"], run_id="r4", trace_id="t4")
    confidence = bundle["artifact_chain"]["faq_confidence_artifact"]["outputs"]["confidence_rows"]
    unknowns = bundle["artifact_chain"]["unknowns_artifact"]["outputs"]["unknowns"]
    assert confidence
    assert unknowns


def test_cli_runner_writes_artifacts(tmp_path: Path) -> None:
    bundle = run_wpg_pipeline_from_file(FIXTURE, tmp_path)
    assert (tmp_path / "wpg_pipeline_bundle.json").is_file()
    assert bundle["artifact_chain"]["working_paper_artifact"]["artifact_type"] == "working_paper_artifact"
