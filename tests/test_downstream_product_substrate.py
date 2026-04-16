from __future__ import annotations

import zipfile
from pathlib import Path

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.downstream_product_substrate import (
    DownstreamFailClosedError,
    assemble_meeting_context_bundle,
    build_eval_summary,
    build_meeting_intelligence,
    certify_product_readiness,
    control_decision,
    extract_transcript_facts,
    normalize_docx_transcript,
    required_eval_suite,
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
        "[09:05:00] Bob: We should publish weekly risk status",
        "Unattributed note without clear speaker",
    ])

    ingest = normalize_docx_transcript(
        source_docx_path=str(docx),
        source_id="SRC-001",
        run_id="run-rdm-01",
        trace_id="trace-rdm-01",
        parser_version="docx-normalizer-1.0.0",
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


def test_fail_closed_on_missing_required_eval_and_trace() -> None:
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
    assert "missing_required_eval" in readiness["blocking_reasons"]
    validate_artifact(readiness, "product_readiness_artifact")


def test_fail_closed_on_malformed_source_input(tmp_path: Path) -> None:
    bad = tmp_path / "meeting.txt"
    bad.write_text("not a docx", encoding="utf-8")

    try:
        normalize_docx_transcript(
            source_docx_path=str(bad),
            source_id="SRC-002",
            run_id="run-rdm-01",
            trace_id="trace-rdm-01",
            parser_version="docx-normalizer-1.0.0",
        )
    except DownstreamFailClosedError as exc:
        assert "docx" in str(exc)
    else:
        raise AssertionError("expected DownstreamFailClosedError")
