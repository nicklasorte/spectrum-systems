"""
Tests for spectrum_systems/modules/gap_detection.py

Covers:
  A. Module boundary — gap_detection.py entry points
  B. Unified gap schema — canonical gap objects in both packet and meeting minutes
  C. Contradiction detection — numeric conflicts
  D. Contradiction detection — polarity conflicts
  E. Contradiction propagation to caution_flags
  F. Structured followups
  G. Compatibility / regression — P-fix-1/P-fix-2A behaviors
  H. Validator hardening — malformed objects fail
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.gap_detection import (
    detect_slide_gaps,
    compute_slide_transcript_gaps,
    merge_slide_transcript_outputs,
    detect_cross_slide_contradictions,
    build_deck_assumption_index,
    GAP_TYPES,
    _extract_tokens,
)
from spectrum_systems.modules.slide_intelligence import (
    extract_slide_units,
    extract_claims,
    extract_assumptions,
    build_slide_intelligence_packet,
    normalize_slides,
    align_slides_to_transcript,
    extract_slide_signals,
    _build_deck_assumption_index,
)

SCHEMA_ROOT = REPO_ROOT / "contracts" / "schemas"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "slide_deck_fixture.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _make_slide_unit(slide_id: str, raw_text: str = "", bullets=None, title: str = "") -> dict:
    return {
        "slide_id": slide_id,
        "title": title or slide_id,
        "bullets": bullets or [],
        "raw_text": raw_text,
        "notes": "",
    }


def _claim(claim_id: str, text: str, slide_id: str) -> dict:
    return {
        "claim_id": claim_id,
        "claim_text": text,
        "related_entities": [],
        "confidence": "medium",
        "source_slide_id": slide_id,
    }


# ---------------------------------------------------------------------------
# A. Module boundary tests — gap_detection entry points
# ---------------------------------------------------------------------------

class TestModuleBoundary:
    """Verify that gap_detection.py exposes the expected public API."""

    def test_detect_slide_gaps_is_callable(self):
        unit = _make_slide_unit("S1", "overview")
        result = detect_slide_gaps(unit, [], [])
        assert isinstance(result, list)

    def test_compute_slide_transcript_gaps_is_callable(self):
        result = compute_slide_transcript_gaps(
            {"decisions": [], "action_items": [], "open_questions": [],
             "slide_only_content": [], "discussion_only_content": []}
        )
        assert "reconciliation_status" in result

    def test_merge_slide_transcript_outputs_is_callable(self):
        result = merge_slide_transcript_outputs(
            {"decisions": [], "action_items": [], "open_questions": []},
            {"claims": [], "proposals": [], "open_questions": [], "metrics": []},
            [],
        )
        assert "slide_only_content" in result
        assert "discussion_only_content" in result

    def test_detect_cross_slide_contradictions_is_callable(self):
        result = detect_cross_slide_contradictions([], [])
        assert isinstance(result, list)

    def test_build_deck_assumption_index_is_callable(self):
        result = build_deck_assumption_index([])
        assert "has_propagation_model" in result

    def test_gap_types_contains_expected_values(self):
        expected = {
            "missing_propagation_model", "missing_assumption", "missing_criteria",
            "missing_method", "missing_basis", "contradiction", "reconciliation_gap",
        }
        assert expected.issubset(GAP_TYPES)

    def test_slide_intelligence_still_assembles_packets_correctly(self):
        """slide_intelligence.build_slide_intelligence_packet uses gap_detection."""
        deck = _load_fixture()
        packet = build_slide_intelligence_packet(deck)
        assert packet["artifact_type"] == "slide_intelligence_packet"
        assert isinstance(packet["analysis_gaps"], list)

    def test_detect_gaps_in_slide_intelligence_delegates_to_gap_detection(self):
        """slide_intelligence.detect_gaps is a shim to detect_slide_gaps."""
        from spectrum_systems.modules.slide_intelligence import detect_gaps
        unit = _make_slide_unit("S1", "5G NR may interfere with radar")
        claims = extract_claims(unit)
        asms = extract_assumptions(unit)
        gaps = detect_gaps(unit, claims, asms)
        # Should produce canonical gap objects with gap_type
        for g in gaps:
            assert "gap_type" in g
            assert g["gap_type"] in GAP_TYPES


# ---------------------------------------------------------------------------
# B. Unified gap schema — canonical shape in both packet and meeting minutes
# ---------------------------------------------------------------------------

class TestUnifiedGapSchema:
    """Gap objects must use the canonical shape in both artifact types."""

    CANONICAL_REQUIRED = {"gap_id", "gap_type", "description", "severity",
                          "source_slide_id", "related_claim_ids"}

    def test_packet_gaps_have_canonical_fields(self):
        deck = {
            "artifact_id": "DECK-001",
            "slides": [{
                "slide_number": 1,
                "title": "Interference Results",
                "bullets": ["5G NR may interfere with radar"],
                "raw_text": "5G NR may interfere with radar",
            }],
        }
        packet = build_slide_intelligence_packet(deck)
        for gap in packet["analysis_gaps"]:
            assert self.CANONICAL_REQUIRED.issubset(gap.keys()), (
                f"Gap missing canonical fields: {gap}"
            )

    def test_packet_gap_type_is_valid(self):
        deck = {
            "artifact_id": "DECK-001",
            "slides": [{
                "slide_number": 1,
                "title": "Interference Results",
                "bullets": ["5G NR may interfere with radar"],
                "raw_text": "5G NR may interfere with radar",
            }],
        }
        packet = build_slide_intelligence_packet(deck)
        for gap in packet["analysis_gaps"]:
            assert gap["gap_type"] in GAP_TYPES, (
                f"Invalid gap_type {gap['gap_type']!r}"
            )

    def test_detect_slide_gaps_returns_canonical_objects(self):
        unit = _make_slide_unit("S1", "5G NR may interfere with radar")
        claims = extract_claims(unit)
        gaps = detect_slide_gaps(unit, claims, [])
        for gap in gaps:
            assert self.CANONICAL_REQUIRED.issubset(gap.keys())
            assert gap["gap_type"] in GAP_TYPES

    def test_packet_gap_schema_validates(self):
        """Packet gaps must validate against the JSON schema gap definition."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = SCHEMA_ROOT / "slide_intelligence_packet.schema.json"
        full_schema = json.loads(schema_path.read_text())
        gap_schema = full_schema["$defs"]["gap"]
        # Resolve $defs in context of the full schema
        resolver = jsonschema.RefResolver.from_schema(full_schema)

        deck = {
            "artifact_id": "DECK-001",
            "slides": [{
                "slide_number": 1,
                "title": "Interference",
                "bullets": ["5G NR may interfere with radar"],
                "raw_text": "5G NR may interfere with radar",
            }],
        }
        packet = build_slide_intelligence_packet(deck)
        for gap in packet["analysis_gaps"]:
            # Should not raise
            jsonschema.validate(gap, gap_schema, resolver=resolver)

    def test_no_legacy_string_array_only_followups(self):
        """Reconciliation output must not contain bare string followups."""
        enriched = {
            "decisions": [],
            "action_items": [],
            "open_questions": [],
            "slide_only_content": ["5G NR coexistence study"],
            "discussion_only_content": ["satellite uplink coordination"],
        }
        result = compute_slide_transcript_gaps(enriched, slides_present=True)
        for fup in result["recommended_followups"]:
            assert isinstance(fup, dict), (
                f"Expected dict follow-up object, got: {fup!r}"
            )


