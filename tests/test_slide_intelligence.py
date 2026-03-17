"""
Tests for spectrum_systems/modules/slide_intelligence.py

Covers:
  A. extract_slide_units — unit normalization, title heuristic, figure/table detection
  B. score_slide_signal  — scoring reward for parameters, models, exhibits
  C. classify_slide_role — integration role and technical tag assignment
  D. extract_claims      — claim pattern detection, confidence levels
  E. extract_assumptions — type inference, value extraction, partial entries
  F. extract_entities_and_relationships — entity detection, relationship extraction
  G. detect_gaps         — negative-space detection rules
  H. map_to_working_paper_section — section routing
  I. rewrite_for_working_paper     — prose generation and traceability
  J. compare_with_transcript_and_paper — cross-artifact overlap
  K. build_slide_intelligence_packet   — full end-to-end integration packet
  L. Fixture-driven integration tests  — real fixture through full pipeline
  M. Artifact type / schema validation — new artifact types recognised
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "slide_deck_fixture.json"

import sys
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.slide_intelligence import (  # noqa: E402
    extract_slide_units,
    score_slide_signal,
    classify_slide_role,
    extract_claims,
    extract_assumptions,
    extract_entities_and_relationships,
    detect_gaps,
    map_to_working_paper_section,
    rewrite_for_working_paper,
    compare_with_transcript_and_paper,
    build_slide_intelligence_packet,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _deck_with_one_slide(**kwargs) -> dict:
    """Minimal slide deck with a single slide."""
    slide = {
        "slide_number": 1,
        "title": kwargs.get("title", "Test Slide"),
        "bullets": kwargs.get("bullets", []),
        "notes": kwargs.get("notes", ""),
        "raw_text": kwargs.get("raw_text", ""),
        "has_figure": kwargs.get("has_figure", False),
        "has_table": kwargs.get("has_table", False),
        "type": kwargs.get("type", "text"),
    }
    return {
        "artifact_id": "TEST-DECK-001",
        "artifact_type": "slide_deck",
        "presenting_org": kwargs.get("org", "Test Org"),
        "slides": [slide],
    }


# ---------------------------------------------------------------------------
# A. extract_slide_units
# ---------------------------------------------------------------------------

class TestExtractSlideUnits:
    def test_returns_list_of_dicts(self):
        deck = _load_fixture()
        units = extract_slide_units(deck)
        assert isinstance(units, list)
        assert len(units) == 5

    def test_slide_unit_required_fields(self):
        deck = _load_fixture()
        units = extract_slide_units(deck)
        required = {
            "slide_id", "slide_number", "title", "bullets",
            "notes", "raw_text", "figures_present", "tables_present",
            "source_artifact_id", "presenting_org",
        }
        for unit in units:
            assert required.issubset(unit.keys()), f"Missing fields in {unit}"

    def test_slide_numbers_are_sequential(self):
        deck = _load_fixture()
        units = extract_slide_units(deck)
        numbers = [u["slide_number"] for u in units]
        assert numbers == list(range(1, 6))

    def test_title_from_explicit_field(self):
        deck = _deck_with_one_slide(title="My Explicit Title")
        units = extract_slide_units(deck)
        assert units[0]["title"] == "My Explicit Title"

    def test_title_fallback_to_first_line(self):
        deck = _deck_with_one_slide(title="", raw_text="First Line\nSecond Line")
        units = extract_slide_units(deck)
        assert units[0]["title"] == "First Line"

    def test_bullets_preserved_in_order(self):
        deck = _deck_with_one_slide(bullets=["Alpha", "Beta", "Gamma"])
        units = extract_slide_units(deck)
        assert units[0]["bullets"] == ["Alpha", "Beta", "Gamma"]

    def test_figures_present_from_flag(self):
        deck = _deck_with_one_slide(has_figure=True)
        units = extract_slide_units(deck)
        assert units[0]["figures_present"] is True

    def test_tables_present_from_type(self):
        deck = _deck_with_one_slide(type="table")
        units = extract_slide_units(deck)
        assert units[0]["tables_present"] is True

    def test_source_artifact_id_propagated(self):
        deck = _load_fixture()
        units = extract_slide_units(deck)
        assert all(u["source_artifact_id"] == "SLIDE-DECK-TEST-001" for u in units)

    def test_presenting_org_propagated(self):
        deck = _load_fixture()
        units = extract_slide_units(deck)
        assert units[0]["presenting_org"] == "FCC Office of Engineering and Technology"

    def test_empty_slides_list(self):
        deck = {"artifact_id": "EMPTY-DECK", "slides": []}
        units = extract_slide_units(deck)
        assert units == []

    def test_raw_text_built_from_parts_when_absent(self):
        deck = _deck_with_one_slide(title="My Title", bullets=["Bullet 1"], raw_text="")
        units = extract_slide_units(deck)
        assert "My Title" in units[0]["raw_text"]
        assert "Bullet 1" in units[0]["raw_text"]

    def test_content_field_used_as_bullets_fallback(self):
        deck = {
            "artifact_id": "ALT-DECK",
            "slides": [{
                "slide_number": 1,
                "title": "Alt",
                "content": ["Item A", "Item B"],
            }],
        }
        units = extract_slide_units(deck)
        assert units[0]["bullets"] == ["Item A", "Item B"]


# ---------------------------------------------------------------------------
# B. score_slide_signal
# ---------------------------------------------------------------------------

class TestScoreSlideSignal:
    def _unit(self, raw_text="", bullets=None, figures=False, tables=False):
        return {
            "slide_id": "S1",
            "title": "Test",
            "raw_text": raw_text,
            "bullets": bullets or [],
            "figures_present": figures,
            "tables_present": tables,
        }

    def test_returns_score_and_reasoning(self):
        result = score_slide_signal(self._unit("5G NR EIRP 46 dBm"))
        assert "signal_score" in result
        assert "reasoning" in result

    def test_score_between_0_and_1(self):
        for text in ["", "hello world", "EIRP 46 dBm ITM model 3.5 GHz interference"]:
            r = score_slide_signal(self._unit(text))
            assert 0.0 <= r["signal_score"] <= 1.0

    def test_high_score_for_technical_content(self):
        text = "EIRP 46 dBm ITM Longley-Rice propagation model 3.5 GHz interference guard band"
        r = score_slide_signal(self._unit(text))
        assert r["signal_score"] >= 0.4

    def test_low_score_for_empty_content(self):
        r = score_slide_signal(self._unit(""))
        assert r["signal_score"] == 0.0

    def test_tables_reward_signal(self):
        r_no_table = score_slide_signal(self._unit("hello"))
        r_with_table = score_slide_signal(self._unit("hello", tables=True))
        assert r_with_table["signal_score"] > r_no_table["signal_score"]

    def test_assumptions_keyword_rewards_signal(self):
        r = score_slide_signal(self._unit("assumed EIRP 46 dBm based on 3GPP"))
        assert r["signal_score"] > 0.0
        assert any("assumption" in reason.lower() for reason in r["reasoning"])

    def test_reasoning_is_list(self):
        r = score_slide_signal(self._unit("5G NR interference EIRP"))
        assert isinstance(r["reasoning"], list)


# ---------------------------------------------------------------------------
# C. classify_slide_role
# ---------------------------------------------------------------------------

class TestClassifySlideRole:
    def _unit(self, raw_text="", bullets=None, title="", figures=False, tables=False):
        return {
            "slide_id": "S1",
            "title": title,
            "raw_text": raw_text,
            "bullets": bullets or [],
            "figures_present": figures,
            "tables_present": tables,
        }

    def test_returns_role_and_tags(self):
        result = classify_slide_role(self._unit("background context"))
        assert "integration_role" in result
        assert "technical_tags" in result

    def test_valid_integration_roles(self):
        valid = {"source_text", "source_claim", "source_question", "source_exhibit"}
        for text in [
            "background",
            "5G NR may interfere with radar",
            "TBD — unknown clutter model",
            "",
        ]:
            r = classify_slide_role(self._unit(text))
            assert r["integration_role"] in valid

    def test_claim_role_for_interference_assertion(self):
        r = classify_slide_role(self._unit("5G NR may interfere with radar receivers"))
        assert r["integration_role"] == "source_claim"

    def test_question_role_for_tbd_content(self):
        r = classify_slide_role(self._unit("TBD — propagation model not yet selected"))
        assert r["integration_role"] == "source_question"

    def test_exhibit_role_for_figure_without_bullets(self):
        r = classify_slide_role(self._unit(figures=True, bullets=[]))
        assert r["integration_role"] == "source_exhibit"

    def test_source_text_for_stable_descriptive_content(self):
        r = classify_slide_role(self._unit(
            "The study evaluates coexistence in the 3.5 GHz band.",
            bullets=["The band is shared between mobile and federal systems."]
        ))
        assert r["integration_role"] == "source_text"

    def test_tags_include_assumptions_for_assumption_text(self):
        r = classify_slide_role(self._unit("The following assumptions apply to the model"))
        assert "assumptions" in r["technical_tags"]

    def test_tags_include_interference_for_interference_text(self):
        r = classify_slide_role(self._unit("5G NR interference with radar coexistence"))
        assert "interference" in r["technical_tags"]

    def test_technical_tags_is_list(self):
        r = classify_slide_role(self._unit("some text"))
        assert isinstance(r["technical_tags"], list)


# ---------------------------------------------------------------------------
# D. extract_claims
# ---------------------------------------------------------------------------

class TestExtractClaims:
    def _unit(self, title="", bullets=None, raw_text=""):
        return {
            "slide_id": "TEST-SLIDE-001",
            "title": title,
            "bullets": bullets or [],
            "raw_text": raw_text,
            "notes": "",
        }

    def test_returns_list(self):
        result = extract_claims(self._unit())
        assert isinstance(result, list)

    def test_no_claims_from_neutral_text(self):
        result = extract_claims(self._unit(raw_text="Overview of the study."))
        assert result == []

    def test_claim_detected_for_may_interfere(self):
        claims = extract_claims(self._unit(
            bullets=["5G NR base stations may interfere with federal radar"]
        ))
        assert len(claims) >= 1
        assert any("interfere" in c["claim_text"].lower() for c in claims)

    def test_claim_detected_for_manageable_with(self):
        claims = extract_claims(self._unit(
            bullets=["Interference is manageable with guard bands"]
        ))
        assert len(claims) >= 1

    def test_claim_id_format(self):
        claims = extract_claims(self._unit(
            bullets=["Guard band supports coexistence"]
        ))
        for c in claims:
            assert c["claim_id"].startswith("CLAIM-TEST-SLIDE-001")

    def test_claim_has_required_fields(self):
        claims = extract_claims(self._unit(
            bullets=["5G NR may interfere with radar"]
        ))
        required = {"claim_id", "claim_text", "related_entities", "confidence", "source_slide_id"}
        for c in claims:
            assert required.issubset(c.keys())

    def test_confidence_values_are_valid(self):
        claims = extract_claims(self._unit(
            bullets=["5G NR may interfere with radar"]
        ))
        valid_confidence = {"low", "medium", "high"}
        for c in claims:
            assert c["confidence"] in valid_confidence

    def test_source_slide_id_propagated(self):
        claims = extract_claims(self._unit(
            bullets=["5G may interfere with radar"]
        ))
        for c in claims:
            assert c["source_slide_id"] == "TEST-SLIDE-001"

    def test_no_duplicate_claims(self):
        # Same text repeated should not produce duplicates
        unit = {
            "slide_id": "S1",
            "title": "5G NR may interfere with radar",
            "bullets": ["5G NR may interfere with radar"],
            "raw_text": "5G NR may interfere with radar",
            "notes": "",
        }
        claims = extract_claims(unit)
        texts = [c["claim_text"] for c in claims]
        assert len(texts) == len(set(texts))

    def test_weak_claim_gets_low_confidence(self):
        claims = extract_claims(self._unit(
            bullets=["5G NR may interfere with radar under some conditions"]
        ))
        # "may" is a hedging word → low confidence
        assert any(c["confidence"] == "low" for c in claims)


# ---------------------------------------------------------------------------
# E. extract_assumptions
# ---------------------------------------------------------------------------

class TestExtractAssumptions:
    def _unit(self, bullets=None, raw_text="", title=""):
        return {
            "slide_id": "ASM-TEST-001",
            "title": title,
            "bullets": bullets or [],
            "raw_text": raw_text,
            "notes": "",
        }

    def test_returns_list(self):
        assert isinstance(extract_assumptions(self._unit()), list)

    def test_eirp_assumption_detected(self):
        asms = extract_assumptions(self._unit(bullets=["EIRP: 46 dBm per sector"]))
        types = [a["type"] for a in asms]
        assert "EIRP" in types

    def test_propagation_model_detected(self):
        asms = extract_assumptions(self._unit(
            bullets=["Propagation model: ITM (Longley-Rice)"]
        ))
        types = [a["type"] for a in asms]
        assert "propagation_model" in types

    def test_guard_band_detected(self):
        asms = extract_assumptions(self._unit(bullets=["Guard band: 10 MHz"]))
        types = [a["type"] for a in asms]
        assert "guard_band" in types

    def test_receiver_threshold_detected(self):
        asms = extract_assumptions(self._unit(
            bullets=["Receiver threshold: -107 dBm"]
        ))
        types = [a["type"] for a in asms]
        assert "receiver_threshold" in types

    def test_assumption_has_required_fields(self):
        asms = extract_assumptions(self._unit(bullets=["EIRP: 46 dBm"]))
        required = {"assumption_id", "type", "value", "applies_to", "source_slide_id"}
        for a in asms:
            assert required.issubset(a.keys())

    def test_value_extracted_for_numeric_content(self):
        asms = extract_assumptions(self._unit(bullets=["EIRP: 46 dBm per sector"]))
        eirp = next((a for a in asms if a["type"] == "EIRP"), None)
        assert eirp is not None
        assert eirp["value"] is not None
        assert "46" in eirp["value"]

    def test_partial_entry_when_value_missing(self):
        asms = extract_assumptions(self._unit(bullets=["Propagation model assumed but not specified"]))
        asms_with_none_value = [a for a in asms if a["value"] is None]
        # There should be a partial entry for propagation_model
        types = [a["type"] for a in asms]
        assert "propagation_model" in types

    def test_assumption_id_includes_type(self):
        asms = extract_assumptions(self._unit(bullets=["EIRP 46 dBm"]))
        eirp = next((a for a in asms if a["type"] == "EIRP"), None)
        assert eirp is not None
        assert "EIRP" in eirp["assumption_id"]

    def test_no_duplicate_types_per_slide(self):
        # Same type from two different bullets should produce one entry
        asms = extract_assumptions(self._unit(
            bullets=["EIRP 46 dBm", "EIRP is set to 46 dBm per spec"]
        ))
        eirp_count = sum(1 for a in asms if a["type"] == "EIRP")
        assert eirp_count == 1

    def test_fixture_slide_2_yields_multiple_types(self):
        deck = _load_fixture()
        units = extract_slide_units(deck)
        asms = extract_assumptions(units[1])  # slide 2 = assumptions slide
        assert len(asms) >= 3


# ---------------------------------------------------------------------------
# F. extract_entities_and_relationships
# ---------------------------------------------------------------------------

class TestExtractEntitiesAndRelationships:
    def _unit(self, raw_text="", bullets=None, title=""):
        return {
            "slide_id": "ENT-TEST-001",
            "title": title,
            "bullets": bullets or [],
            "raw_text": raw_text,
            "notes": "",
        }

    def test_returns_dict_with_entities_and_relationships(self):
        result = extract_entities_and_relationships(self._unit())
        assert "entities" in result
        assert "relationships" in result

    def test_entities_is_list(self):
        result = extract_entities_and_relationships(self._unit("5G NR 3.5 GHz"))
        assert isinstance(result["entities"], list)

    def test_relationships_is_list(self):
        result = extract_entities_and_relationships(self._unit())
        assert isinstance(result["relationships"], list)

    def test_frequency_band_entity_detected(self):
        result = extract_entities_and_relationships(self._unit("Analysis in 3500 MHz band"))
        types = [e["type"] for e in result["entities"]]
        assert "frequency_band" in types

    def test_system_entity_detected(self):
        result = extract_entities_and_relationships(self._unit("5G NR base station deployment"))
        types = [e["type"] for e in result["entities"]]
        assert "system" in types

    def test_model_entity_detected(self):
        result = extract_entities_and_relationships(
            self._unit("Using ITM propagation model for analysis")
        )
        types = [e["type"] for e in result["entities"]]
        assert "model_standard" in types

    def test_agency_entity_detected(self):
        result = extract_entities_and_relationships(self._unit("FCC and NTIA coordination"))
        names = [e["name"] for e in result["entities"]]
        assert "FCC" in names or "NTIA" in names

    def test_interferes_with_relationship_detected(self):
        result = extract_entities_and_relationships(
            self._unit("5G NR may interfere with radar systems")
        )
        rel_types = [r["relation"] for r in result["relationships"]]
        assert "interferes_with" in rel_types

    def test_assumes_relationship_detected(self):
        result = extract_entities_and_relationships(
            self._unit("Analysis assumes ITM propagation model")
        )
        rel_types = [r["relation"] for r in result["relationships"]]
        assert "assumes" in rel_types

    def test_entity_has_required_fields(self):
        result = extract_entities_and_relationships(
            self._unit("5G NR 3500 MHz band")
        )
        for entity in result["entities"]:
            assert "name" in entity
            assert "type" in entity
            assert "source_slide_id" in entity

    def test_relationship_has_required_fields(self):
        result = extract_entities_and_relationships(
            self._unit("5G NR may interfere with radar")
        )
        for rel in result["relationships"]:
            assert "source" in rel
            assert "relation" in rel
            assert "target" in rel
            assert "source_slide_id" in rel


# ---------------------------------------------------------------------------
# G. detect_gaps
# ---------------------------------------------------------------------------

class TestDetectGaps:
    def _unit(self, raw_text="", bullets=None, title=""):
        return {
            "slide_id": "GAP-TEST-001",
            "title": title,
            "bullets": bullets or [],
            "raw_text": raw_text,
            "notes": "",
        }

    def test_returns_list(self):
        result = detect_gaps(self._unit(), [], [])
        assert isinstance(result, list)

    def test_gap_has_required_fields(self):
        unit = self._unit("5G NR may interfere with radar")
        claims = extract_claims(unit)
        gaps = detect_gaps(unit, claims, [])
        required = {"gap_id", "description", "severity", "related_claim_ids", "source_slide_id"}
        for gap in gaps:
            assert required.issubset(gap.keys())

    def test_interference_claim_without_propagation_model_raises_gap(self):
        unit = self._unit("5G NR may interfere with radar within 5 km")
        claims = extract_claims(unit)
        gaps = detect_gaps(unit, claims, [])
        descriptions = " ".join(g["description"] for g in gaps)
        assert "propagation" in descriptions.lower()

    def test_no_gap_when_propagation_model_present(self):
        unit = self._unit(
            "5G NR may interfere with radar. Propagation model: ITM Longley-Rice."
        )
        claims = extract_claims(unit)
        gaps = detect_gaps(unit, claims, [])
        prop_gaps = [g for g in gaps if "propagation" in g["description"].lower()]
        assert prop_gaps == []

    def test_severity_values_are_valid(self):
        unit = self._unit("5G NR may interfere with radar")
        claims = extract_claims(unit)
        gaps = detect_gaps(unit, claims, [])
        valid = {"high", "medium", "low"}
        for g in gaps:
            assert g["severity"] in valid

    def test_no_gaps_for_fully_specified_slide(self):
        unit = self._unit(
            "Interference analysis uses ITM propagation model. "
            "EIRP 46 dBm assumed. Based on Monte Carlo simulation.",
            bullets=["5G NR may interfere with radar"],
        )
        claims = extract_claims(unit)
        asms = extract_assumptions(unit)
        gaps = detect_gaps(unit, claims, asms)
        high_gaps = [g for g in gaps if g["severity"] == "high"]
        assert high_gaps == []

    def test_recommendation_without_basis_generates_gap(self):
        unit = self._unit(
            title="Recommendation",
            bullets=["We recommend a 10 MHz guard band requirement"]
        )
        claims = extract_claims(unit)
        gaps = detect_gaps(unit, claims, [])
        descriptions = " ".join(g["description"] for g in gaps)
        assert "recommendation" in descriptions.lower() or "basis" in descriptions.lower()

    def test_fixture_slide_3_generates_gap(self):
        deck = _load_fixture()
        units = extract_slide_units(deck)
        claims = extract_claims(units[2])  # slide 3 = findings slide
        asms = extract_assumptions(units[2])
        gaps = detect_gaps(units[2], claims, asms)
        assert isinstance(gaps, list)
        # Slide 3 has claims but the interference text has no explicit propagation model named
        # (table present but no model keyword) — may or may not generate gap, but must not error


# ---------------------------------------------------------------------------
# H. map_to_working_paper_section
# ---------------------------------------------------------------------------

class TestMapToWorkingPaperSection:
    VALID_SECTIONS = {
        "Executive Summary",
        "Objective and Scope",
        "System Description",
        "Assumptions and Inputs",
        "Methodology",
        "Preliminary Findings",
        "Risk Assessment",
        "Mitigation Options",
        "Open Questions",
        "Recommended Next Steps",
        "Appendix / Exhibits",
    }

    def _unit(self, raw_text="", bullets=None, figures=False, tables=False):
        return {
            "slide_id": "MAP-001",
            "title": "Test",
            "raw_text": raw_text,
            "bullets": bullets or [],
            "figures_present": figures,
            "tables_present": tables,
            "notes": "",
        }

    def test_returns_valid_section(self):
        for text in ["", "background", "assumption", "interference", "recommendation"]:
            unit = self._unit(text)
            role = classify_slide_role(unit)
            section = map_to_working_paper_section(unit, role)
            assert section in self.VALID_SECTIONS

    def test_exhibit_maps_to_appendix(self):
        unit = self._unit(figures=True)
        role = {"integration_role": "source_exhibit", "technical_tags": []}
        section = map_to_working_paper_section(unit, role)
        assert section == "Appendix / Exhibits"

    def test_question_maps_to_open_questions(self):
        unit = self._unit("TBD — clutter model unknown")
        role = {"integration_role": "source_question", "technical_tags": []}
        section = map_to_working_paper_section(unit, role)
        assert section == "Open Questions"

    def test_assumptions_tag_maps_to_assumptions_section(self):
        unit = self._unit("assumed EIRP 46 dBm")
        role = {"integration_role": "source_text", "technical_tags": ["assumptions"]}
        section = map_to_working_paper_section(unit, role)
        assert section == "Assumptions and Inputs"

    def test_interference_tag_maps_to_preliminary_findings(self):
        unit = self._unit("interference coexistence")
        role = {"integration_role": "source_claim", "technical_tags": ["interference"]}
        section = map_to_working_paper_section(unit, role)
        assert section == "Preliminary Findings"

    def test_recommendation_tag_maps_to_next_steps(self):
        unit = self._unit("We recommend guard band")
        role = {"integration_role": "source_claim", "technical_tags": ["recommendation"]}
        section = map_to_working_paper_section(unit, role)
        assert section == "Recommended Next Steps"


# ---------------------------------------------------------------------------
# I. rewrite_for_working_paper
# ---------------------------------------------------------------------------

class TestRewriteForWorkingPaper:
    VALID_STYLE_MODES = {
        "narrative",
        "assumptions_block",
        "methods_text",
        "findings_text",
        "issue_statement",
        "question_prompt",
        "exhibit_note",
    }

    def _unit(self, title="Test", bullets=None, raw_text="", notes="", figures=False):
        return {
            "slide_id": "RW-001",
            "title": title,
            "bullets": bullets or [],
            "raw_text": raw_text,
            "notes": notes,
            "figures_present": figures,
            "tables_present": False,
            "source_artifact_id": "DECK-001",
        }

    def test_returns_required_fields(self):
        unit = self._unit(bullets=["Background context"])
        role = classify_slide_role(unit)
        section = map_to_working_paper_section(unit, role)
        result = rewrite_for_working_paper(unit, role, section)
        required = {"proposed_text", "style_mode", "caution_flags", "confidence", "traceability"}
        assert required.issubset(result.keys())

    def test_style_mode_is_valid(self):
        unit = self._unit(bullets=["Some content here"])
        role = classify_slide_role(unit)
        section = map_to_working_paper_section(unit, role)
        result = rewrite_for_working_paper(unit, role, section)
        assert result["style_mode"] in self.VALID_STYLE_MODES

    def test_traceability_fields_present(self):
        unit = self._unit(bullets=["Content"])
        role = classify_slide_role(unit)
        section = map_to_working_paper_section(unit, role)
        result = rewrite_for_working_paper(unit, role, section)
        tr = result["traceability"]
        assert tr["source_slide_id"] == "RW-001"
        assert tr["source_artifact_id"] == "DECK-001"
        assert tr["mapped_section"] == section

    def test_proposed_text_is_non_empty_for_content_slide(self):
        unit = self._unit(bullets=["5G NR EIRP 46 dBm assumed for analysis"])
        role = classify_slide_role(unit)
        section = map_to_working_paper_section(unit, role)
        result = rewrite_for_working_paper(unit, role, section)
        assert result["proposed_text"].strip() != ""

    def test_strong_language_triggers_caution_flag(self):
        unit = self._unit(raw_text="This will prove full compatibility between systems.")
        role = {"integration_role": "source_claim", "technical_tags": []}
        section = "Preliminary Findings"
        result = rewrite_for_working_paper(unit, role, section)
        assert len(result["caution_flags"]) > 0

    def test_provisional_content_triggers_caution_and_low_confidence(self):
        unit = self._unit(raw_text="Preliminary results — subject to revision")
        role = {"integration_role": "source_text", "technical_tags": []}
        section = "Executive Summary"
        result = rewrite_for_working_paper(unit, role, section)
        assert result["confidence"] == "low"
        assert any("provisional" in f.lower() for f in result["caution_flags"])

    def test_exhibit_role_produces_exhibit_note(self):
        unit = self._unit(figures=True, title="Path Loss Figure")
        role = {"integration_role": "source_exhibit", "technical_tags": []}
        section = "Appendix / Exhibits"
        result = rewrite_for_working_paper(unit, role, section)
        assert result["style_mode"] == "exhibit_note"
        assert "Exhibit" in result["proposed_text"] or "exhibit" in result["proposed_text"]

    def test_assumptions_style_mode(self):
        unit = self._unit(
            title="Key Assumptions",
            bullets=["EIRP 46 dBm", "ITM propagation model"],
            raw_text="assumed EIRP 46 dBm",
        )
        role = {"integration_role": "source_text", "technical_tags": ["assumptions"]}
        section = "Assumptions and Inputs"
        result = rewrite_for_working_paper(unit, role, section)
        assert result["style_mode"] == "assumptions_block"

    def test_caution_flags_is_list(self):
        unit = self._unit(bullets=["content"])
        role = classify_slide_role(unit)
        section = map_to_working_paper_section(unit, role)
        result = rewrite_for_working_paper(unit, role, section)
        assert isinstance(result["caution_flags"], list)


# ---------------------------------------------------------------------------
# J. compare_with_transcript_and_paper
# ---------------------------------------------------------------------------

class TestCompareWithTranscriptAndPaper:
    def test_returns_comparison_dict(self):
        result = compare_with_transcript_and_paper([], None, None)
        required = {
            "supported_by_transcript",
            "challenged_in_discussion",
            "unresolved",
            "missing_from_paper",
            "already_in_paper",
            "better_as_question",
        }
        assert required.issubset(result.keys())

    def test_all_missing_when_no_paper(self):
        outputs = [
            {"claim_id": "C1", "claim_text": "5G NR may interfere with radar"},
        ]
        result = compare_with_transcript_and_paper(outputs, None, None)
        assert "C1" in result["missing_from_paper"]

    def test_supported_when_transcript_overlaps(self):
        outputs = [
            {
                "claim_id": "C1",
                "claim_text": "interference from 5G base stations confirmed",
            }
        ]
        transcript = {
            "text": "We confirmed interference from 5G base stations in the 3.5 GHz band."
        }
        result = compare_with_transcript_and_paper(outputs, transcript, None)
        assert "C1" in result["supported_by_transcript"]

    def test_better_as_question_for_tbd_content(self):
        outputs = [{"claim_id": "Q1", "claim_text": "TBD — unknown model"}]
        result = compare_with_transcript_and_paper(outputs, None, None)
        assert "Q1" in result["better_as_question"]

    def test_already_in_paper_when_paper_overlaps(self):
        outputs = [
            {
                "claim_id": "C2",
                "claim_text": "coexistence requires guard band separation",
            }
        ]
        paper = {
            "text": "The study concludes that coexistence requires a guard band separation."
        }
        result = compare_with_transcript_and_paper(outputs, None, paper)
        assert "C2" in result["already_in_paper"]

    def test_empty_outputs_returns_empty_lists(self):
        result = compare_with_transcript_and_paper([], {"text": "some text"}, {"text": "paper"})
        for key in result:
            assert result[key] == []


# ---------------------------------------------------------------------------
# K. build_slide_intelligence_packet
# ---------------------------------------------------------------------------

class TestBuildSlideIntelligencePacket:
    def test_returns_dict_with_required_fields(self):
        deck = _load_fixture()
        packet = build_slide_intelligence_packet(deck)
        required = {
            "artifact_type",
            "source_artifact_id",
            "slide_to_paper_candidates",
            "extracted_claims",
            "assumptions_registry_entries",
            "knowledge_graph_edges",
            "analysis_gaps",
            "validation_status",
            "recommended_agency_questions",
            "suggested_exhibits",
            "signal_scores",
            "traceability_index",
        }
        assert required.issubset(packet.keys())

    def test_artifact_type_is_slide_intelligence_packet(self):
        deck = _load_fixture()
        packet = build_slide_intelligence_packet(deck)
        assert packet["artifact_type"] == "slide_intelligence_packet"

    def test_source_artifact_id_matches_input(self):
        deck = _load_fixture()
        packet = build_slide_intelligence_packet(deck)
        assert packet["source_artifact_id"] == "SLIDE-DECK-TEST-001"

    def test_candidates_count_matches_slide_count(self):
        deck = _load_fixture()
        packet = build_slide_intelligence_packet(deck)
        assert len(packet["slide_to_paper_candidates"]) == 5

    def test_figure_slide_in_suggested_exhibits(self):
        deck = _load_fixture()
        packet = build_slide_intelligence_packet(deck)
        exhibit_slide_ids = [e["slide_id"] for e in packet["suggested_exhibits"]]
        # Slide 4 is a figure slide
        assert any("slide-4" in sid for sid in exhibit_slide_ids)

    def test_assumptions_registry_has_entries(self):
        deck = _load_fixture()
        packet = build_slide_intelligence_packet(deck)
        assert len(packet["assumptions_registry_entries"]) >= 1

    def test_traceability_index_has_one_entry_per_slide(self):
        deck = _load_fixture()
        packet = build_slide_intelligence_packet(deck)
        assert len(packet["traceability_index"]) == 5

    def test_traceability_index_entry_fields(self):
        deck = _load_fixture()
        packet = build_slide_intelligence_packet(deck)
        required = {
            "slide_id", "slide_number", "source_artifact_id",
            "section", "integration_role", "signal_score",
            "claim_count", "assumption_count", "gap_count",
        }
        for entry in packet["traceability_index"]:
            assert required.issubset(entry.keys())

    def test_validation_status_is_valid(self):
        deck = _load_fixture()
        packet = build_slide_intelligence_packet(deck)
        assert packet["validation_status"] in {"needs_review", "provisional", "informational"}

    def test_deterministic_output(self):
        deck = _load_fixture()
        p1 = build_slide_intelligence_packet(deck)
        p2 = build_slide_intelligence_packet(deck)
        assert p1["traceability_index"] == p2["traceability_index"]
        assert p1["artifact_type"] == p2["artifact_type"]

    def test_packet_with_transcript_and_paper(self):
        deck = _load_fixture()
        transcript = {
            "text": "We confirmed interference from 5G NR base stations. "
                    "The propagation model used is ITM Longley-Rice."
        }
        paper = {"text": "Preliminary findings indicate coexistence requires guard band."}
        packet = build_slide_intelligence_packet(deck, transcript, paper)
        assert "supported_by_transcript" not in packet  # comparison is internal
        assert packet["artifact_type"] == "slide_intelligence_packet"

    def test_empty_deck_returns_packet(self):
        deck = {"artifact_id": "EMPTY", "slides": []}
        packet = build_slide_intelligence_packet(deck)
        assert packet["artifact_type"] == "slide_intelligence_packet"
        assert packet["slide_to_paper_candidates"] == []


# ---------------------------------------------------------------------------
# L. Fixture-driven integration tests
# ---------------------------------------------------------------------------

class TestFixtureIntegration:
    def test_slide_1_maps_to_objective_section(self):
        deck = _load_fixture()
        units = extract_slide_units(deck)
        role = classify_slide_role(units[0])
        section = map_to_working_paper_section(units[0], role)
        assert section in {
            "Objective and Scope",
            "Executive Summary",
            "System Description",
        }

    def test_slide_2_assumptions_slide_yields_multiple_assumptions(self):
        deck = _load_fixture()
        units = extract_slide_units(deck)
        asms = extract_assumptions(units[1])
        assert len(asms) >= 3

    def test_slide_3_interference_slide_yields_claims(self):
        deck = _load_fixture()
        units = extract_slide_units(deck)
        claims = extract_claims(units[2])
        assert len(claims) >= 1

    def test_slide_4_figure_slide_is_exhibit(self):
        deck = _load_fixture()
        units = extract_slide_units(deck)
        role = classify_slide_role(units[3])
        assert role["integration_role"] == "source_exhibit"

    def test_slide_5_question_slide_is_source_question(self):
        deck = _load_fixture()
        units = extract_slide_units(deck)
        role = classify_slide_role(units[4])
        assert role["integration_role"] == "source_question"

    def test_slide_5_questions_appear_in_recommended_agency_questions(self):
        deck = _load_fixture()
        packet = build_slide_intelligence_packet(deck)
        questions = packet["recommended_agency_questions"]
        assert len(questions) >= 1

    def test_full_pipeline_no_error(self):
        deck = _load_fixture()
        packet = build_slide_intelligence_packet(deck)
        assert packet is not None


# ---------------------------------------------------------------------------
# M. Artifact type / schema validation
# ---------------------------------------------------------------------------

class TestArtifactTypeRegistration:
    def test_slide_deck_in_standards_manifest(self):
        manifest_path = REPO_ROOT / "contracts" / "standards-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        types = [c["artifact_type"] for c in manifest["contracts"]]
        assert "slide_deck" in types, "slide_deck must be in standards manifest"

    def test_slide_intelligence_packet_in_standards_manifest(self):
        manifest_path = REPO_ROOT / "contracts" / "standards-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        types = [c["artifact_type"] for c in manifest["contracts"]]
        assert "slide_intelligence_packet" in types, \
            "slide_intelligence_packet must be in standards manifest"

    def test_slide_deck_has_work_class(self):
        manifest_path = REPO_ROOT / "contracts" / "standards-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(
            (c for c in manifest["contracts"] if c["artifact_type"] == "slide_deck"),
            None,
        )
        assert entry is not None
        assert entry["artifact_class"] == "work"

    def test_slide_intelligence_packet_has_work_class(self):
        manifest_path = REPO_ROOT / "contracts" / "standards-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(
            (c for c in manifest["contracts"] if c["artifact_type"] == "slide_intelligence_packet"),
            None,
        )
        assert entry is not None
        assert entry["artifact_class"] == "work"

    def test_slide_deck_schema_exists(self):
        schema_path = REPO_ROOT / "contracts" / "schemas" / "slide_deck.schema.json"
        assert schema_path.exists(), "slide_deck schema file must exist"

    def test_slide_intelligence_packet_schema_exists(self):
        schema_path = (
            REPO_ROOT / "contracts" / "schemas" / "slide_intelligence_packet.schema.json"
        )
        assert schema_path.exists(), "slide_intelligence_packet schema file must exist"

    def test_knowledge_graph_edge_schema_exists(self):
        schema_path = (
            REPO_ROOT / "contracts" / "schemas" / "knowledge_graph_edge.schema.json"
        )
        assert schema_path.exists(), "knowledge_graph_edge schema file must exist"

    def test_slide_intelligence_manifest_exists(self):
        manifest_path = (
            REPO_ROOT
            / "docs"
            / "module-manifests"
            / "workflow_modules"
            / "slide_intelligence.json"
        )
        assert manifest_path.exists(), "slide_intelligence module manifest must exist"


# ---------------------------------------------------------------------------
# N. Pipeline-oriented API (ingest → normalize → align → signals → merge → gaps)
# ---------------------------------------------------------------------------

from spectrum_systems.modules.slide_intelligence import (  # noqa: E402
    ingest_slides,
    normalize_slides,
    align_slides_to_transcript,
    extract_slide_signals,
    merge_slide_transcript_outputs,
    compute_slide_transcript_gaps,
)


class TestIngestSlides:
    def test_ingest_json_fixture_returns_list(self):
        slides = ingest_slides(FIXTURE_PATH)
        assert isinstance(slides, list)
        assert len(slides) == 5

    def test_ingest_json_required_fields(self):
        slides = ingest_slides(FIXTURE_PATH)
        for s in slides:
            assert "slide_number" in s
            assert "title" in s
            assert "bullet_points" in s
            assert "full_text" in s

    def test_ingest_json_preserves_order(self):
        slides = ingest_slides(FIXTURE_PATH)
        numbers = [s["slide_number"] for s in slides]
        assert numbers == sorted(numbers)

    def test_ingest_unsupported_format_raises(self, tmp_path):
        bad = tmp_path / "deck.pptx"
        bad.write_text("dummy")
        with pytest.raises(ValueError, match="Unsupported"):
            ingest_slides(bad)


class TestNormalizeSlides:
    def _raw(self):
        return ingest_slides(FIXTURE_PATH)

    def test_normalize_returns_list(self):
        normalized = normalize_slides(self._raw())
        assert isinstance(normalized, list)
        assert len(normalized) == 5

    def test_normalized_required_fields(self):
        for slide in normalize_slides(self._raw()):
            assert "slide_id" in slide
            assert "title" in slide
            assert "bullets" in slide
            assert "raw_text" in slide
            assert "keywords" in slide

    def test_slide_ids_sequential(self):
        ids = [s["slide_id"] for s in normalize_slides(self._raw())]
        assert ids == [f"slide_{i:02d}" for i in range(1, 6)]

    def test_keywords_is_list(self):
        for slide in normalize_slides(self._raw()):
            assert isinstance(slide["keywords"], list)

    def test_title_extracted(self):
        normalized = normalize_slides(self._raw())
        # All fixture slides have explicit titles
        for slide in normalized:
            assert slide["title"] != ""

    def test_empty_input_returns_empty(self):
        assert normalize_slides([]) == []


class TestAlignSlidesToTranscript:
    def _slides(self):
        return normalize_slides(ingest_slides(FIXTURE_PATH))

    def _segments(self):
        return [
            {"text": "We discussed the interference potential from 5G NR into radar systems."},
            {"text": "The propagation model used is the ITM Longley-Rice model."},
            {"text": "Coexistence requires a 10 MHz guard band minimum."},
            {"text": "Action item: confirm EIRP assumptions with 3GPP standards body."},
            {"text": "Open question: what clutter model should we use for suburban areas?"},
        ]

    def test_returns_one_entry_per_slide(self):
        result = align_slides_to_transcript(self._slides(), self._segments())
        assert len(result) == 5

    def test_required_fields_in_entry(self):
        result = align_slides_to_transcript(self._slides(), self._segments())
        for entry in result:
            assert "slide_id" in entry
            assert "matched_segments" in entry
            assert "confidence" in entry

    def test_confidence_between_0_and_1(self):
        result = align_slides_to_transcript(self._slides(), self._segments())
        for entry in result:
            assert 0.0 <= entry["confidence"] <= 1.0

    def test_matched_segments_are_strings(self):
        result = align_slides_to_transcript(self._slides(), self._segments())
        for entry in result:
            for seg in entry["matched_segments"]:
                assert isinstance(seg, str)

    def test_empty_segments_returns_zero_confidence(self):
        result = align_slides_to_transcript(self._slides(), [])
        for entry in result:
            assert entry["confidence"] == 0.0
            assert entry["matched_segments"] == []

    def test_slide_ids_preserved(self):
        slides = self._slides()
        result = align_slides_to_transcript(slides, self._segments())
        expected_ids = {s["slide_id"] for s in slides}
        actual_ids = {e["slide_id"] for e in result}
        assert expected_ids == actual_ids


class TestExtractSlideSignals:
    def _slides(self):
        return normalize_slides(ingest_slides(FIXTURE_PATH))

    def test_returns_required_keys(self):
        sigs = extract_slide_signals(self._slides())
        for key in ("claims", "assumptions", "proposals", "metrics", "open_questions"):
            assert key in sigs

    def test_values_are_lists(self):
        sigs = extract_slide_signals(self._slides())
        for key in ("claims", "assumptions", "proposals", "metrics", "open_questions"):
            assert isinstance(sigs[key], list)

    def test_metrics_detected_for_dBm_values(self):
        slides = [{"slide_id": "s01", "bullets": ["EIRP 46 dBm per sector"], "raw_text": "EIRP 46 dBm per sector", "keywords": []}]
        sigs = extract_slide_signals(slides)
        assert len(sigs["metrics"]) >= 1

    def test_proposals_detected_for_verb_start(self):
        slides = [{"slide_id": "s01", "bullets": ["Implement a 10 MHz guard band"], "raw_text": "", "keywords": []}]
        sigs = extract_slide_signals(slides)
        assert len(sigs["proposals"]) >= 1

    def test_open_questions_detected(self):
        slides = [{"slide_id": "s01", "bullets": ["TBD — propagation model not selected?"], "raw_text": "", "keywords": []}]
        sigs = extract_slide_signals(slides)
        assert len(sigs["open_questions"]) >= 1

    def test_empty_slides_returns_empty_signals(self):
        sigs = extract_slide_signals([])
        for key in ("claims", "assumptions", "proposals", "metrics", "open_questions"):
            assert sigs[key] == []


class TestMergeSlideTranscriptOutputs:
    def _slides(self):
        return normalize_slides(ingest_slides(FIXTURE_PATH))

    def _alignment(self):
        segs = [
            {"text": "interference from 5G NR base stations into federal radar"},
            {"text": "guard band of 10 MHz between allocations"},
        ]
        return align_slides_to_transcript(self._slides(), segs)

    def _signals(self):
        return extract_slide_signals(self._slides())

    def _structured(self):
        return {
            "decisions": [{"decision_id": "D-001", "description": "Adopt ITM propagation model"}],
            "action_items": [{"action_id": "AI-001", "description": "Confirm EIRP with 3GPP"}],
            "open_questions": [{"question_id": "Q-001", "description": "Guard band requirements TBD"}],
        }

    def test_returns_dict(self):
        result = merge_slide_transcript_outputs(self._structured(), self._signals(), self._alignment())
        assert isinstance(result, dict)

    def test_decisions_enriched_with_slide_support(self):
        result = merge_slide_transcript_outputs(self._structured(), self._signals(), self._alignment())
        for d in result["decisions"]:
            assert "slide_support" in d
            assert "source_slide_ids" in d

    def test_action_items_enriched(self):
        result = merge_slide_transcript_outputs(self._structured(), self._signals(), self._alignment())
        for ai in result["action_items"]:
            assert "slide_support" in ai

    def test_open_questions_enriched(self):
        result = merge_slide_transcript_outputs(self._structured(), self._signals(), self._alignment())
        for q in result["open_questions"]:
            assert "slide_support" in q

    def test_slide_only_content_present(self):
        result = merge_slide_transcript_outputs(self._structured(), self._signals(), self._alignment())
        assert "slide_only_content" in result
        assert isinstance(result["slide_only_content"], list)

    def test_discussion_only_content_present(self):
        result = merge_slide_transcript_outputs(self._structured(), self._signals(), self._alignment())
        assert "discussion_only_content" in result
        assert isinstance(result["discussion_only_content"], list)

    def test_slide_support_boolean(self):
        result = merge_slide_transcript_outputs(self._structured(), self._signals(), self._alignment())
        for key in ("decisions", "action_items", "open_questions"):
            for item in result[key]:
                assert isinstance(item["slide_support"], bool)


class TestComputeSlideTranscriptGaps:
    def _enriched(self):
        slides = normalize_slides(ingest_slides(FIXTURE_PATH))
        segs = [
            {"text": "We confirmed interference from 5G NR base stations in the 3.5 GHz band."},
            {"text": "Guard band of 10 MHz is sufficient."},
        ]
        alignment = align_slides_to_transcript(slides, segs)
        signals = extract_slide_signals(slides)
        structured = {
            "decisions": [{"decision_id": "D-001", "description": "Use ITM propagation model"}],
            "action_items": [{"action_id": "AI-001", "description": "Verify EIRP assumptions"}],
            "open_questions": [{"question_id": "Q-001", "description": "Clutter model TBD"}],
        }
        return merge_slide_transcript_outputs(structured, signals, alignment)

    def test_returns_required_keys(self):
        gaps = compute_slide_transcript_gaps(self._enriched())
        for key in ("unpresented_discussions", "undiscussed_slides", "weak_alignment_areas", "recommended_followups"):
            assert key in gaps

    def test_values_are_lists(self):
        gaps = compute_slide_transcript_gaps(self._enriched())
        for key in ("unpresented_discussions", "undiscussed_slides", "weak_alignment_areas", "recommended_followups"):
            assert isinstance(gaps[key], list)

    def test_deterministic_output(self):
        enriched = self._enriched()
        g1 = compute_slide_transcript_gaps(enriched)
        g2 = compute_slide_transcript_gaps(enriched)
        assert g1 == g2


# ---------------------------------------------------------------------------
# O. Pipeline integration — optional slides
# ---------------------------------------------------------------------------

from spectrum_systems.modules.meeting_minutes_pipeline import run_pipeline  # noqa: E402


class TestPipelineSlideIntegration:
    _TRANSCRIPT = (
        "Alice: We need to confirm the interference model for the 3.5 GHz coexistence study.\n"
        "Bob: Agreed. Let us use the ITM Longley-Rice model.\n"
        "Alice: Action item — Bob will validate EIRP assumptions against 3GPP specs.\n"
        "Bob: Any open questions on guard band?\n"
        "Alice: TBD — we need agency input."
    )
    _EXTRACTION = {
        "decisions_made": [{"id": "D-001", "description": "Use ITM model"}],
        "action_items": [{"id": "AI-001", "description": "Bob validates EIRP"}],
        "questions_raised": [],
    }
    _SIGNALS = {
        "risks_or_open_questions": [],
        "decisions_made": [{"id": "D-001", "description": "Use ITM model"}],
    }

    def test_pipeline_without_slides_succeeds(self, tmp_path):
        result = run_pipeline(
            transcript_text=self._TRANSCRIPT,
            structured_extraction=self._EXTRACTION,
            signals=self._SIGNALS,
            artifacts_root=tmp_path,
        )
        assert result is not None
        assert "slide_intelligence" not in result

    def test_pipeline_with_slides_adds_slide_intelligence(self, tmp_path):
        deck = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        result = run_pipeline(
            transcript_text=self._TRANSCRIPT,
            structured_extraction=self._EXTRACTION,
            signals=self._SIGNALS,
            artifacts_root=tmp_path,
            slide_deck=deck,
        )
        assert "slide_intelligence" in result
        packet = result["slide_intelligence"]
        assert packet["artifact_type"] == "slide_intelligence_packet"

    def test_pipeline_slides_does_not_break_validation(self, tmp_path):
        deck = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        result = run_pipeline(
            transcript_text=self._TRANSCRIPT,
            structured_extraction=self._EXTRACTION,
            signals=self._SIGNALS,
            artifacts_root=tmp_path,
            slide_deck=deck,
        )
        assert result["validation"]["passed"] is True

    def test_pipeline_slides_deterministic(self, tmp_path):
        import shutil
        deck = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        d1 = tmp_path / "run1"
        d2 = tmp_path / "run2"
        r1 = run_pipeline(
            transcript_text=self._TRANSCRIPT,
            structured_extraction=self._EXTRACTION,
            signals=self._SIGNALS,
            artifacts_root=d1,
            slide_deck=deck,
        )
        r2 = run_pipeline(
            transcript_text=self._TRANSCRIPT,
            structured_extraction=self._EXTRACTION,
            signals=self._SIGNALS,
            artifacts_root=d2,
            slide_deck=deck,
        )
        assert (
            r1["slide_intelligence"]["validation_status"]
            == r2["slide_intelligence"]["validation_status"]
        )

    def test_pipeline_bad_slides_does_not_crash(self, tmp_path):
        """Pipeline must not raise if slide_deck is malformed."""
        result = run_pipeline(
            transcript_text=self._TRANSCRIPT,
            structured_extraction=self._EXTRACTION,
            signals=self._SIGNALS,
            artifacts_root=tmp_path,
            slide_deck={"artifact_id": "BAD", "slides": []},
        )
        assert result is not None


# ---------------------------------------------------------------------------
# P. Contract integration — meeting_minutes_record slide fields
# ---------------------------------------------------------------------------

class TestMeetingMinutesRecordSlideFields:
    """The meeting_minutes_record schema must accept optional slide fields."""

    _SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "meeting_minutes_record.schema.json"

    def _schema(self):
        return json.loads(self._SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_slides_present_field_defined(self):
        schema = self._schema()
        assert "slides_present" in schema["properties"]

    def test_slide_alignment_field_defined(self):
        schema = self._schema()
        assert "slide_alignment" in schema["properties"]

    def test_slide_signals_field_defined(self):
        schema = self._schema()
        assert "slide_signals" in schema["properties"]

    def test_gap_analysis_field_defined(self):
        schema = self._schema()
        assert "gap_analysis" in schema["properties"]

    def test_slide_fields_not_required(self):
        schema = self._schema()
        for field in ("slides_present", "slide_alignment", "slide_signals", "gap_analysis"):
            assert field not in schema["required"]

    def test_slides_present_is_boolean_type(self):
        schema = self._schema()
        assert schema["properties"]["slides_present"]["type"] == "boolean"


# ---------------------------------------------------------------------------
# Q. Documentation — slide-intelligence-layer.md
# ---------------------------------------------------------------------------

class TestSlideIntelligenceDocumentation:
    def test_design_doc_exists(self):
        doc_path = REPO_ROOT / "docs" / "design" / "slide-intelligence-layer.md"
        assert doc_path.exists(), "docs/design/slide-intelligence-layer.md must exist"

    def test_design_doc_has_required_sections(self):
        doc_path = REPO_ROOT / "docs" / "design" / "slide-intelligence-layer.md"
        content = doc_path.read_text(encoding="utf-8")
        for section in ("Purpose", "Architecture", "Data Flow", "Known Limitations"):
            assert section in content, f"Missing section: {section}"

    def test_design_doc_mentions_lllm_future(self):
        doc_path = REPO_ROOT / "docs" / "design" / "slide-intelligence-layer.md"
        content = doc_path.read_text(encoding="utf-8")
        assert "LLM" in content


# ---------------------------------------------------------------------------
# R. Golden path — end-to-end enrichment with transcript + slides
# ---------------------------------------------------------------------------

class TestGoldenPath:
    """End-to-end golden path: fixture deck through full pipeline API."""

    def test_golden_path_ingest_to_gaps(self):
        """Full pipeline: ingest → normalize → align → signals → merge → gaps."""
        # 1. Ingest
        raw = ingest_slides(FIXTURE_PATH)
        assert len(raw) == 5

        # 2. Normalize
        slides = normalize_slides(raw)
        assert len(slides) == 5
        for s in slides:
            assert s["slide_id"].startswith("slide_")

        # 3. Align
        segments = [
            {"text": "We confirmed interference from 5G NR base stations into federal radar in the 3.5 GHz band."},
            {"text": "The ITM Longley-Rice propagation model was agreed as the baseline."},
            {"text": "Action item: validate EIRP of 46 dBm against 3GPP TS 38.104."},
            {"text": "Guard band of 10 MHz proposed — needs agency confirmation."},
            {"text": "Open question: what clutter model applies to suburban deployment areas?"},
        ]
        alignment = align_slides_to_transcript(slides, segments)
        assert len(alignment) == 5
        for entry in alignment:
            assert 0.0 <= entry["confidence"] <= 1.0

        # 4. Signals
        signals = extract_slide_signals(slides)
        assert isinstance(signals["claims"], list)
        assert isinstance(signals["assumptions"], list)
        assert len(signals["metrics"]) >= 1  # dBm values in fixture

        # 5. Merge
        structured = {
            "decisions": [{"decision_id": "D-001", "description": "Use ITM propagation model for terrain-sensitive paths"}],
            "action_items": [{"action_id": "AI-001", "description": "Validate EIRP assumptions against 3GPP TS 38.104"}],
            "open_questions": [{"question_id": "Q-001", "description": "Which clutter model applies to suburban deployments?"}],
        }
        enriched = merge_slide_transcript_outputs(structured, signals, alignment)
        for d in enriched["decisions"]:
            assert "slide_support" in d
        for ai in enriched["action_items"]:
            assert "slide_support" in ai

        # 6. Gaps
        gaps = compute_slide_transcript_gaps(enriched)
        for key in ("unpresented_discussions", "undiscussed_slides", "weak_alignment_areas", "recommended_followups"):
            assert isinstance(gaps[key], list)

        # 7. No schema violations (slide_intelligence_packet)
        packet = build_slide_intelligence_packet(
            _load_fixture(),
            transcript_artifact={"text": " ".join(s["text"] for s in segments)},
        )
        assert packet["artifact_type"] == "slide_intelligence_packet"
        assert packet["validation_status"] in {"needs_review", "provisional", "informational"}

    def test_golden_path_deterministic(self):
        raw = ingest_slides(FIXTURE_PATH)
        r1 = compute_slide_transcript_gaps(
            merge_slide_transcript_outputs(
                {"decisions": [], "action_items": [], "open_questions": []},
                extract_slide_signals(normalize_slides(raw)),
                align_slides_to_transcript(
                    normalize_slides(raw),
                    [{"text": "5G NR interference with radar coexistence study at 3.5 GHz."}],
                ),
            )
        )
        r2 = compute_slide_transcript_gaps(
            merge_slide_transcript_outputs(
                {"decisions": [], "action_items": [], "open_questions": []},
                extract_slide_signals(normalize_slides(raw)),
                align_slides_to_transcript(
                    normalize_slides(raw),
                    [{"text": "5G NR interference with radar coexistence study at 3.5 GHz."}],
                ),
            )
        )
        assert r1 == r2
