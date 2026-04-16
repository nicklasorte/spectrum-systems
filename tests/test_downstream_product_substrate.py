from __future__ import annotations

import zipfile
from pathlib import Path

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.downstream_product_substrate import (
    DownstreamFailClosedError,
    apply_policy_thresholds,
    assemble_meeting_context_bundle,
    assess_capacity_and_burst,
    build_eval_summary,
    build_failure_artifact,
    build_meeting_intelligence,
    build_operability_report,
    build_chaos_scenarios,
    certify_product_readiness,
    control_decision,
    derive_review_triggers,
    detect_transcript_drift,
    extract_transcript_facts,
    normalize_docx_transcript,
    required_eval_suite,
    run_multi_pass_extraction,
    run_transcript_eval_suite,
    verify_replay_integrity,
)


def _write_docx(path: Path, lines: list[str]) -> None:
    xml_lines = "".join(f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in lines)
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{xml_lines}</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", xml)


def test_rdm01_pipeline_artifacts_validate(tmp_path: Path) -> None:
    docx = tmp_path / "meeting.docx"
    _write_docx(docx, [
        "[09:00:00] Alice: Kickoff governance review",
        "[09:05:00] Bob: We adopt weekly risk status",
        "Unattributed note without clear speaker",
    ])

    ingest = normalize_docx_transcript(
        source_docx_path=str(docx),
        source_id="SRC-001",
        run_id="run-rdm-01",
        trace_id="trace-rdm-01",
        parser_version="docx-normalizer-1.1.0",
        chunk_size=2,
        ingest_timestamp="2026-04-16T00:00:00Z",
    )
    validate_artifact(ingest["raw_meeting_record_artifact"], "raw_meeting_record_artifact")
    validate_artifact(ingest["normalized_transcript_artifact"], "normalized_transcript_artifact")
    for chunk in ingest["transcript_chunk_artifacts"]:
        validate_artifact(chunk, "transcript_chunk_artifact")

    facts = extract_transcript_facts(ingest["normalized_transcript_artifact"])
    validate_artifact(facts, "transcript_fact_artifact")
    intelligence = build_meeting_intelligence(facts)
    for artifact_type, payloads in intelligence.items():
        for payload in payloads:
            validate_artifact(payload, artifact_type)

    context = assemble_meeting_context_bundle(
        run_id="run-rdm-01",
        trace_id="trace-rdm-01",
        included_artifacts=[ingest["normalized_transcript_artifact"], facts],
        excluded_refs=["raw:SRC-legacy"],
        recipe_version="recipe-1.0.0",
    )
    validate_artifact(context, "meeting_context_bundle")


def test_deterministic_replay_and_multi_pass(tmp_path: Path) -> None:
    docx = tmp_path / "meeting.docx"
    _write_docx(docx, [
        "[10:00:00] Alice: Decision approved",
        "[10:01:00] Bob: Decision not approved",
        "Charlie: owner action required",
    ])
    first = normalize_docx_transcript(
        source_docx_path=str(docx),
        source_id="SRC-DET",
        run_id="run-det",
        trace_id="trace-det",
        parser_version="docx-normalizer-1.1.0",
        ingest_timestamp="2026-04-16T00:00:00Z",
    )
    second = normalize_docx_transcript(
        source_docx_path=str(docx),
        source_id="SRC-DET",
        run_id="run-det",
        trace_id="trace-det",
        parser_version="docx-normalizer-1.1.0",
        ingest_timestamp="2026-04-16T00:00:00Z",
    )
    assert first == second

    replay = verify_replay_integrity(
        artifact=first["normalized_transcript_artifact"],
        replay_artifact=second["normalized_transcript_artifact"],
    )
    assert replay["match"] is True

    passes = run_multi_pass_extraction(
        normalized_transcript=first["normalized_transcript_artifact"],
        chunk_artifacts=first["transcript_chunk_artifacts"],
        model_id="governed-sim-model",
        prompt_version="trn-01.1",
    )
    assert len(passes["passes"]) == 5
    assert passes["outputs"]["pass5"]["synthesis"]["contradiction_count"] >= 1


def test_eval_policy_review_and_certification_gate() -> None:
    eval_summary = build_eval_summary(required_eval_suite(), {"schema_conformance": "pass"})
    control = control_decision(eval_summary, trace_complete=False, replay_match=True)
    readiness = certify_product_readiness(
        artifact_refs=["MEETING_INTELLIGENCE_PACKET-001"],
        eval_summary=eval_summary,
        control=control,
        replay_linkage=False,
        trace_complete=False,
    )
    assert eval_summary["status"] == "block"
    assert control["decision"] == "block"
    assert readiness["certification_status"] == "blocked"

    thresholds = apply_policy_thresholds(
        evidence_coverage=0.8,
        ambiguity_rate=0.4,
        contradiction_rate=0.1,
        replay_match_rate=1.0,
        completed_required_evals=False,
    )
    assert thresholds["status"] == "block"

    review = derive_review_triggers(
        ambiguity_rate=0.5,
        contradiction_density=0.3,
        missing_material_evidence=1,
        policy_conflict=True,
        replay_anomalies=1,
        high_risk_outputs=1,
    )
    assert review["requires_human_review"] is True


def test_eval_suite_observability_drift_capacity() -> None:
    normalized = {
        "lines": [
            {"speaker": "ALICE", "timestamp": "09:00:00", "ambiguity_flags": [], "line_id": "LINE-0001", "text": "x", "confidence": 0.9},
            {"speaker": "UNKNOWN", "timestamp": None, "ambiguity_flags": ["unknown_speaker"], "line_id": "LINE-0002", "text": "y", "confidence": 0.4},
        ]
    }
    pass_bundle = {"outputs": {"pass5": {"synthesis": {"evidence_coverage": 1.0, "contradiction_count": 0}}}}
    evals = run_transcript_eval_suite(
        run_id="run-1",
        trace_id="trace-1",
        normalized=normalized,
        pass_bundle=pass_bundle,
        replay_match=True,
    )
    assert evals["schema_conformance"] == "pass"

    report = build_operability_report({"parse_success_rate": 1.0, "review_queue_volume": 7})
    assert report["parse_success_rate"] == 1.0

    drift = detect_transcript_drift(
        baseline={"ambiguity_rate": 0.1, "evidence_coverage": 0.98},
        current={"ambiguity_rate": 0.5, "evidence_coverage": 0.8},
    )
    assert drift["freeze_required"] is True

    capacity = assess_capacity_and_burst(
        queue_depth=200,
        backlog_age_minutes=60,
        timeout_rate=0.2,
        retry_rate=0.5,
        concurrency=40,
    )
    assert capacity["status"] == "degraded"


def test_fail_closed_on_malformed_source_input_and_chaos_registry(tmp_path: Path) -> None:
    bad = tmp_path / "meeting.txt"
    bad.write_text("not a docx", encoding="utf-8")

    try:
        normalize_docx_transcript(
            source_docx_path=str(bad),
            source_id="SRC-002",
            run_id="run-rdm-01",
            trace_id="trace-rdm-01",
            parser_version="docx-normalizer-1.1.0",
        )
    except DownstreamFailClosedError as exc:
        failure = build_failure_artifact(
            source_id="SRC-002",
            run_id="run-rdm-01",
            trace_id="trace-rdm-01",
            parser_version="docx-normalizer-1.1.0",
            reason=str(exc),
        )
        assert failure["artifact_type"] == "transcript_ingest_failure_artifact"
    else:
        raise AssertionError("expected DownstreamFailClosedError")

    scenarios = build_chaos_scenarios()
    assert len(scenarios) == 9