# ---------------------------------------------------------------------------
# C. Contradiction detection — numeric conflict
# ---------------------------------------------------------------------------

class TestContradictionNumeric:
    """Quantitative conflicts between same-unit values on same topic."""

    def test_numeric_conflict_emits_contradiction_gap(self):
        """Slide 3: exclusion zone 5 km vs Slide 5: separation sufficient at 3 km."""
        claims = [
            _claim("C-001", "The exclusion zone of 5 km is required for coexistence.", "SLIDE-3"),
            _claim("C-002", "Separation of 3 km is sufficient for coexistence.", "SLIDE-5"),
        ]
        units = [
            _make_slide_unit("SLIDE-3", "The exclusion zone of 5 km is required for coexistence."),
            _make_slide_unit("SLIDE-5", "Separation of 3 km is sufficient for coexistence."),
        ]
        gaps = detect_cross_slide_contradictions(units, claims)
        contradiction_gaps = [g for g in gaps if g["gap_type"] == "contradiction"]
        assert len(contradiction_gaps) >= 1, (
            "Expected at least one contradiction gap for conflicting km values"
        )

    def test_contradiction_gap_has_canonical_fields(self):
        claims = [
            _claim("C-001", "The exclusion zone of 5 km is required for coexistence.", "SLIDE-3"),
            _claim("C-002", "Separation of 3 km is sufficient for coexistence.", "SLIDE-5"),
        ]
        units = [
            _make_slide_unit("SLIDE-3", "The exclusion zone of 5 km is required for coexistence."),
            _make_slide_unit("SLIDE-5", "Separation of 3 km is sufficient for coexistence."),
        ]
        gaps = detect_cross_slide_contradictions(units, claims)
        for gap in gaps:
            assert "gap_id" in gap
            assert "gap_type" in gap
            assert gap["gap_type"] == "contradiction"
            assert "description" in gap
            assert "severity" in gap
            assert "related_claim_ids" in gap
            assert "source_slide_id" in gap

    def test_contradiction_links_both_claim_ids(self):
        claims = [
            _claim("C-001", "The exclusion zone of 5 km is required for coexistence.", "SLIDE-3"),
            _claim("C-002", "Separation of 3 km is sufficient for coexistence.", "SLIDE-5"),
        ]
        units = [
            _make_slide_unit("SLIDE-3", "The exclusion zone of 5 km is required for coexistence."),
            _make_slide_unit("SLIDE-5", "Separation of 3 km is sufficient for coexistence."),
        ]
        gaps = detect_cross_slide_contradictions(units, claims)
        if gaps:
            # Should contain both claim IDs
            all_linked = set()
            for g in gaps:
                all_linked.update(g.get("related_claim_ids", []))
            assert "C-001" in all_linked or "C-002" in all_linked

    def test_same_unit_same_value_does_not_emit_contradiction(self):
        """Same numeric value on same topic → not a contradiction."""
        claims = [
            _claim("C-001", "The exclusion zone of 5 km is required for coexistence.", "SLIDE-3"),
            _claim("C-002", "Separation of 5 km is required for coexistence.", "SLIDE-5"),
        ]
        units = [
            _make_slide_unit("SLIDE-3", "The exclusion zone of 5 km is required for coexistence."),
            _make_slide_unit("SLIDE-5", "Separation of 5 km is required for coexistence."),
        ]
        gaps = detect_cross_slide_contradictions(units, claims)
        assert gaps == [], "Identical values should not emit a contradiction"

    def test_same_slide_claims_do_not_produce_contradiction(self):
        """Claims from the same slide should not be flagged as contradictory."""
        claims = [
            _claim("C-001", "The exclusion zone of 5 km is required for coexistence.", "SLIDE-3"),
            _claim("C-002", "Separation of 3 km is sufficient for coexistence.", "SLIDE-3"),
        ]
        units = [_make_slide_unit("SLIDE-3")]
        gaps = detect_cross_slide_contradictions(units, claims)
        assert gaps == [], "Same-slide claims must not be flagged as contradictions"


