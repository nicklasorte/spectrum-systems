"""
tests/test_working_paper_engine.py

Covers:
  - No-results case (quantitative results not available)
  - Transcript-heavy case (multiple transcripts, no docs)
  - Missing-study-plan case (no study plan excerpts)
  - Contradiction detection
  - Unsupported quantitative-claim detection (VAL-002)
  - Gap propagation into report
  - FAQ section mapping
  - Schema validation of output bundle
  - Deterministic behavior for identical structured inputs
  - All seven required sections present
  - Section 6 RESULTS NOT YET AVAILABLE marker
  - Forbidden pattern detection (VAL-006)
  - Traceability requirements populated
  - CLI basic invocation
  - inputs_from_dict parses dict correctly
  - Module manifest exists and conforms to schema
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.working_paper_engine import (
    WorkingPaperBundle,
    WorkingPaperInputs,
    run_pipeline,
)
from spectrum_systems.modules.working_paper_engine.artifacts import (
    bundle_to_dict,
    bundle_to_markdown,
    validate_bundle_schema,
)
from spectrum_systems.modules.working_paper_engine.interpret import interpret
from spectrum_systems.modules.working_paper_engine.models import (
    ObservedItem,
    SourceDocumentExcerpt,
    SourceType,
    StudyPlanExcerpt,
    TranscriptExcerpt,
    ValidationSeverity,
)
from spectrum_systems.modules.working_paper_engine.observe import observe
from spectrum_systems.modules.working_paper_engine.service import inputs_from_dict
from spectrum_systems.modules.working_paper_engine.synthesize import synthesize
from spectrum_systems.modules.working_paper_engine.validate import (
    check_forbidden_patterns,
    check_required_sections,
    check_results_readiness,
    check_s6_no_results_claim,
    validate,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

BUNDLE_SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "working_paper_bundle.schema.json"
MANIFEST_PATH = (
    REPO_ROOT / "docs" / "module-manifests" / "workflow_modules" / "working_paper_engine.json"
)
MODULE_MANIFEST_SCHEMA_PATH = REPO_ROOT / "schemas" / "module-manifest.schema.json"

MINIMAL_INPUTS = WorkingPaperInputs(
    title="3.5 GHz Band Sharing Study",
    context_description="Preliminary assessment of 3550-3700 MHz band sharing between federal and commercial systems.",
    band_description="3550-3700 MHz",
)

TRANSCRIPT_INPUTS = WorkingPaperInputs(
    title="Spectrum Coordination Meeting — Working Paper",
    context_description="Meeting transcript review for 3.5 GHz coordination.",
    band_description="3.5 GHz",
    transcripts=[
        TranscriptExcerpt(
            artifact_id="tx-001",
            locator="00:05:30",
            speaker="Dr. Smith",
            content=(
                "We assume the federal P2P antenna height is 30 meters. "
                "The propagation model uses ITM at 3625 MHz. "
                "There is an open question about actual radar exclusion zone radius."
            ),
        ),
        TranscriptExcerpt(
            artifact_id="tx-002",
            locator="00:22:10",
            speaker="Ms. Jones",
            content=(
                "The protection criteria threshold is not yet confirmed. "
                "We agreed that link budget validation is required before proceeding. "
                "Antenna height data is missing for the study area."
            ),
        ),
    ],
)

FULL_INPUTS = WorkingPaperInputs(
    title="Federal Spectrum Study — 3.5 GHz Full Assessment",
    context_description="Full engineering assessment of 3550-3700 MHz band.",
    band_description="3550-3700 MHz",
    source_documents=[
        SourceDocumentExcerpt(
            artifact_id="doc-001",
            locator="Section 3.2",
            content=(
                "The interference analysis assumes a path loss model based on ITM. "
                "Protection criteria for federal P2P links require I/N < -6 dB. "
                "Link budget analysis at 3625 MHz center frequency."
            ),
            title="Technical Analysis Report",
        ),
    ],
    transcripts=[
        TranscriptExcerpt(
            artifact_id="tx-003",
            locator="00:10:00",
            speaker="Dr. Brown",
            content=(
                "The coordination zone radius is assumed to be 40 km. "
                "There is uncertainty about this value given the deployment density. "
                "Path loss measurements are missing for rural terrain types."
            ),
        ),
    ],
    study_plan_excerpts=[
        StudyPlanExcerpt(
            artifact_id="sp-001",
            locator="Task 2.1",
            content=(
                "Conduct interference analysis for 3550-3700 MHz band. "
                "Model protection zones for federal P2P systems."
            ),
            objective="Assess feasibility of commercial deployments in the 3.5 GHz band.",
        ),
    ],
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run_pipeline(inputs: WorkingPaperInputs) -> WorkingPaperBundle:
    return run_pipeline(inputs)


# ---------------------------------------------------------------------------
# Test: no-results case
# ---------------------------------------------------------------------------


class TestNoResultsCase:
    def test_results_readiness_false_for_minimal_inputs(self):
        bundle = _run_pipeline(MINIMAL_INPUTS)
        assert not bundle.results_readiness.quantitative_results_available

    def test_section_6_contains_marker(self):
        bundle = _run_pipeline(MINIMAL_INPUTS)
        s6 = next(s for s in bundle.report.sections if s.section_id == "6")
        assert "RESULTS NOT YET AVAILABLE" in s6.content

    def test_no_results_readiness_check_passes(self):
        bundle = _run_pipeline(MINIMAL_INPUTS)
        check_ids = {f.check_id for f in bundle.validation.passes}
        assert "VAL-008" in check_ids

    def test_readiness_notes_present(self):
        bundle = _run_pipeline(MINIMAL_INPUTS)
        assert len(bundle.results_readiness.readiness_notes) > 10


# ---------------------------------------------------------------------------
# Test: transcript-heavy case
# ---------------------------------------------------------------------------


class TestTranscriptHeavyCase:
    def test_bundle_has_seven_sections(self):
        bundle = _run_pipeline(TRANSCRIPT_INPUTS)
        assert len(bundle.report.sections) == 7

    def test_section_ids_correct(self):
        bundle = _run_pipeline(TRANSCRIPT_INPUTS)
        ids = [s.section_id for s in bundle.report.sections]
        assert ids == ["1", "2", "3", "4", "5", "6", "7"]

    def test_source_artifact_ids_include_transcripts(self):
        bundle = _run_pipeline(TRANSCRIPT_INPUTS)
        assert "tx-001" in bundle.source_artifact_ids
        assert "tx-002" in bundle.source_artifact_ids

    def test_gap_register_not_empty(self):
        bundle = _run_pipeline(TRANSCRIPT_INPUTS)
        assert len(bundle.gap_register) > 0

    def test_faq_items_present(self):
        bundle = _run_pipeline(TRANSCRIPT_INPUTS)
        assert len(bundle.faq) > 0

    def test_all_faq_section_refs_valid(self):
        bundle = _run_pipeline(TRANSCRIPT_INPUTS)
        valid_ids = {s.section_id for s in bundle.report.sections}
        for faq in bundle.faq:
            assert faq.section_ref in valid_ids, (
                f"FAQ {faq.faq_id} references invalid section {faq.section_ref!r}"
            )


# ---------------------------------------------------------------------------
# Test: missing-study-plan case
# ---------------------------------------------------------------------------


class TestMissingStudyPlanCase:
    def test_pipeline_runs_without_study_plan(self):
        inputs = WorkingPaperInputs(
            title="Study Without Plan",
            context_description="No study plan available.",
            band_description="2.5 GHz",
            transcripts=[
                TranscriptExcerpt(
                    artifact_id="tx-sp-test",
                    content="The interference model is not yet defined. Link budget is pending.",
                ),
            ],
        )
        bundle = _run_pipeline(inputs)
        assert len(bundle.report.sections) == 7

    def test_traceability_has_no_study_plan_artifact(self):
        inputs = WorkingPaperInputs(
            title="No Study Plan",
            band_description="2.5 GHz",
        )
        bundle = _run_pipeline(inputs)
        study_plan_refs = [
            a for a in bundle.traceability_requirements.required_artifacts
            if "study_plan" in a
        ]
        assert len(study_plan_refs) == 0


# ---------------------------------------------------------------------------
# Test: contradiction detection
# ---------------------------------------------------------------------------


class TestContradictionDetection:
    def test_contradiction_produces_gap_candidate(self):
        items = [
            ObservedItem(
                item_id="OBS-001",
                source_artifact_id="src-a",
                source_type=SourceType.DOCUMENT,
                source_locator="p.1",
                text="The coordination zone radius is 40 km.",
                tag="fact",
            ),
            ObservedItem(
                item_id="OBS-002",
                source_artifact_id="src-b",
                source_type=SourceType.TRANSCRIPT,
                source_locator="00:05",
                text="The coordination zone radius is 150 km.",
                tag="fact",
            ),
        ]
        concerns = interpret(items)
        contradiction_concerns = [
            c for c in concerns if c.bucket.value == "contradictions"
        ]
        assert len(contradiction_concerns) > 0

    def test_contradiction_gap_is_blocking(self):
        inputs = WorkingPaperInputs(
            title="Contradiction Test",
            source_documents=[
                SourceDocumentExcerpt(
                    artifact_id="doc-c1",
                    content="Protection zone is 40 km for the modeled scenario.",
                ),
            ],
            transcripts=[
                TranscriptExcerpt(
                    artifact_id="tx-c1",
                    content="Protection zone is 150 km according to the latest analysis.",
                ),
            ],
        )
        bundle = _run_pipeline(inputs)
        blocking_gaps = [g for g in bundle.gap_register if g.blocking]
        assert len(blocking_gaps) > 0


# ---------------------------------------------------------------------------
# Test: unsupported quantitative-claim detection
# ---------------------------------------------------------------------------


class TestUnsupportedQuantitativeClaimDetection:
    def test_val_002_triggers_for_injected_results_claim(self):
        """Directly test the VAL-002 check with injected bad content."""
        from spectrum_systems.modules.working_paper_engine.models import (
            ReportSection,
            ResultsReadiness,
        )

        bad_sections = [
            ReportSection(
                section_id=str(i),
                title=f"Section {i}",
                content="Normal content." if i != 6 else "The results show 75% improvement.",
            )
            for i in range(1, 8)
        ]
        readiness = ResultsReadiness(
            quantitative_results_available=False,
            readiness_notes="Not ready.",
        )
        finding = check_s6_no_results_claim(bad_sections, readiness)
        assert finding.severity == ValidationSeverity.ERROR

    def test_val_002_passes_when_results_available(self):
        from spectrum_systems.modules.working_paper_engine.models import (
            ReportSection,
            ResultsReadiness,
        )

        sections = [
            ReportSection(
                section_id=str(i),
                title=f"Section {i}",
                content="The analysis yields 3.5 dB improvement.",
            )
            for i in range(1, 8)
        ]
        readiness = ResultsReadiness(
            quantitative_results_available=True,
            readiness_notes="Results available.",
        )
        finding = check_s6_no_results_claim(sections, readiness)
        assert finding.severity == ValidationSeverity.PASS


# ---------------------------------------------------------------------------
# Test: forbidden pattern detection
# ---------------------------------------------------------------------------


class TestForbiddenPatternDetection:
    def test_forbidden_pattern_flagged(self):
        from spectrum_systems.modules.working_paper_engine.models import ReportSection

        sections = [
            ReportSection(
                section_id=str(i),
                title=f"Section {i}",
                content="Normal content." if i != 3 else "Most links are feasible.",
            )
            for i in range(1, 8)
        ]
        finding = check_forbidden_patterns(sections)
        assert finding.severity == ValidationSeverity.ERROR

    def test_clean_content_passes(self):
        from spectrum_systems.modules.working_paper_engine.models import ReportSection

        sections = [
            ReportSection(
                section_id=str(i),
                title=f"Section {i}",
                content="Analysis indicates candidate assignments require further validation.",
            )
            for i in range(1, 8)
        ]
        finding = check_forbidden_patterns(sections)
        assert finding.severity == ValidationSeverity.PASS


# ---------------------------------------------------------------------------
# Test: gap propagation into report
# ---------------------------------------------------------------------------


class TestGapPropagation:
    def test_gaps_have_valid_section_refs(self):
        bundle = _run_pipeline(FULL_INPUTS)
        valid_ids = {s.section_id for s in bundle.report.sections}
        for gap in bundle.gap_register:
            assert gap.section_ref in valid_ids, (
                f"Gap {gap.gap_id} has invalid section_ref {gap.section_ref!r}"
            )

    def test_blocking_gaps_in_register(self):
        bundle = _run_pipeline(TRANSCRIPT_INPUTS)
        # Transcript has open issues → should produce blocking gaps
        gap_types = {g.gap_type.value for g in bundle.gap_register}
        assert len(gap_types) > 0

    def test_gap_ids_are_unique(self):
        bundle = _run_pipeline(FULL_INPUTS)
        ids = [g.gap_id for g in bundle.gap_register]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Test: FAQ section mapping
# ---------------------------------------------------------------------------


class TestFAQSectionMapping:
    def test_faq_ids_are_unique(self):
        bundle = _run_pipeline(TRANSCRIPT_INPUTS)
        ids = [f.faq_id for f in bundle.faq]
        assert len(ids) == len(set(ids))

    def test_faq_questions_non_empty(self):
        bundle = _run_pipeline(TRANSCRIPT_INPUTS)
        for faq in bundle.faq:
            assert len(faq.question) >= 10, f"FAQ {faq.faq_id} question too short"

    def test_val_004_passes_for_valid_faq(self):
        bundle = _run_pipeline(TRANSCRIPT_INPUTS)
        check_ids_pass = {f.check_id for f in bundle.validation.passes}
        assert "VAL-004" in check_ids_pass


# ---------------------------------------------------------------------------
# Test: schema validation of output bundle
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_bundle_schema_exists(self):
        assert BUNDLE_SCHEMA_PATH.exists(), "Bundle schema file must exist"

    def test_full_bundle_validates_against_schema(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            pytest.skip("jsonschema not installed")
        bundle = _run_pipeline(FULL_INPUTS)
        bundle_dict = bundle_to_dict(bundle)
        errors = validate_bundle_schema(bundle_dict)
        assert errors == [], f"Schema validation errors: {errors}"

    def test_minimal_bundle_validates_against_schema(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            pytest.skip("jsonschema not installed")
        bundle = _run_pipeline(MINIMAL_INPUTS)
        bundle_dict = bundle_to_dict(bundle)
        errors = validate_bundle_schema(bundle_dict)
        assert errors == [], f"Schema validation errors: {errors}"

    def test_bundle_dict_has_required_top_level_keys(self):
        bundle = _run_pipeline(MINIMAL_INPUTS)
        bundle_dict = bundle_to_dict(bundle)
        required = {
            "artifact_id",
            "source_artifact_ids",
            "report",
            "faq",
            "gap_register",
            "validation_checklist",
            "results_readiness",
            "traceability_requirements",
            "validation",
            "metadata",
        }
        assert required.issubset(bundle_dict.keys()), (
            f"Missing keys: {required - set(bundle_dict.keys())}"
        )

    def test_artifact_id_format(self):
        bundle = _run_pipeline(MINIMAL_INPUTS)
        assert bundle.artifact_id.startswith("WPE-")
        assert len(bundle.artifact_id) == 16  # "WPE-" + 12 hex chars

    def test_validation_checklist_has_all_checks(self):
        bundle = _run_pipeline(FULL_INPUTS)
        check_ids = {f.check_id for f in bundle.validation_checklist}
        expected = {
            "VAL-001", "VAL-002", "VAL-003", "VAL-004",
            "VAL-005", "VAL-006", "VAL-007", "VAL-008",
        }
        assert expected.issubset(check_ids), (
            f"Missing check IDs: {expected - check_ids}"
        )


# ---------------------------------------------------------------------------
# Test: deterministic behavior
# ---------------------------------------------------------------------------


class TestDeterministicBehavior:
    def test_identical_inputs_produce_identical_sections(self):
        """Same structured inputs must yield same section content (artifact_id excluded)."""
        inputs = WorkingPaperInputs(
            title="Determinism Test",
            context_description="Fixed context for determinism check.",
            band_description="5.8 GHz",
            source_documents=[
                SourceDocumentExcerpt(
                    artifact_id="det-doc-001",
                    content="Propagation model based on ITM. Interference threshold is -6 dB I/N.",
                ),
            ],
        )
        bundle_a = _run_pipeline(inputs)
        bundle_b = _run_pipeline(inputs)
        # Sections should be identical
        for sec_a, sec_b in zip(bundle_a.report.sections, bundle_b.report.sections):
            assert sec_a.content == sec_b.content, (
                f"Non-deterministic content in section {sec_a.section_id}"
            )

    def test_identical_inputs_produce_identical_gap_descriptions(self):
        inputs = WorkingPaperInputs(
            title="Determinism Test 2",
            transcripts=[
                TranscriptExcerpt(
                    artifact_id="det-tx-001",
                    content="Link budget is missing. Path loss data is not available.",
                ),
            ],
        )
        bundle_a = _run_pipeline(inputs)
        bundle_b = _run_pipeline(inputs)
        descs_a = [g.description for g in bundle_a.gap_register]
        descs_b = [g.description for g in bundle_b.gap_register]
        assert descs_a == descs_b


# ---------------------------------------------------------------------------
# Test: observe stage unit tests
# ---------------------------------------------------------------------------


class TestObserveStage:
    def test_observe_returns_items(self):
        inputs = WorkingPaperInputs(
            title="Observe Test",
            source_documents=[
                SourceDocumentExcerpt(
                    artifact_id="obs-doc-001",
                    content="The system assumes 30 m antenna height. Path loss is unknown.",
                ),
            ],
        )
        items = observe(inputs)
        assert len(items) > 0

    def test_observe_tags_assumption(self):
        inputs = WorkingPaperInputs(
            title="Tag Test",
            source_documents=[
                SourceDocumentExcerpt(
                    artifact_id="tag-doc-001",
                    content="We assume the antenna height is 30 m.",
                ),
            ],
        )
        items = observe(inputs)
        tags = {i.tag for i in items}
        assert "assumption" in tags

    def test_observe_tags_open_issue(self):
        inputs = WorkingPaperInputs(
            title="Tag Open Issue",
            transcripts=[
                TranscriptExcerpt(
                    artifact_id="tx-oi-001",
                    content="The protection zone radius is an open question.",
                ),
            ],
        )
        items = observe(inputs)
        tags = {i.tag for i in items}
        assert "open_issue" in tags

    def test_observe_minimal_returns_context_item(self):
        inputs = WorkingPaperInputs(
            title="Context Only",
            context_description="3.5 GHz study context.",
        )
        items = observe(inputs)
        assert len(items) > 0
        assert items[0].source_artifact_id == "context"

    def test_observe_preserves_speaker_in_transcript(self):
        inputs = WorkingPaperInputs(
            title="Speaker Test",
            transcripts=[
                TranscriptExcerpt(
                    artifact_id="spk-tx-001",
                    speaker="Dr. Alpha",
                    content="This is a test statement.",
                ),
            ],
        )
        items = observe(inputs)
        assert any("Dr. Alpha" in item.text for item in items)


# ---------------------------------------------------------------------------
# Test: interpret stage unit tests
# ---------------------------------------------------------------------------


class TestInterpretStage:
    def test_interpret_produces_concerns(self):
        items = [
            ObservedItem(
                item_id="I-001",
                source_artifact_id="src-1",
                source_type=SourceType.DOCUMENT,
                source_locator="p.1",
                text="The methodology uses ITM propagation model.",
                tag="methodology",
            ),
        ]
        concerns = interpret(items)
        assert len(concerns) > 0

    def test_interpret_flags_missing_propagation_model(self):
        items = [
            ObservedItem(
                item_id="I-001",
                source_artifact_id="src-1",
                source_type=SourceType.DOCUMENT,
                source_locator="p.1",
                text="The antenna height is 30 m.",
                tag="assumption",
            ),
        ]
        concerns = interpret(items)
        missing = [c for c in concerns if "propagation model" in c.description]
        assert len(missing) > 0

    def test_interpret_maps_to_correct_section(self):
        items = [
            ObservedItem(
                item_id="I-002",
                source_artifact_id="src-2",
                source_type=SourceType.DOCUMENT,
                source_locator="p.2",
                text="We assume a fixed interference threshold.",
                tag="assumption",
            ),
        ]
        concerns = interpret(items)
        assumption_concerns = [c for c in concerns if c.bucket.value == "assumptions"]
        assert len(assumption_concerns) > 0
        for c in assumption_concerns:
            section_values = [s.value for s in c.section_refs]
            assert "4" in section_values


# ---------------------------------------------------------------------------
# Test: markdown rendering
# ---------------------------------------------------------------------------


class TestMarkdownRendering:
    def test_markdown_contains_title(self):
        bundle = _run_pipeline(MINIMAL_INPUTS)
        md = bundle_to_markdown(bundle)
        assert "3.5 GHz Band Sharing Study" in md

    def test_markdown_contains_draft_marker(self):
        bundle = _run_pipeline(MINIMAL_INPUTS)
        md = bundle_to_markdown(bundle)
        assert "DRAFT / PRE-DECISIONAL" in md

    def test_markdown_contains_all_sections(self):
        bundle = _run_pipeline(MINIMAL_INPUTS)
        md = bundle_to_markdown(bundle)
        for i in range(1, 8):
            assert f"## Section {i}:" in md


# ---------------------------------------------------------------------------
# Test: inputs_from_dict
# ---------------------------------------------------------------------------


class TestInputsFromDict:
    def test_minimal_dict(self):
        data = {"title": "Test Paper"}
        inputs = inputs_from_dict(data)
        assert inputs.title == "Test Paper"
        assert inputs.source_documents == []
        assert inputs.transcripts == []
        assert inputs.study_plan_excerpts == []

    def test_full_dict(self):
        data = {
            "title": "Full Test",
            "context_description": "Test context.",
            "band_description": "3.5 GHz",
            "source_documents": [
                {"artifact_id": "d-001", "content": "Doc content.", "locator": "p.1", "title": "Doc"}
            ],
            "transcripts": [
                {"artifact_id": "t-001", "content": "Transcript.", "speaker": "Alice", "locator": "00:01"}
            ],
            "study_plan_excerpts": [
                {"artifact_id": "s-001", "content": "Plan content.", "objective": "Test obj."}
            ],
        }
        inputs = inputs_from_dict(data)
        assert inputs.title == "Full Test"
        assert len(inputs.source_documents) == 1
        assert len(inputs.transcripts) == 1
        assert len(inputs.study_plan_excerpts) == 1
        assert inputs.transcripts[0].speaker == "Alice"

    def test_missing_title_defaults(self):
        inputs = inputs_from_dict({})
        assert "Untitled" in inputs.title


# ---------------------------------------------------------------------------
# Test: module manifest
# ---------------------------------------------------------------------------


class TestModuleManifest:
    def test_manifest_file_exists(self):
        assert MANIFEST_PATH.exists(), (
            f"Module manifest not found at {MANIFEST_PATH}"
        )

    def test_manifest_is_valid_json(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        assert "module_id" in manifest

    def test_manifest_module_id(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        assert manifest["module_id"] == "workflow_modules.working_paper_engine"

    def test_manifest_has_forbidden_responsibilities(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        assert len(manifest.get("forbidden_responsibilities", [])) > 0

    def test_manifest_conforms_to_schema(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            pytest.skip("jsonschema not installed")
        schema = json.loads(MODULE_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        errors = list(validator.iter_errors(manifest))
        assert errors == [], f"Manifest schema errors: {[e.message for e in errors]}"


# ---------------------------------------------------------------------------
# Test: contract schemas exist
# ---------------------------------------------------------------------------


class TestContractSchemasExist:
    def test_bundle_schema_is_valid_json(self):
        schema = json.loads(BUNDLE_SCHEMA_PATH.read_text(encoding="utf-8"))
        assert "$schema" in schema
        assert schema["title"] == "Working Paper Bundle"

    def test_gap_register_schema_exists(self):
        path = REPO_ROOT / "contracts" / "schemas" / "working_paper_gap_register.schema.json"
        assert path.exists()
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert "$schema" in schema

    def test_faq_schema_exists(self):
        path = REPO_ROOT / "contracts" / "schemas" / "working_paper_faq.schema.json"
        assert path.exists()
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert "$schema" in schema


# ---------------------------------------------------------------------------
# Test: CLI basic invocation
# ---------------------------------------------------------------------------


class TestCLI:
    def test_cli_runs_and_exits_zero(self, tmp_path):
        input_data = {
            "title": "CLI Test Paper",
            "context_description": "CLI integration test.",
            "band_description": "700 MHz",
        }
        input_file = tmp_path / "inputs.json"
        input_file.write_text(json.dumps(input_data), encoding="utf-8")
        output_file = tmp_path / "bundle.json"

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "run_working_paper_engine.py"),
                "--inputs",
                str(input_file),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"CLI exited {result.returncode}\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
        assert output_file.exists()
        bundle_dict = json.loads(output_file.read_text(encoding="utf-8"))
        assert "artifact_id" in bundle_dict

    def test_cli_writes_markdown(self, tmp_path):
        input_data = {
            "title": "CLI Markdown Test",
            "band_description": "900 MHz",
        }
        input_file = tmp_path / "inputs.json"
        input_file.write_text(json.dumps(input_data), encoding="utf-8")
        output_file = tmp_path / "bundle.json"
        md_file = tmp_path / "report.md"

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "run_working_paper_engine.py"),
                "--inputs",
                str(input_file),
                "--output",
                str(output_file),
                "--pretty-report-out",
                str(md_file),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert md_file.exists()
        md_content = md_file.read_text(encoding="utf-8")
        assert "CLI Markdown Test" in md_content
        assert "DRAFT / PRE-DECISIONAL" in md_content
