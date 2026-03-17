"""
Tests for spectrum_systems/modules/working_paper_generator.py

Covers:
  - generate_working_paper: minimal transcript → valid paper
  - generate_working_paper: transcript + slides → enriched paper
  - generate_working_paper: gap-driven question generation
  - generate_working_paper: traceability is present and well-formed
  - generate_agency_questions: produces >= 5 questions
  - validate_working_paper: valid paper passes, invalid paper fails
  - Contract schema: example working_paper.json validates against schema
  - Golden case: full enriched paper satisfies all required sections
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.working_paper_generator import (
    _LIST_SECTION_KEYS,
    generate_agency_questions,
    generate_working_paper,
    validate_working_paper,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "working_paper.schema.json"
CONTRACT_EXAMPLE_PATH = REPO_ROOT / "contracts" / "examples" / "working_paper.json"

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

MINIMAL_TRANSCRIPT: dict = {
    "title": "3.5 GHz Spectrum Coordination Meeting",
    "meeting_context": "Coordination meeting for 3550-3700 MHz band sharing.",
    "text": (
        "The team discussed interference modelling for the 3550-3700 MHz band. "
        "Protection criteria for federal P2P links were reviewed. "
        "We agreed that link budget validation is required before proceeding. "
        "There is uncertainty about actual antenna deployment heights. "
        "The propagation model assumptions need further review."
    ),
    "decisions_made": [
        "Link budget validation is required before deployment.",
        "A coordination protocol document will be drafted.",
    ],
    "action_items": ["Draft coordination protocol by next meeting."],
    "risks_or_open_questions": [
        "Antenna height assumptions have not been field-validated.",
        "Radar exclusion zone parameters are not yet confirmed.",
    ],
    "assumptions": [
        "Federal P2P antenna height of 30 m assumed.",
        "Commercial base station EIRP limited to 30 dBm/10 MHz.",
    ],
    "entities": [
        {"name": "P2P link", "type": "system"},
        {"name": "base station", "type": "system"},
    ],
}

SLIDE_SIGNALS: dict = {
    "claims": [
        {
            "text": "Protection zones range from 40 km to 150 km depending on deployment density.",
            "confidence": 0.82,
            "section": "key_findings",
        },
        {
            "text": "Link budget analysis uses ITM model at 3625 MHz center frequency.",
            "confidence": 0.90,
            "section": "technical_analysis",
        },
    ],
    "methods": ["ITM propagation model", "link budget analysis"],
    "entities": [{"name": "radar system", "type": "federal_system"}],
}

GAP_ANALYSIS: dict = {
    "gaps": [
        "No field measurement data for path loss in the 3.5 GHz band.",
        "Aggregate interference model is missing for dense urban deployments.",
    ],
    "deployment_gaps": ["Commercial antenna deployment heights not validated in study area."],
    "interference_gaps": ["Radar blanket exclusion zone not evaluated in interference model."],
    "conflicts": [
        "Slide presented protection zone radius of 150 km; discussion assumed 40 km without justification."
    ],
}

REQUIRED_KEYS = {
    "title",
    "executive_summary",
    "purpose_and_scope",
    "system_description",
    "technical_analysis",
    "key_findings",
    "risks_and_uncertainties",
    "decisions_and_recommendations",
    "open_questions_for_agencies",
    "appendix",
}

REQUIRED_APPENDIX_KEYS = {
    "source_traceability",
    "slide_alignment_summary",
    "discussion_gaps",
}


# ---------------------------------------------------------------------------
# 1. Minimal transcript → valid paper
# ---------------------------------------------------------------------------


def test_minimal_transcript_produces_all_required_keys() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    assert REQUIRED_KEYS.issubset(set(paper.keys())), (
        f"Missing keys: {REQUIRED_KEYS - set(paper.keys())}"
    )


def test_minimal_transcript_produces_all_appendix_keys() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    appendix = paper["appendix"]
    assert isinstance(appendix, dict)
    assert REQUIRED_APPENDIX_KEYS.issubset(set(appendix.keys())), (
        f"Missing appendix keys: {REQUIRED_APPENDIX_KEYS - set(appendix.keys())}"
    )


def test_minimal_transcript_title_is_populated() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    assert paper["title"], "title must not be empty"


def test_minimal_transcript_executive_summary_is_string() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    assert isinstance(paper["executive_summary"], str)
    assert len(paper["executive_summary"]) > 50


def test_minimal_transcript_list_sections_are_lists() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    for key in _LIST_SECTION_KEYS:
        assert isinstance(paper[key], list), f"{key} must be a list"


def test_minimal_transcript_decisions_captured_in_recommendations() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    recs = " ".join(paper["decisions_and_recommendations"]).lower()
    assert "link budget" in recs or "coordination" in recs


def test_minimal_transcript_risks_from_open_questions() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    risks_text = " ".join(paper["risks_and_uncertainties"]).lower()
    assert "antenna" in risks_text or "radar" in risks_text or "uncertainty" in risks_text or "assumption" in risks_text


def test_minimal_transcript_generates_questions() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    assert len(paper["open_questions_for_agencies"]) >= 5


def test_minimal_transcript_passes_validation() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    errors = validate_working_paper(paper)
    assert errors == [], f"Validation errors: {errors}"


# ---------------------------------------------------------------------------
# 2. Transcript + slides → enriched paper
# ---------------------------------------------------------------------------


def test_with_slides_key_findings_enriched() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT, slide_signals=SLIDE_SIGNALS)
    findings_text = " ".join(paper["key_findings"]).lower()
    assert "protection" in findings_text or "link budget" in findings_text or "itm" in findings_text


def test_with_slides_technical_analysis_references_methods() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT, slide_signals=SLIDE_SIGNALS)
    assert "ITM" in paper["technical_analysis"] or "itm" in paper["technical_analysis"].lower()


def test_with_slides_slide_alignment_summary_populated() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT, slide_signals=SLIDE_SIGNALS)
    alignment = paper["appendix"]["slide_alignment_summary"]
    assert isinstance(alignment, list)
    assert len(alignment) > 0


def test_with_slides_slide_alignment_entries_have_required_fields() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT, slide_signals=SLIDE_SIGNALS)
    for entry in paper["appendix"]["slide_alignment_summary"]:
        assert "slide_claim" in entry
        assert "section" in entry
        assert "confidence" in entry
        assert 0.0 <= entry["confidence"] <= 1.0


def test_with_slides_passes_validation() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT, slide_signals=SLIDE_SIGNALS)
    errors = validate_working_paper(paper)
    assert errors == [], f"Validation errors: {errors}"


# ---------------------------------------------------------------------------
# 3. Gap-driven question generation
# ---------------------------------------------------------------------------


def test_gap_analysis_generates_gap_questions() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT, gap_analysis=GAP_ANALYSIS)
    questions_text = " ".join(paper["open_questions_for_agencies"]).lower()
    assert "gap" in questions_text or "field measurement" in questions_text or "aggregate" in questions_text


def test_gap_analysis_augments_technical_analysis() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT, gap_analysis=GAP_ANALYSIS)
    assert (
        "Unaddressed Deployment" in paper["technical_analysis"]
        or "Unvalidated Interference" in paper["technical_analysis"]
        or "deployment" in paper["technical_analysis"].lower()
    )


def test_gap_analysis_conflicts_in_discussion_gaps() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT, gap_analysis=GAP_ANALYSIS)
    gaps = paper["appendix"]["discussion_gaps"]
    assert isinstance(gaps, list)
    assert len(gaps) > 0


def test_gap_risks_included_in_risks_section() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT, gap_analysis=GAP_ANALYSIS)
    risks_text = " ".join(paper["risks_and_uncertainties"]).lower()
    assert "gap" in risks_text or "field measurement" in risks_text or "aggregate" in risks_text


def test_full_inputs_produces_minimum_question_count() -> None:
    paper = generate_working_paper(
        MINIMAL_TRANSCRIPT,
        slide_signals=SLIDE_SIGNALS,
        gap_analysis=GAP_ANALYSIS,
    )
    assert len(paper["open_questions_for_agencies"]) >= 5


# ---------------------------------------------------------------------------
# 4. Traceability
# ---------------------------------------------------------------------------


def test_traceability_is_present() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    traceability = paper["appendix"]["source_traceability"]
    assert isinstance(traceability, list)
    assert len(traceability) > 0


def test_traceability_entries_have_required_fields() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT, slide_signals=SLIDE_SIGNALS)
    for entry in paper["appendix"]["source_traceability"]:
        assert "claim" in entry, "Traceability entry missing 'claim'"
        assert "source" in entry, "Traceability entry missing 'source'"
        assert "confidence" in entry, "Traceability entry missing 'confidence'"


def test_traceability_confidence_is_in_range() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT, slide_signals=SLIDE_SIGNALS)
    for entry in paper["appendix"]["source_traceability"]:
        assert 0.0 <= entry["confidence"] <= 1.0, (
            f"Confidence out of range: {entry['confidence']}"
        )


def test_traceability_sources_are_valid_values() -> None:
    valid_sources = {"transcript", "slide", "gap_analysis", "derived"}
    paper = generate_working_paper(
        MINIMAL_TRANSCRIPT, slide_signals=SLIDE_SIGNALS, gap_analysis=GAP_ANALYSIS
    )
    for entry in paper["appendix"]["source_traceability"]:
        assert entry["source"] in valid_sources, (
            f"Unexpected source: {entry['source']}"
        )


def test_decisions_have_transcript_traceability() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    transcript_entries = [
        e for e in paper["appendix"]["source_traceability"] if e["source"] == "transcript"
    ]
    assert len(transcript_entries) > 0


def test_slide_claims_have_slide_traceability() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT, slide_signals=SLIDE_SIGNALS)
    slide_entries = [
        e for e in paper["appendix"]["source_traceability"] if e["source"] == "slide"
    ]
    assert len(slide_entries) > 0


# ---------------------------------------------------------------------------
# 5. generate_agency_questions standalone
# ---------------------------------------------------------------------------


def test_agency_questions_minimum_count() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    questions = generate_agency_questions(paper, gap_analysis=None)
    assert len(questions) >= 5


def test_agency_questions_with_gaps_minimum_count() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    questions = generate_agency_questions(paper, gap_analysis=GAP_ANALYSIS)
    assert len(questions) >= 5


def test_agency_questions_are_strings() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    questions = generate_agency_questions(paper)
    for q in questions:
        assert isinstance(q, str), "Each question must be a string"


def test_agency_questions_contain_calibrated_framing() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    questions = generate_agency_questions(paper)
    combined = " ".join(questions).lower()
    assert (
        "how would" in combined
        or "what assumptions" in combined
        or "what would it take" in combined
        or "what additional" in combined
    )


def test_agency_questions_are_unique() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    questions = generate_agency_questions(paper)
    # Use a 60-character prefix for uniqueness — matches the dedup logic in generate_agency_questions
    assert len(questions) == len(set(q.lower()[:60] for q in questions)), "Questions should be unique"


# ---------------------------------------------------------------------------
# 6. validate_working_paper
# ---------------------------------------------------------------------------


def test_valid_paper_passes_validation() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    errors = validate_working_paper(paper)
    assert errors == []


def test_missing_key_fails_validation() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    del paper["executive_summary"]
    errors = validate_working_paper(paper)
    assert any("executive_summary" in e for e in errors)


def test_empty_required_string_fails_validation() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    paper["title"] = ""
    errors = validate_working_paper(paper)
    assert any("title" in e for e in errors)


def test_non_list_key_findings_fails_validation() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    paper["key_findings"] = "not a list"
    errors = validate_working_paper(paper)
    assert any("key_findings" in e for e in errors)


def test_missing_appendix_fails_validation() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    del paper["appendix"]
    errors = validate_working_paper(paper)
    assert any("appendix" in e for e in errors)


def test_missing_appendix_key_fails_validation() -> None:
    paper = generate_working_paper(MINIMAL_TRANSCRIPT)
    del paper["appendix"]["source_traceability"]
    errors = validate_working_paper(paper)
    assert any("source_traceability" in e for e in errors)


# ---------------------------------------------------------------------------
# 7. Contract schema validation
# ---------------------------------------------------------------------------


def test_contract_schema_file_exists() -> None:
    assert CONTRACT_SCHEMA_PATH.is_file(), (
        f"Schema file missing: {CONTRACT_SCHEMA_PATH}"
    )


def test_contract_example_file_exists() -> None:
    assert CONTRACT_EXAMPLE_PATH.is_file(), (
        f"Example file missing: {CONTRACT_EXAMPLE_PATH}"
    )


def test_contract_schema_is_valid_json() -> None:
    schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert "$schema" in schema
    assert "properties" in schema


def test_contract_example_validates_against_schema() -> None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    example = json.loads(CONTRACT_EXAMPLE_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(example))
    assert errors == [], f"Schema validation errors: {[str(e) for e in errors]}"


# ---------------------------------------------------------------------------
# 8. Golden case: full enriched paper
# ---------------------------------------------------------------------------


GOLDEN_TRANSCRIPT: dict = {
    "title": "Golden Case: 3.5 GHz Coordination",
    "meeting_context": "NTIA/FCC coordination on 3550-3700 MHz CBRS sharing framework.",
    "text": (
        "We reviewed interference studies for the 3550-3700 MHz band. "
        "Federal P2P links were the primary incumbent concern. "
        "CBRS base stations are the primary commercial entrants. "
        "Link budget analysis using the Longley-Rice ITM model was presented. "
        "Protection zones of 40 km to 150 km were recommended. "
        "EIRP limits of 30 dBm/10 MHz were proposed. "
        "There is uncertainty about whether the ITM model is accurate for urban canyons. "
        "We agreed that the SAS coordination mechanism should be the primary tool. "
        "A field measurement campaign is needed to validate propagation assumptions. "
        "Radar exclusion zones need separate analysis."
    ),
    "decisions_made": [
        "SAS coordination is the primary interference management mechanism.",
        "EIRP limits will be set at 30 dBm/10 MHz.",
        "A field measurement campaign will be commissioned.",
    ],
    "action_items": [
        "Commission field measurement campaign.",
        "Draft coordination protocol document.",
        "Complete radar exclusion zone analysis.",
    ],
    "risks_or_open_questions": [
        "ITM model accuracy in urban canyons is unvalidated.",
        "Radar exclusion zone analysis is incomplete.",
        "Aggregate interference from dense CBRS deployments is not modeled.",
    ],
    "assumptions": [
        "Federal antenna height: 30 m.",
        "Commercial EIRP: 30 dBm/10 MHz.",
        "ITM model default parameters apply.",
    ],
    "entities": [
        {"name": "P2P link", "type": "federal_system"},
        {"name": "CBRS base station", "type": "commercial_system"},
        {"name": "radar", "type": "federal_system"},
    ],
}

GOLDEN_SLIDES: dict = {
    "claims": [
        {"text": "Protection zones range from 40 km to 150 km based on ITM calculations.", "confidence": 0.90, "section": "key_findings"},
        {"text": "EIRP limit of 30 dBm/10 MHz provides 6 dB margin above interference threshold.", "confidence": 0.85, "section": "technical_analysis"},
        {"text": "SAS database coordination resolves >95% of potential co-channel interference events.", "confidence": 0.80, "section": "decisions_and_recommendations"},
    ],
    "methods": ["Longley-Rice ITM", "link budget", "Monte Carlo simulation"],
    "entities": [{"name": "SAS", "type": "coordination_system"}],
}

GOLDEN_GAP_ANALYSIS: dict = {
    "gaps": [
        "No urban canyon path loss measurements available.",
        "Aggregate interference model missing for dense deployments.",
    ],
    "deployment_gaps": [
        "Commercial antenna density in dense urban areas not validated.",
    ],
    "interference_gaps": [
        "Radar exclusion zone analysis not completed for all radar variants.",
    ],
    "conflicts": [
        "Slide protection zone of 150 km conflicts with discussion assumption of 40 km.",
    ],
}


def test_golden_case_no_empty_required_sections() -> None:
    paper = generate_working_paper(GOLDEN_TRANSCRIPT, GOLDEN_SLIDES, GOLDEN_GAP_ANALYSIS)
    for key in ("title", "executive_summary", "purpose_and_scope", "system_description", "technical_analysis"):
        assert paper[key], f"Required section '{key}' is empty"
    for key in ("key_findings", "risks_and_uncertainties", "decisions_and_recommendations"):
        assert paper[key], f"Required list section '{key}' is empty"


def test_golden_case_questions_generated() -> None:
    paper = generate_working_paper(GOLDEN_TRANSCRIPT, GOLDEN_SLIDES, GOLDEN_GAP_ANALYSIS)
    assert len(paper["open_questions_for_agencies"]) >= 5


def test_golden_case_traceability_present() -> None:
    paper = generate_working_paper(GOLDEN_TRANSCRIPT, GOLDEN_SLIDES, GOLDEN_GAP_ANALYSIS)
    assert len(paper["appendix"]["source_traceability"]) > 0


def test_golden_case_passes_validate_working_paper() -> None:
    paper = generate_working_paper(GOLDEN_TRANSCRIPT, GOLDEN_SLIDES, GOLDEN_GAP_ANALYSIS)
    errors = validate_working_paper(paper)
    assert errors == [], f"Validation errors in golden case: {errors}"


def test_golden_case_slide_alignment_from_slides() -> None:
    paper = generate_working_paper(GOLDEN_TRANSCRIPT, GOLDEN_SLIDES, GOLDEN_GAP_ANALYSIS)
    assert len(paper["appendix"]["slide_alignment_summary"]) > 0


def test_golden_case_discussion_gaps_from_gap_analysis() -> None:
    paper = generate_working_paper(GOLDEN_TRANSCRIPT, GOLDEN_SLIDES, GOLDEN_GAP_ANALYSIS)
    assert len(paper["appendix"]["discussion_gaps"]) > 0


def test_golden_case_gap_augmented_technical_analysis() -> None:
    paper = generate_working_paper(GOLDEN_TRANSCRIPT, GOLDEN_SLIDES, GOLDEN_GAP_ANALYSIS)
    assert (
        "Unaddressed Deployment" in paper["technical_analysis"]
        or "Unvalidated Interference" in paper["technical_analysis"]
        or "deployment" in paper["technical_analysis"].lower()
    )


# ---------------------------------------------------------------------------
# 9. Graceful fallback (no slides, no gaps)
# ---------------------------------------------------------------------------


def test_no_slides_no_gaps_produces_valid_paper() -> None:
    paper = generate_working_paper({"text": "Short meeting. We discussed spectrum sharing."})
    errors = validate_working_paper(paper)
    assert errors == []


def test_empty_transcript_text_produces_valid_paper() -> None:
    paper = generate_working_paper({"text": "", "title": "Empty Meeting"})
    errors = validate_working_paper(paper)
    assert errors == []


def test_segments_format_transcript_works() -> None:
    transcript = {
        "title": "Segment Format Meeting",
        "segments": [
            {"text": "Federal P2P links are the incumbent system."},
            {"text": "Commercial CBRS base stations will share the band."},
        ],
    }
    paper = generate_working_paper(transcript)
    assert paper["title"] == "Segment Format Meeting"
    errors = validate_working_paper(paper)
    assert errors == []