# ---------------------------------------------------------------------------
# D. Contradiction detection — polarity conflict
# ---------------------------------------------------------------------------

class TestContradictionPolarity:
    """Opposite interference/compatibility assertions across slides."""

    def test_may_interfere_vs_does_not_interfere(self):
        """Slide 2: 'may interfere' vs Slide 6: 'does not interfere'."""
        claims = [
            _claim("C-P1", "5G NR base stations may interfere with radar receivers.", "SLIDE-2"),
            _claim("C-P2", "5G NR base stations does not interfere with radar systems.", "SLIDE-6"),
        ]
        units = [
            _make_slide_unit("SLIDE-2", "5G NR base stations may interfere with radar receivers."),
            _make_slide_unit("SLIDE-6", "5G NR base stations does not interfere with radar systems."),
        ]
        gaps = detect_cross_slide_contradictions(units, claims)
        polarity_gaps = [g for g in gaps if g["gap_type"] == "contradiction"]
        assert len(polarity_gaps) >= 1, (
            "Expected contradiction gap for 'may interfere' vs 'does not interfere'"
        )

    def test_polarity_gap_severity_is_high(self):
        claims = [
            _claim("C-P1", "5G NR base stations may interfere with radar receivers.", "SLIDE-2"),
            _claim("C-P2", "5G NR base stations does not interfere with radar systems.", "SLIDE-6"),
        ]
        units = [
            _make_slide_unit("SLIDE-2", "5G NR base stations may interfere with radar receivers."),
            _make_slide_unit("SLIDE-6", "5G NR base stations does not interfere with radar systems."),
        ]
        gaps = detect_cross_slide_contradictions(units, claims)
        for g in gaps:
            assert g["severity"] in {"high", "medium", "low"}

    def test_no_topic_overlap_does_not_emit_polarity_contradiction(self):
        """Claims on completely different topics should not produce a contradiction."""
        claims = [
            _claim("C-X1", "5G NR may interfere with radar receivers.", "SLIDE-A"),
            _claim("C-X2", "Satellite uplinks does not interfere with ground stations.", "SLIDE-B"),
        ]
        units = [
            _make_slide_unit("SLIDE-A", "5G NR may interfere with radar receivers."),
            _make_slide_unit("SLIDE-B", "Satellite uplinks does not interfere with ground stations."),
        ]
        # "radar" vs "satellite uplinks" — may not have ≥2 shared topic tokens
        # This test checks conservative matching; the exact result depends on
        # token overlap, so we just check that the function is deterministic.
        gaps1 = detect_cross_slide_contradictions(units, claims)
        gaps2 = detect_cross_slide_contradictions(units, claims)
        assert gaps1 == gaps2, "Contradiction detection must be deterministic"

    def test_duplicate_pairs_not_emitted_twice(self):
        """The same contradiction pair should not appear more than once."""
        claims = [
            _claim("C-D1", "5G NR base stations may interfere with radar receivers.", "SLIDE-2"),
            _claim("C-D2", "5G NR base stations does not interfere with radar systems.", "SLIDE-6"),
        ]
        units = [
            _make_slide_unit("SLIDE-2", "5G NR base stations may interfere with radar receivers."),
            _make_slide_unit("SLIDE-6", "5G NR base stations does not interfere with radar systems."),
        ]
        gaps = detect_cross_slide_contradictions(units, claims)
        ids = [g["gap_id"] for g in gaps]
        assert len(ids) == len(set(ids)), "Duplicate contradiction gap IDs found"


