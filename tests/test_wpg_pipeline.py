from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.wpg.redteam import run_wpg_redteam_suite
from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline, run_wpg_pipeline_from_file
from tests.wpg_context_helpers import build_complete_context_bundle


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
        context_bundle_artifact=build_complete_context_bundle(trace_id=payload["trace_id"], run_id=payload["run_id"]),
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
        "wpg_grounding_eval_case",
        "wpg_contradiction_propagation_record",
        "wpg_uncertainty_control_record",
        "narrative_integrity_record",
    }
    assert expected.issubset(bundle["artifact_chain"].keys())


def test_replay_is_deterministic() -> None:
    payload = _load()
    context = build_complete_context_bundle(trace_id="t1", run_id="r1")
    a = run_wpg_pipeline(payload["transcript"], run_id="r1", trace_id="t1", mode="working_paper", context_bundle_artifact=context)
    b = run_wpg_pipeline(payload["transcript"], run_id="r1", trace_id="t1", mode="working_paper", context_bundle_artifact=context)
    assert a["replay"]["signature"] == b["replay"]["signature"]


def test_output_modes_supported() -> None:
    payload = _load()
    for mode in ("working_paper", "executive_summary", "FAQ_brief", "slide_outline"):
        bundle = run_wpg_pipeline(
            payload["transcript"],
            run_id="r2",
            trace_id=f"t-{mode}",
            mode=mode,
            context_bundle_artifact=build_complete_context_bundle(trace_id=f"t-{mode}", run_id="r2"),
        )
        assert bundle["artifact_chain"]["working_paper_artifact"]["outputs"]["mode"] == mode


def test_control_and_enforcement_on_each_stage() -> None:
    payload = _load()
    bundle = run_wpg_pipeline(payload["transcript"], run_id="r3", trace_id="t3", context_bundle_artifact=build_complete_context_bundle(trace_id="t3", run_id="r3"))
    for artifact in bundle["artifact_chain"].values():
        if "evaluation_refs" not in artifact:
            continue
        decision = artifact["evaluation_refs"]["control_decision"]
        assert decision["decision"] in {"ALLOW", "WARN", "BLOCK", "FREEZE"}
        assert decision["enforcement"]["action"] in {"proceed", "annotate", "trigger_repair", "halt"}


def test_confidence_and_unknowns_present() -> None:
    payload = _load()
    bundle = run_wpg_pipeline(payload["transcript"], run_id="r4", trace_id="t4", context_bundle_artifact=build_complete_context_bundle(trace_id="t4", run_id="r4"))
    confidence = bundle["artifact_chain"]["faq_confidence_artifact"]["outputs"]["confidence_rows"]
    unknowns = bundle["artifact_chain"]["unknowns_artifact"]["outputs"]["unknowns"]
    assert confidence
    assert unknowns


def test_unknown_input_cannot_allow_with_full_confidence() -> None:
    bundle = run_wpg_pipeline(
        {"segments": [{"segment_id": "u-1", "speaker": "Ops", "agency": "NOAA", "text": "When does this complete? Unknown pending validation."}]},
        run_id="r-unknown",
        trace_id="t-unknown",
        context_bundle_artifact=build_complete_context_bundle(trace_id="t-unknown", run_id="r-unknown"),
    )
    rows = bundle["artifact_chain"]["faq_confidence_artifact"]["outputs"]["confidence_rows"]
    assert rows[0]["unknown"] is True
    assert rows[0]["confidence"] < 1.0
    assert bundle["artifact_chain"]["faq_artifact"]["evaluation_refs"]["control_decision"]["decision"] != "ALLOW"


def test_semantic_conflict_detection_non_empty() -> None:
    transcript = {
        "segments": [
            {"segment_id": "c-1", "speaker": "A", "agency": "FAA", "text": "Can deployment start now? Yes deployment can start now."},
            {"segment_id": "c-2", "speaker": "B", "agency": "DoD", "text": "Can deployment start now? No deployment cannot start now."},
        ]
    }
    bundle = run_wpg_pipeline(
        transcript,
        run_id="r-conflict",
        trace_id="t-conflict",
        context_bundle_artifact=build_complete_context_bundle(trace_id="t-conflict", run_id="r-conflict"),
    )
    conflicts = bundle["artifact_chain"]["faq_conflict_artifact"]["outputs"]["conflicts"]
    assert conflicts


