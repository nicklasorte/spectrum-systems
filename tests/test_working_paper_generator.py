"""
Tests for the working_paper_generator module and the run_working_paper_generator CLI.

Covers:
  - transcript_parser: basic parsing, speaker detection, segment tagging
  - paper_state_reader: JSON and plain-text input formats
  - meeting_delta_engine: new topics, updated sections, unresolved/consensus items
  - argument_builder: argument extraction and stance inference
  - question_engine: question detection and resolution inference
  - readiness_scorer: section score calculation, overall readiness flag
  - patch_generator: update and add patch operations
  - draft_writer: patch application, section versioning, scaffolding from scratch
  - CLI: help flag, JSON output, Markdown output, missing-argument error
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WPG_DIR = REPO_ROOT / "working_paper_generator"
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_working_paper_generator.py"
SAMPLE_TRANSCRIPT = REPO_ROOT / "examples" / "example-transcript.txt"

sys.path.insert(0, str(REPO_ROOT))

from working_paper_generator.transcript_parser import parse_transcript  # noqa: E402
from working_paper_generator.paper_state_reader import read_paper_state  # noqa: E402
from working_paper_generator.meeting_delta_engine import compute_delta  # noqa: E402
from working_paper_generator.argument_builder import build_arguments  # noqa: E402
from working_paper_generator.question_engine import extract_questions  # noqa: E402
from working_paper_generator.readiness_scorer import score_readiness  # noqa: E402
from working_paper_generator.patch_generator import generate_patch  # noqa: E402
from working_paper_generator.draft_writer import write_draft  # noqa: E402
from working_paper_generator.schemas import (  # noqa: E402
    PaperSection,
    PaperState,
    ReadinessReport,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SIMPLE_TRANSCRIPT = """\
[Engineering] We need to validate interference modelling assumptions for coastal sites.
[Policy] We also need clearer protection criteria for aviation corridors.
[Operations] Agreed — missing handover procedures for new bands must be documented.
[Engineering] I agree, let's add a documentation action item.
"""

MULTI_SPEAKER_TRANSCRIPT = """\
Alice: This approach supports our goals.
Bob: However, I have concerns about the timeline.
Alice: Agreed — we will proceed cautiously.
Carol: What is the deadline for this decision?
"""

MINIMAL_PAPER_TEXT = """\
# Working Paper Draft

## Introduction

Background context for the study.

## Methodology