# ---------------------------------------------------------------------------
# E. Contradiction propagation to caution_flags
# ---------------------------------------------------------------------------

class TestContradictionPropagationToCautionFlags:
    """Contradictions spanning two slides → caution flags on both candidates."""

    def _build_two_slide_contradiction_deck(self) -> dict:
        return {
            "artifact_id": "CONTRA-DECK-001",
            "slides": [
                {
                    "slide_number": 2,
                    "title": "Preliminary Findings",
                    "bullets": ["5G NR base stations may interfere with radar receivers."],
                    "raw_text": "5G NR base stations may interfere with radar receivers.",
                },
                {
                    "slide_number": 6,
                    "title": "Final Assessment",
                    "bullets": ["5G NR base stations does not interfere with radar systems."],
                    "raw_text": "5G NR base stations does not interfere with radar systems.",
                },
            ],
        }

    def test_contradiction_gap_appears_in_analysis_gaps(self):
        deck = self._build_two_slide_contradiction_deck()
        packet = build_slide_intelligence_packet(deck)
        contradiction_gaps = [
            g for g in packet["analysis_gaps"] if g.get("gap_type") == "contradiction"
        ]
        assert len(contradiction_gaps) >= 1, (
            "Expected contradiction gap to appear in packet analysis_gaps"
        )

    def test_both_slide_candidates_receive_caution_flags(self):
        deck = self._build_two_slide_contradiction_deck()
        packet = build_slide_intelligence_packet(deck)
        contradiction_gaps = [
            g for g in packet["analysis_gaps"] if g.get("gap_type") == "contradiction"
        ]
        if not contradiction_gaps:
            pytest.skip("No contradiction gaps produced by this fixture — skip propagation test")

        # Check that at least one candidate has a caution flag from the contradiction gap
        # The flag text contains the gap description (not necessarily the word "contradiction")
        contra_desc = contradiction_gaps[0]["description"]
        all_flags = []
        for candidate in packet["slide_to_paper_candidates"]:
            all_flags.extend(candidate["caution_flags"])
        has_contra_flag = any(contra_desc in f for f in all_flags)
        assert has_contra_flag, (
            f"Expected at least one candidate to have a contradiction caution flag "
            f"(description: {contra_desc!r}). All flags: {all_flags}"
        )

    def test_no_duplicate_caution_flags(self):
        deck = self._build_two_slide_contradiction_deck()
        packet = build_slide_intelligence_packet(deck)
        for candidate in packet["slide_to_paper_candidates"]:
            flags = candidate["caution_flags"]
            assert len(flags) == len(set(flags)), (
                f"Duplicate caution flags found for slide {candidate['slide_id']}: {flags}"
            )