def test_invalid_transcript_is_blocked() -> None:
    with pytest.raises(Exception):
        run_wpg_pipeline({"segments": [{"segment_id": "bad", "speaker": "A"}]}, run_id="r-bad", trace_id="t-bad")


def test_narrative_order_has_justification() -> None:
    payload = _load()
    bundle = run_wpg_pipeline(payload["transcript"], run_id="r5", trace_id="t5", context_bundle_artifact=build_complete_context_bundle(trace_id="t5", run_id="r5"))
    sections = bundle["artifact_chain"]["working_section_artifact"]["outputs"]["sections"]
    assert all(section.get("chronology", {}).get("justification") for section in sections)


def test_delta_identical_input_same_hash() -> None:
    payload = _load()
    first = run_wpg_pipeline(payload["transcript"], run_id="r6", trace_id="t6", context_bundle_artifact=build_complete_context_bundle(trace_id="t6", run_id="r6"))
    prior = first["artifact_chain"]["working_paper_artifact"]
    second = run_wpg_pipeline(
        payload["transcript"],
        run_id="r6",
        trace_id="t6",
        prior_working_paper=prior,
        context_bundle_artifact=build_complete_context_bundle(trace_id="t6", run_id="r6"),
    )
    delta = second["artifact_chain"]["wpg_delta_artifact"]["outputs"]
    assert delta["previous_hash"] == delta["current_hash"]
    assert delta["changed"] is False




def test_transcript_ingress_deterministic_identity() -> None:
    payload = _load()
    context = build_complete_context_bundle(trace_id="t-ident", run_id="r-ident")
    a = run_wpg_pipeline(payload["transcript"], run_id="r-ident", trace_id="t-ident", context_bundle_artifact=context)
    b = run_wpg_pipeline(payload["transcript"], run_id="r-ident", trace_id="t-ident", context_bundle_artifact=context)
    assert a["artifact_chain"]["transcript_artifact"]["outputs"]["artifact_id"] == b["artifact_chain"]["transcript_artifact"]["outputs"]["artifact_id"]


def test_phase_a_assurance_artifacts_emitted() -> None:
    payload = _load()
    bundle = run_wpg_pipeline(payload["transcript"], run_id="r-assure", trace_id="t-assure", context_bundle_artifact=build_complete_context_bundle(trace_id="t-assure", run_id="r-assure"))
    assert bundle["artifact_chain"]["wpg_grounding_eval_case"]["outputs"]["supported_claim_ratio"] >= 0.0
    assert bundle["artifact_chain"]["wpg_uncertainty_control_record"]["outputs"]["narrative_warning_present"] is True

def test_rtx05_redteam_has_no_high_green_proceed() -> None:
    findings = run_wpg_redteam_suite()
    assert all(
        not (entry["severity"] == "HIGH" and entry["control_outcome"] == "proceed")
        for entry in findings["findings"]
    )


def test_cli_runner_writes_artifacts(tmp_path: Path) -> None:
    bundle = run_wpg_pipeline_from_file(FIXTURE, tmp_path)
    assert (tmp_path / "wpg_pipeline_bundle.json").is_file()
    assert bundle["artifact_chain"]["working_paper_artifact"]["artifact_type"] == "working_paper_artifact"


def test_pipeline_blocks_when_required_context_slides_missing() -> None:
    payload = _load()
    context = build_complete_context_bundle(trace_id="t-missing-slides", run_id="r-missing-slides")
    context["components"] = [c for c in context["components"] if c["component_type"] != "slides"]
    with pytest.raises(Exception, match="context admission blocked pipeline execution"):
        run_wpg_pipeline(payload["transcript"], run_id="r-missing-slides", trace_id="t-missing-slides", context_bundle_artifact=context)


def test_pipeline_blocks_when_required_context_critique_missing() -> None:
    payload = _load()
    context = build_complete_context_bundle(trace_id="t-missing-critique", run_id="r-missing-critique")
    context["components"] = [c for c in context["components"] if c["component_type"] != "critique_artifacts"]
    with pytest.raises(Exception, match="context admission blocked pipeline execution"):
        run_wpg_pipeline(payload["transcript"], run_id="r-missing-critique", trace_id="t-missing-critique", context_bundle_artifact=context)