Description of proposed methods.
"""

MINIMAL_PAPER_JSON = {
    "paper_id": "WP-TEST-001",
    "title": "Test Working Paper",
    "version": "1.0",
    "sections": [
        {
            "section_id": "SEC-001",
            "title": "Introduction",
            "content": "Background context.",
            "status": "draft",
            "open_issues": ["Need coastal site data"],
        },
        {
            "section_id": "SEC-002",
            "title": "Methodology",
            "content": "Methods TBD.",
            "status": "draft",
            "open_issues": [],
        },
    ],
}


# ---------------------------------------------------------------------------
# Module file existence
# ---------------------------------------------------------------------------


def test_module_directory_exists() -> None:
    assert WPG_DIR.is_dir(), "working_paper_generator/ directory is missing"


@pytest.mark.parametrize(
    "filename",
    [
        "__init__.py",
        "schemas.py",
        "transcript_parser.py",
        "paper_state_reader.py",
        "meeting_delta_engine.py",
        "argument_builder.py",
        "question_engine.py",
        "readiness_scorer.py",
        "patch_generator.py",
        "draft_writer.py",
    ],
)
def test_module_files_exist(filename: str) -> None:
    assert (WPG_DIR / filename).is_file(), f"working_paper_generator/{filename} is missing"


def test_cli_script_exists() -> None:
    assert SCRIPT_PATH.is_file(), "scripts/run_working_paper_generator.py is missing"


# ---------------------------------------------------------------------------
# transcript_parser
# ---------------------------------------------------------------------------


def test_parse_transcript_returns_segments() -> None:
    result = parse_transcript(SIMPLE_TRANSCRIPT, meeting_title="Test Meeting")
    assert result.meeting_title == "Test Meeting"
    assert len(result.segments) >= 4
    assert result.raw_text == SIMPLE_TRANSCRIPT


def test_parse_transcript_participants() -> None:
    result = parse_transcript(SIMPLE_TRANSCRIPT)
    assert "Engineering" in result.participants
    assert "Policy" in result.participants
    assert "Operations" in result.participants


def test_parse_transcript_tags_decisions() -> None:
    result = parse_transcript(SIMPLE_TRANSCRIPT)
    decision_segs = [s for s in result.segments if "decision" in s.tags]
    assert decision_segs, "Expected at least one decision-tagged segment"


def test_parse_transcript_tags_questions() -> None:
    result = parse_transcript(MULTI_SPEAKER_TRANSCRIPT)
    question_segs = [s for s in result.segments if "question" in s.tags]
    assert question_segs, "Expected at least one question-tagged segment"


def test_parse_transcript_colon_speaker_format() -> None:
    result = parse_transcript(MULTI_SPEAKER_TRANSCRIPT)
    speakers = {seg.speaker for seg in result.segments}
    assert "Alice" in speakers
    assert "Bob" in speakers
    assert "Carol" in speakers


def test_parse_transcript_empty_input() -> None:
    result = parse_transcript("")
    assert result.segments == []
    assert result.participants == []


# ---------------------------------------------------------------------------
# paper_state_reader
# ---------------------------------------------------------------------------


def test_read_paper_state_plain_text(tmp_path: Path) -> None:
    paper_file = tmp_path / "paper.md"
    paper_file.write_text(MINIMAL_PAPER_TEXT, encoding="utf-8")
    state = read_paper_state(str(paper_file))
    assert state.title == "Working Paper Draft"
    assert len(state.sections) == 2
    assert state.sections[0].title == "Introduction"
    assert state.sections[1].title == "Methodology"


def test_read_paper_state_json(tmp_path: Path) -> None:
    paper_file = tmp_path / "paper.json"
    paper_file.write_text(json.dumps(MINIMAL_PAPER_JSON), encoding="utf-8")
    state = read_paper_state(str(paper_file))
    assert state.paper_id == "WP-TEST-001"
    assert state.version == "1.0"
    assert len(state.sections) == 2
    assert state.sections[0].open_issues == ["Need coastal site data"]


def test_read_paper_state_preserves_section_ids(tmp_path: Path) -> None:
    paper_file = tmp_path / "paper.json"
    paper_file.write_text(json.dumps(MINIMAL_PAPER_JSON), encoding="utf-8")
    state = read_paper_state(str(paper_file))
    ids = [sec.section_id for sec in state.sections]
    assert ids == ["SEC-001", "SEC-002"]


# ---------------------------------------------------------------------------
# meeting_delta_engine
# ---------------------------------------------------------------------------


def test_compute_delta_no_existing_paper() -> None:
    transcript = parse_transcript(SIMPLE_TRANSCRIPT)
    delta = compute_delta(transcript)
    assert isinstance(delta.new_topics, list)
    assert isinstance(delta.unresolved_items, list)
    assert isinstance(delta.consensus_items, list)
    assert isinstance(delta.updated_sections, list)


def test_compute_delta_with_paper_state(tmp_path: Path) -> None:
    paper_file = tmp_path / "paper.json"
    paper_file.write_text(json.dumps(MINIMAL_PAPER_JSON), encoding="utf-8")
    state = read_paper_state(str(paper_file))

    transcript = parse_transcript(SIMPLE_TRANSCRIPT)
    delta = compute_delta(transcript, state)
    # "Agreed" segment → consensus item
    assert any("agreed" in item.lower() or "Agreed" in item for item in delta.consensus_items)


def test_compute_delta_unresolved_has_questions() -> None:
    transcript = parse_transcript(MULTI_SPEAKER_TRANSCRIPT)
    delta = compute_delta(transcript)
    assert isinstance(delta.unresolved_items, list)


# ---------------------------------------------------------------------------
# argument_builder
# ---------------------------------------------------------------------------


def test_build_arguments_returns_list() -> None:
    transcript = parse_transcript(SIMPLE_TRANSCRIPT)
    args = build_arguments(transcript)
    assert isinstance(args, list)
    assert len(args) > 0


def test_build_arguments_ids_are_unique() -> None:
    transcript = parse_transcript(SIMPLE_TRANSCRIPT)
    args = build_arguments(transcript)
    ids = [a.argument_id for a in args]
    assert len(ids) == len(set(ids))


def test_build_arguments_stance_values() -> None:
    transcript = parse_transcript(MULTI_SPEAKER_TRANSCRIPT)
    args = build_arguments(transcript)
    valid_stances = {"supporting", "opposing", "neutral"}
    for arg in args:
        assert arg.stance in valid_stances, f"Unexpected stance: {arg.stance}"


def test_build_arguments_opposing_stance_detected() -> None:
    transcript = parse_transcript(MULTI_SPEAKER_TRANSCRIPT)
    args = build_arguments(transcript)
    opposing = [a for a in args if a.stance == "opposing"]
    assert opposing, "Expected at least one opposing argument from Bob's 'concerns' line"


# ---------------------------------------------------------------------------
# question_engine
# ---------------------------------------------------------------------------


def test_extract_questions_detects_literal_question_mark() -> None:
    transcript = parse_transcript(MULTI_SPEAKER_TRANSCRIPT)
    questions = extract_questions(transcript)
    assert len(questions) >= 1
    texts = [q.text for q in questions]
    assert any("?" in t for t in texts)


def test_extract_questions_ids_are_unique() -> None:
    transcript = parse_transcript(MULTI_SPEAKER_TRANSCRIPT)
    questions = extract_questions(transcript)
    ids = [q.question_id for q in questions]
    assert len(ids) == len(set(ids))


def test_extract_questions_resolution_status_values() -> None:
    transcript = parse_transcript(MULTI_SPEAKER_TRANSCRIPT)
    questions = extract_questions(transcript)
    valid = {"open", "deferred", "resolved"}
    for q in questions:
        assert q.resolution_status in valid


# ---------------------------------------------------------------------------
# readiness_scorer
# ---------------------------------------------------------------------------


def _make_paper_state() -> PaperState:
    return PaperState(
        paper_id="WP-TEST",
        title="Test Paper",
        version="1.0",
        sections=[
            PaperSection("SEC-001", "Introduction", "Background.", "draft", ["Need data"]),
            PaperSection("SEC-002", "Methodology", "Methods.", "draft"),
        ],
    )


def test_score_readiness_returns_report() -> None:
    state = _make_paper_state()
    transcript = parse_transcript(SIMPLE_TRANSCRIPT)
    delta = compute_delta(transcript, state)
    questions = extract_questions(transcript, state)
    report = score_readiness(state, delta, questions)
    assert 0.0 <= report.overall_score <= 1.0
    assert len(report.sections) == 2


def test_score_readiness_section_scores_in_range() -> None:
    state = _make_paper_state()
    transcript = parse_transcript(SIMPLE_TRANSCRIPT)
    delta = compute_delta(transcript, state)
    questions = extract_questions(transcript)
    report = score_readiness(state, delta, questions)
    for sr in report.sections:
        assert 0.0 <= sr.score <= 1.0


def test_score_readiness_ready_to_draft_is_bool() -> None:
    state = _make_paper_state()
    transcript = parse_transcript(SIMPLE_TRANSCRIPT)
    delta = compute_delta(transcript, state)
    questions = extract_questions(transcript, state)
    report = score_readiness(state, delta, questions)
    assert isinstance(report.ready_to_draft, bool)


# ---------------------------------------------------------------------------
# patch_generator
# ---------------------------------------------------------------------------


def test_generate_patch_no_existing_paper() -> None:
    transcript = parse_transcript(SIMPLE_TRANSCRIPT)
    delta = compute_delta(transcript)
    patch = generate_patch(delta, paper_state=None, meeting_title="Test Meeting")
    assert patch.source_meeting == "Test Meeting"
    assert isinstance(patch.patches, list)


def test_generate_patch_add_operations_for_new_topics() -> None:
    transcript = parse_transcript(SIMPLE_TRANSCRIPT)
    delta = compute_delta(transcript)
    patch = generate_patch(delta, paper_state=None)
    add_patches = [p for p in patch.patches if p.operation == "add"]
    assert len(add_patches) == len(patch.patches), "Without existing paper all patches should be add"


def test_generate_patch_with_existing_paper(tmp_path: Path) -> None:
    paper_file = tmp_path / "paper.json"
    paper_file.write_text(json.dumps(MINIMAL_PAPER_JSON), encoding="utf-8")
    state = read_paper_state(str(paper_file))

    transcript = parse_transcript(SIMPLE_TRANSCRIPT)
    delta = compute_delta(transcript, state)
    patch = generate_patch(delta, state)
    ops = {p.operation for p in patch.patches}
    assert ops.issubset({"add", "update", "delete"})


# ---------------------------------------------------------------------------
# draft_writer
# ---------------------------------------------------------------------------


def test_write_draft_no_existing_paper() -> None:
    transcript = parse_transcript(SIMPLE_TRANSCRIPT)
    delta = compute_delta(transcript)
    args_list = build_arguments(transcript)
    questions = extract_questions(transcript)
    readiness = ReadinessReport(overall_score=0.0, sections=[], ready_to_draft=False)
    patch = generate_patch(delta, paper_state=None, meeting_title="Test Meeting")

    draft = write_draft(patch, None, args_list, questions, readiness)
    assert draft.paper_id is not None
    assert draft.title is not None
    assert isinstance(draft.sections, list)


def test_write_draft_with_existing_paper(tmp_path: Path) -> None:
    paper_file = tmp_path / "paper.json"
    paper_file.write_text(json.dumps(MINIMAL_PAPER_JSON), encoding="utf-8")
    state = read_paper_state(str(paper_file))

    transcript = parse_transcript(SIMPLE_TRANSCRIPT)
    delta = compute_delta(transcript, state)
    args_list = build_arguments(transcript, state)
    questions = extract_questions(transcript, state)
    readiness = score_readiness(state, delta, questions)
    patch = generate_patch(delta, state)

    draft = write_draft(patch, state, args_list, questions, readiness)
    assert draft.paper_id == "WP-TEST-001"
    assert "draft" in draft.version
    assert draft.patch_applied is not None


def test_write_draft_preserves_arguments_and_questions() -> None:
    transcript = parse_transcript(MULTI_SPEAKER_TRANSCRIPT)
    delta = compute_delta(transcript)
    args_list = build_arguments(transcript)
    questions = extract_questions(transcript)
    readiness = ReadinessReport(overall_score=0.5, sections=[], ready_to_draft=True)
    patch = generate_patch(delta, None)

    draft = write_draft(patch, None, args_list, questions, readiness)
    assert draft.arguments == args_list
    assert draft.open_questions == questions


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


def test_cli_help() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--transcript" in result.stdout


def test_cli_missing_transcript_flag() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_cli_json_output(tmp_path: Path) -> None:
    output_file = tmp_path / "output.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--transcript",
            str(SAMPLE_TRANSCRIPT),
            "--output",
            str(output_file),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert output_file.is_file()
    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert "paper_id" in data
    assert "sections" in data
    assert "open_questions" in data
    assert "readiness" in data


def test_cli_markdown_output(tmp_path: Path) -> None:
    output_file = tmp_path / "output.md"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--transcript",
            str(SAMPLE_TRANSCRIPT),
            "--output",
            str(output_file),
            "--format",
            "markdown",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert output_file.is_file()
    content = output_file.read_text(encoding="utf-8")
    assert "# " in content  # has at least one Markdown heading
    assert "Readiness Assessment" in content


def test_cli_with_draft_input(tmp_path: Path) -> None:
    paper_file = tmp_path / "draft.json"
    paper_file.write_text(json.dumps(MINIMAL_PAPER_JSON), encoding="utf-8")
    output_file = tmp_path / "result.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--transcript",
            str(SAMPLE_TRANSCRIPT),
            "--draft",
            str(paper_file),
            "--output",
            str(output_file),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert data["paper_id"] == "WP-TEST-001"


def test_cli_meeting_title_flag(tmp_path: Path) -> None:
    output_file = tmp_path / "result.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--transcript",
            str(SAMPLE_TRANSCRIPT),
            "--meeting-title",
            "Spectrum Coordination Sync",
            "--output",
            str(output_file),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert "Spectrum Coordination Sync" in data.get("title", "")