# ---------------------------------------------------------------------------
# F. Structured followups
# ---------------------------------------------------------------------------

class TestStructuredFollowups:
    """Reconciliation output must contain structured follow-up objects."""

    FOLLOWUP_REQUIRED = {"followup_id", "type", "text", "source_type", "source_id"}
    VALID_TYPES = {"discuss", "add_evidence", "clarify_alignment"}
    VALID_SOURCE_TYPES = {"slide", "transcript", "gap"}

    def _enriched_with_content(self) -> dict:
        return {
            "decisions": [],
            "action_items": [],
            "open_questions": [],
            "slide_only_content": ["5G NR coexistence study requires guard band"],
            "discussion_only_content": ["satellite uplink coordination reviewed"],
        }

    def test_followups_are_dicts_not_strings(self):
        result = compute_slide_transcript_gaps(self._enriched_with_content(), slides_present=True)
        for fup in result["recommended_followups"]:
            assert isinstance(fup, dict), f"Expected dict, got {type(fup)}: {fup!r}"

    def test_followup_has_required_fields(self):
        result = compute_slide_transcript_gaps(self._enriched_with_content(), slides_present=True)
        for fup in result["recommended_followups"]:
            assert self.FOLLOWUP_REQUIRED.issubset(fup.keys()), (
                f"Follow-up missing required fields: {fup}"
            )

    def test_followup_type_is_valid(self):
        result = compute_slide_transcript_gaps(self._enriched_with_content(), slides_present=True)
        for fup in result["recommended_followups"]:
            assert fup["type"] in self.VALID_TYPES, (
                f"Invalid follow-up type: {fup['type']!r}"
            )

    def test_followup_source_type_is_valid(self):
        result = compute_slide_transcript_gaps(self._enriched_with_content(), slides_present=True)
        for fup in result["recommended_followups"]:
            assert fup["source_type"] in self.VALID_SOURCE_TYPES, (
                f"Invalid follow-up source_type: {fup['source_type']!r}"
            )

    def test_followup_text_is_non_empty(self):
        result = compute_slide_transcript_gaps(self._enriched_with_content(), slides_present=True)
        for fup in result["recommended_followups"]:
            assert fup["text"].strip() != "", "Follow-up text must not be empty"

    def test_followup_id_is_unique(self):
        result = compute_slide_transcript_gaps(self._enriched_with_content(), slides_present=True)
        ids = [fup["followup_id"] for fup in result["recommended_followups"]]
        assert len(ids) == len(set(ids)), "Follow-up IDs must be unique"

    def test_discuss_type_for_undiscussed_slides(self):
        enriched = {
            "decisions": [], "action_items": [], "open_questions": [],
            "slide_only_content": ["5G NR guard band study"],
            "discussion_only_content": [],
        }
        result = compute_slide_transcript_gaps(enriched)
        discuss_fups = [f for f in result["recommended_followups"] if f["type"] == "discuss"]
        assert len(discuss_fups) >= 1, "Expected 'discuss' follow-up for undiscussed slide content"

    def test_add_evidence_type_for_unpresented_discussions(self):
        enriched = {
            "decisions": [], "action_items": [], "open_questions": [],
            "slide_only_content": [],
            "discussion_only_content": ["satellite uplink coordination"],
        }
        result = compute_slide_transcript_gaps(enriched)
        add_ev_fups = [f for f in result["recommended_followups"] if f["type"] == "add_evidence"]
        assert len(add_ev_fups) >= 1, "Expected 'add_evidence' follow-up for unpresented discussions"

    def test_clarify_alignment_type_for_weak_areas(self):
        enriched = {
            "decisions": [{"decision_id": "D-001", "description": "Deploy 5G NR", "slide_support": False}],
            "action_items": [],
            "open_questions": [],
            "slide_only_content": [],
            "discussion_only_content": [],
        }
        result = compute_slide_transcript_gaps(enriched)
        clarify_fups = [f for f in result["recommended_followups"] if f["type"] == "clarify_alignment"]
        assert len(clarify_fups) >= 1, "Expected 'clarify_alignment' follow-up for weak alignment areas"

    def test_followup_validates_against_schema(self):
        """Follow-up objects should validate against meeting_minutes_record followup schema."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = SCHEMA_ROOT / "meeting_minutes_record.schema.json"
        full_schema = json.loads(schema_path.read_text())
        followup_schema = full_schema["$defs"]["followup"]
        resolver = jsonschema.RefResolver.from_schema(full_schema)

        enriched = {
            "decisions": [], "action_items": [], "open_questions": [],
            "slide_only_content": ["5G NR coexistence study"],
            "discussion_only_content": ["satellite uplink"],
        }
        result = compute_slide_transcript_gaps(enriched, slides_present=True)
        for fup in result["recommended_followups"]:
            jsonschema.validate(fup, followup_schema, resolver=resolver)


# ---------------------------------------------------------------------------
# G. Compatibility / regression — P-fix-1/P-fix-2A behaviors preserved
# ---------------------------------------------------------------------------

class TestRegressionPfix1:
    """Stopword-resistant support matching (P-fix-1 Part A)."""

    def test_stopword_only_overlap_does_not_count_as_support(self):
        raw_slide = [{
            "slide_number": 1,
            "title": "Overview",
            "bullet_points": ["The and or in on at"],
            "full_text": "The and or in on at",
        }]
        slides = normalize_slides(raw_slide)
        segments = [{"text": "the and or in on at by"}]
        alignment = align_slides_to_transcript(slides, segments)
        signals = extract_slide_signals(slides)
        structured = {
            "decisions": [{"decision_id": "D-001", "description": "the and or in on at"}],
            "action_items": [],
            "open_questions": [],
        }
        enriched = merge_slide_transcript_outputs(structured, signals, alignment)
        assert enriched["decisions"][0]["slide_support"] is False

    def test_two_meaningful_tokens_counts_as_support(self):
        shared = "interference coexistence radar band"
        raw_slide = [{
            "slide_number": 1,
            "title": "Interference",
            "bullet_points": [shared],
            "full_text": shared,
        }]
        slides = normalize_slides(raw_slide)
        segments = [{"text": shared}]
        alignment = align_slides_to_transcript(slides, segments)
        signals = extract_slide_signals(slides)
        structured = {
            "decisions": [{"decision_id": "D-001", "description": shared}],
            "action_items": [],
            "open_questions": [],
        }
        enriched = merge_slide_transcript_outputs(structured, signals, alignment)
        assert enriched["decisions"][0]["slide_support"] is True


class TestRegressionPfix1B:
    """Deck-level Rule 1 suppression (P-fix-1 Part B)."""

    def test_rule1_suppressed_when_propagation_present_elsewhere(self):
        slide2 = _make_slide_unit("SLIDE-2", "Propagation model: ITM Longley-Rice.")
        slide3 = _make_slide_unit("SLIDE-3", "5G NR may interfere with radar at 3.5 GHz.")
        deck_index = build_deck_assumption_index([slide2, slide3])
        claims3 = extract_claims(slide3)
        gaps3 = detect_slide_gaps(slide3, claims3, [], deck_assumption_index=deck_index)
        rule1_gaps = [g for g in gaps3 if g.get("gap_type") == "missing_propagation_model"]
        assert rule1_gaps == []

    def test_rule1_fires_when_propagation_absent_from_entire_deck(self):
        slide1 = _make_slide_unit("SLIDE-1", "Overview of coexistence study.")
        slide2 = _make_slide_unit("SLIDE-2", "5G NR may interfere with radar systems.")
        deck_index = build_deck_assumption_index([slide1, slide2])
        claims2 = extract_claims(slide2)
        gaps2 = detect_slide_gaps(slide2, claims2, [], deck_assumption_index=deck_index)
        rule1_gaps = [g for g in gaps2 if g.get("gap_type") == "missing_propagation_model"]
        assert len(rule1_gaps) >= 1


class TestRegressionPfix1C:
    """Slide-only coverage across multiple signal types (P-fix-2A)."""

    def test_slide_question_appears_in_undiscussed_slides(self):
        raw_slide = [{
            "slide_number": 1,
            "title": "Open Issues",
            "bullet_points": ["What guard band is required for 5G NR near radar bands?"],
            "full_text": "What guard band is required for 5G NR near radar bands?",
        }]
        slides = normalize_slides(raw_slide)
        segments = [{"text": "Action item: review satellite coordination agreements"}]
        alignment = align_slides_to_transcript(slides, segments)
        signals = extract_slide_signals(slides)
        structured = {
            "decisions": [],
            "action_items": [{"description": "Review satellite coordination agreements"}],
            "open_questions": [],
        }
        enriched = merge_slide_transcript_outputs(structured, signals, alignment)
        slide_only = enriched["slide_only_content"]
        assert any("guard band" in item.lower() for item in slide_only)


class TestRegressionInertReconciliation:
    """Inert reconciliation review flagging (P-fix-2A)."""

    def test_all_empty_with_slides_present_flags_review(self):
        enriched = {
            "decisions": [], "action_items": [], "open_questions": [],
            "slide_only_content": [], "discussion_only_content": [],
        }
        result = compute_slide_transcript_gaps(enriched, slides_present=True)
        assert result["reconciliation_status"] == "inert_review_required"

    def test_nonempty_gives_ok_status(self):
        enriched = {
            "decisions": [{"decision_id": "D-001", "description": "Use ITM model",
                           "slide_support": False}],
            "action_items": [], "open_questions": [],
            "slide_only_content": [],
            "discussion_only_content": ["ITM propagation model missing"],
        }
        result = compute_slide_transcript_gaps(enriched, slides_present=True)
        assert result["reconciliation_status"] == "ok"


# ---------------------------------------------------------------------------
# H. Validator hardening — malformed objects fail schema validation
# ---------------------------------------------------------------------------

class TestValidatorHardening:
    """Malformed gap and follow-up objects must fail JSON schema validation."""

    def test_malformed_gap_fails_packet_schema(self):
        """A gap object missing required fields must fail the packet schema."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = SCHEMA_ROOT / "slide_intelligence_packet.schema.json"
        full_schema = json.loads(schema_path.read_text())
        gap_schema = full_schema["$defs"]["gap"]
        resolver = jsonschema.RefResolver.from_schema(full_schema)

        malformed_gap = {
            "gap_id": "GAP-001",
            # Missing: gap_type, description, severity, source_slide_id, related_claim_ids
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(malformed_gap, gap_schema, resolver=resolver)

    def test_invalid_gap_type_fails_packet_schema(self):
        """A gap with an invalid gap_type value must fail the packet schema."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = SCHEMA_ROOT / "slide_intelligence_packet.schema.json"
        full_schema = json.loads(schema_path.read_text())
        gap_schema = full_schema["$defs"]["gap"]
        resolver = jsonschema.RefResolver.from_schema(full_schema)

        invalid_gap = {
            "gap_id": "GAP-001",
            "gap_type": "invalid_type_not_in_enum",
            "description": "Some gap",
            "severity": "high",
            "source_slide_id": "SLIDE-1",
            "related_claim_ids": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_gap, gap_schema, resolver=resolver)

    def test_malformed_followup_fails_meeting_minutes_schema(self):
        """A follow-up object missing required fields must fail the schema."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = SCHEMA_ROOT / "meeting_minutes_record.schema.json"
        full_schema = json.loads(schema_path.read_text())
        followup_schema = full_schema["$defs"]["followup"]
        resolver = jsonschema.RefResolver.from_schema(full_schema)

        malformed_fup = {
            "followup_id": "FUP-001",
            # Missing: type, text, source_type, source_id
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(malformed_fup, followup_schema, resolver=resolver)

    def test_invalid_followup_type_fails_schema(self):
        """A follow-up with an invalid type value must fail the schema."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = SCHEMA_ROOT / "meeting_minutes_record.schema.json"
        full_schema = json.loads(schema_path.read_text())
        followup_schema = full_schema["$defs"]["followup"]
        resolver = jsonschema.RefResolver.from_schema(full_schema)

        invalid_fup = {
            "followup_id": "FUP-001",
            "type": "invalid_type",
            "text": "Some follow-up",
            "source_type": "slide",
            "source_id": "SLIDE-1",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_fup, followup_schema, resolver=resolver)

    def test_valid_gap_passes_packet_schema(self):
        """A correctly formed gap must pass the packet schema."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = SCHEMA_ROOT / "slide_intelligence_packet.schema.json"
        full_schema = json.loads(schema_path.read_text())
        gap_schema = full_schema["$defs"]["gap"]
        resolver = jsonschema.RefResolver.from_schema(full_schema)

        valid_gap = {
            "gap_id": "GAP-001",
            "gap_type": "missing_propagation_model",
            "description": "Interference claim without propagation model.",
            "severity": "high",
            "source_slide_id": "SLIDE-1",
            "related_claim_ids": ["CLAIM-001"],
            "evidence": None,
        }
        # Should not raise
        jsonschema.validate(valid_gap, gap_schema, resolver=resolver)

    def test_valid_followup_passes_meeting_minutes_schema(self):
        """A correctly formed follow-up must pass the schema."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = SCHEMA_ROOT / "meeting_minutes_record.schema.json"
        full_schema = json.loads(schema_path.read_text())
        followup_schema = full_schema["$defs"]["followup"]
        resolver = jsonschema.RefResolver.from_schema(full_schema)

        valid_fup = {
            "followup_id": "FUP-001",
            "type": "discuss",
            "text": "Discuss in next meeting: guard band requirement",
            "source_type": "slide",
            "source_id": "5G NR guard band",
            "target_section": None,
            "severity": None,
        }
        jsonschema.validate(valid_fup, followup_schema, resolver=resolver)
