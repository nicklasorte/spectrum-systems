"""
Tests for the working_paper_engine module.

Covers:
  - Module file existence
  - No-results case (Section 6 in results-framework mode)
  - Transcript-heavy case
  - Missing-study-plan case
  - Contradiction detection in VALIDATE stage
  - Unsupported quantitative claim detection
  - Gap propagation into report sections
  - FAQ section mapping
  - Schema validation of output bundle
  - Deterministic behavior for identical structured inputs
  - CLI: help flag, valid inputs, missing required args
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = REPO_ROOT / "spectrum_systems" / "modules" / "working_paper_engine"
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_working_paper_engine.py"
SCHEMA_DIR = REPO_ROOT / "contracts" / "schemas"

sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.working_paper_engine.models import (  # noqa: E402
    EngineInputs,
    ProvenanceMode,
    SourceDocumentExcerpt,
    StudyPlanExcerpt,
    TranscriptExcerpt,
)
from spectrum_systems.modules.working_paper_engine.observe import run_observe  # noqa: E402
from spectrum_systems.modules.working_paper_engine.interpret import (  # noqa: E402
    run_interpret,
    extract_gap_items,
)
from spectrum_systems.modules.working_paper_engine.synthesize import run_synthesize  # noqa: E402
from spectrum_systems.modules.working_paper_engine.validate import run_validate  # noqa: E402
from spectrum_systems.modules.working_paper_engine.artifacts import (  # noqa: E402
    assemble_bundle,
    validate_bundle_schema,
    render_markdown,
)
from spectrum_systems.modules.working_paper_engine.service import run_pipeline  # noqa: E402


# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------

MINIMAL_SOURCE_DOC = SourceDocumentExcerpt(
    content=(
        "The study analyzes interference between federal radar systems and commercial "
        "5G networks in the 3.1–3.45 GHz band. "
        "Protection criteria are specified in NTIA Report 21-550. "
        "Propagation modeling uses the ITM model."
    ),
    artifact_id="DOC-001",
    source_locator="p.1",
    title="Radar-5G Coexistence Study",
)

MINIMAL_TRANSCRIPT = TranscriptExcerpt(
    content=(
        "Alice: What are the interference thresholds for coastal radar sites? "
        "Bob: We need the measurement data from the coastal deployment. "
        "Alice: Agreed — the missing coastal data is a gap that must be resolved. "
        "Carol: Are the protection criteria consistent with adjacent band allocations?"
    ),
    artifact_id="TRANS-001",
    source_locator="turn 1-4",
    speaker="Multiple",
    meeting_title="Radar-5G Coordination Meeting",
)

MINIMAL_STUDY_PLAN = StudyPlanExcerpt(
    content=(
        "The study shall evaluate feasibility of commercial use in the 3.1–3.45 GHz band. "
        "Assumptions include uniform deployment density. "
        "The study must produce interference margin results for all candidate assignments."
    ),
    artifact_id="PLAN-001",
    source_locator="Section 2",
    study_title="NTIA Radar-5G Feasibility Study",
)


def _minimal_inputs() -> EngineInputs:
    return EngineInputs(
        source_documents=[MINIMAL_SOURCE_DOC],
        transcripts=[MINIMAL_TRANSCRIPT],
        study_plans=[MINIMAL_STUDY_PLAN],
        title_hint="Radar-5G Coexistence Working Paper",
        study_id="STUDY-001",
    )


def _no_results_inputs() -> EngineInputs:
    """Inputs without quantitative results."""
    return _minimal_inputs()


def _transcript_heavy_inputs() -> EngineInputs:
    """Inputs with only transcripts (no source docs, no study plan)."""
    return EngineInputs(
        transcripts=[MINIMAL_TRANSCRIPT],
        title_hint="Transcript-Only Working Paper",
        study_id="STUDY-002",
    )


def _missing_study_plan_inputs() -> EngineInputs:
    """Inputs without a study plan."""
    return EngineInputs(
        source_documents=[MINIMAL_SOURCE_DOC],
        transcripts=[MINIMAL_TRANSCRIPT],
        title_hint="No Study Plan Working Paper",
        study_id="STUDY-003",
    )


# ---------------------------------------------------------------------------
# Module file existence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename",
    [
        "__init__.py",
        "models.py",
        "observe.py",
        "interpret.py",
        "synthesize.py",
        "validate.py",
        "artifacts.py",
        "service.py",
    ],
)
def test_module_files_exist(filename: str) -> None:
    assert (MODULE_DIR / filename).is_file(), f"Module file missing: {filename}"


def test_cli_script_exists() -> None:
    assert SCRIPT_PATH.is_file(), "scripts/run_working_paper_engine.py is missing"


@pytest.mark.parametrize(
    "schema_file",
    [
        "working_paper_bundle.schema.json",
        "working_paper_gap_register.schema.json",
        "working_paper_faq.schema.json",
    ],
)
def test_schema_files_exist(schema_file: str) -> None:
    assert (SCHEMA_DIR / schema_file).is_file(), f"Schema file missing: {schema_file}"


# ---------------------------------------------------------------------------
# OBSERVE stage
# ---------------------------------------------------------------------------


def test_observe_returns_items() -> None:
    inputs = _minimal_inputs()
    result = run_observe(inputs)
    assert len(result.items) > 0


def test_observe_assigns_item_ids() -> None:
    inputs = _minimal_inputs()
    result = run_observe(inputs)
    ids = [item.item_id for item in result.items]
    assert len(ids) == len(set(ids)), "Item IDs must be unique"


def test_observe_preserves_source_type() -> None:
    inputs = _minimal_inputs()
    result = run_observe(inputs)
    source_types = {item.source_type for item in result.items}
    assert "source_document" in source_types
    assert "transcript" in source_types
    assert "study_plan" in source_types


def test_observe_detects_questions() -> None:
    inputs = EngineInputs(
        transcripts=[TranscriptExcerpt(content="What are the interference thresholds?")]
    )
    result = run_observe(inputs)
    question_items = [i for i in result.items if "question" in i.tags]
    assert question_items, "Expected question-tagged items"


def test_observe_detects_constraints() -> None:
    inputs = EngineInputs(
        source_documents=[SourceDocumentExcerpt(content="Interference must not exceed the protection threshold.")]
    )
    result = run_observe(inputs)
    constraint_items = [i for i in result.items if "constraint" in i.tags]
    assert constraint_items, "Expected constraint-tagged items"


def test_observe_empty_inputs() -> None:
    inputs = EngineInputs()
    result = run_observe(inputs)
    assert result.items == []


# ---------------------------------------------------------------------------
# INTERPRET stage
# ---------------------------------------------------------------------------


def test_interpret_returns_concerns() -> None:
    inputs = _minimal_inputs()
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    assert len(interpret_result.concerns) > 0


def test_interpret_concern_ids_unique() -> None:
    inputs = _minimal_inputs()
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    ids = [c.concern_id for c in interpret_result.concerns]
    assert len(ids) == len(set(ids))


def test_interpret_flags_gap_candidates() -> None:
    inputs = EngineInputs(
        transcripts=[TranscriptExcerpt(content="The coastal data is missing and must be resolved.")]
    )
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    gap_candidates = [c for c in interpret_result.concerns if c.is_gap_candidate]
    assert gap_candidates, "Expected at least one gap candidate from missing-data content"


def test_extract_gap_items_produces_gaps() -> None:
    inputs = _minimal_inputs()
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    gaps = extract_gap_items(interpret_result)
    # Minimal inputs have questions and missing data — should produce gaps
    assert len(gaps) > 0


def test_gap_ids_are_unique() -> None:
    inputs = _minimal_inputs()
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    gaps = extract_gap_items(interpret_result)
    gap_ids = [g.gap_id for g in gaps]
    assert len(gap_ids) == len(set(gap_ids))


def test_gap_ids_follow_pattern() -> None:
    inputs = _minimal_inputs()
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    gaps = extract_gap_items(interpret_result)
    for g in gaps:
        assert g.gap_id.startswith("GAP-"), f"Gap ID should start with GAP-: {g.gap_id}"


# ---------------------------------------------------------------------------
# SYNTHESIZE stage
# ---------------------------------------------------------------------------


def test_synthesize_produces_seven_sections() -> None:
    inputs = _no_results_inputs()
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    gaps = extract_gap_items(interpret_result)
    synth_result = run_synthesize(inputs, interpret_result, gaps, quantitative_results_available=False)
    assert len(synth_result.sections) == 7


def test_synthesize_section_ids_are_1_through_7() -> None:
    inputs = _minimal_inputs()
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    gaps = extract_gap_items(interpret_result)
    synth_result = run_synthesize(inputs, interpret_result, gaps)
    section_ids = [s.section_id for s in synth_result.sections]
    assert section_ids == ["1", "2", "3", "4", "5", "6", "7"]


def test_synthesize_no_results_section6_contains_notice() -> None:
    """Section 6 must switch to results-framework mode when results are unavailable."""
    inputs = _no_results_inputs()
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    gaps = extract_gap_items(interpret_result)
    synth_result = run_synthesize(inputs, interpret_result, gaps, quantitative_results_available=False)
    sec6 = next(s for s in synth_result.sections if s.section_id == "6")
    assert "NOTICE" in sec6.content, "Section 6 must contain NOTICE when results are not available"
    assert "not available" in sec6.content


def test_synthesize_no_results_section6_no_fabricated_results() -> None:
    """Section 6 must not claim results exist when none do."""
    inputs = _no_results_inputs()
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    gaps = extract_gap_items(interpret_result)
    synth_result = run_synthesize(inputs, interpret_result, gaps, quantitative_results_available=False)
    sec6 = next(s for s in synth_result.sections if s.section_id == "6")
    # Must not contain language implying results exist
    assert "results indicate" not in sec6.content.lower()
    assert "analysis shows" not in sec6.content.lower()


def test_synthesize_transcript_heavy_case() -> None:
    """Engine should work even with only transcript inputs."""
    inputs = _transcript_heavy_inputs()
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    gaps = extract_gap_items(interpret_result)
    synth_result = run_synthesize(inputs, interpret_result, gaps)
    assert len(synth_result.sections) == 7


def test_synthesize_missing_study_plan_case() -> None:
    """Engine should work without a study plan."""
    inputs = _missing_study_plan_inputs()
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    gaps = extract_gap_items(interpret_result)
    synth_result = run_synthesize(inputs, interpret_result, gaps)
    assert len(synth_result.sections) == 7


def test_synthesize_faq_section_refs_are_valid() -> None:
    """All FAQ items must reference a section ID that exists in the report."""
    inputs = _minimal_inputs()
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    gaps = extract_gap_items(interpret_result)
    synth_result = run_synthesize(inputs, interpret_result, gaps)
    section_ids = {s.section_id for s in synth_result.sections}
    for faq in synth_result.faq_items:
        assert faq.section_ref in section_ids, (
            f"FAQ {faq.faq_id} references non-existent section {faq.section_ref}"
        )


def test_synthesize_gap_register_section_refs_valid() -> None:
    """All gap items must reference a section ID that exists in the report."""
    inputs = _minimal_inputs()
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    gaps = extract_gap_items(interpret_result)
    synth_result = run_synthesize(inputs, interpret_result, gaps)
    section_ids = {s.section_id for s in synth_result.sections}
    for gap in synth_result.gap_items:
        assert gap.section_ref in section_ids, (
            f"Gap {gap.gap_id} references non-existent section {gap.section_ref}"
        )


def test_synthesize_gaps_propagated_into_sections() -> None:
    """Gap markers should appear in section content when gaps exist."""
    inputs = EngineInputs(
        transcripts=[TranscriptExcerpt(
            content=(
                "The coastal site data is missing and not available. "
                "We do not have the interference measurement results. "
                "What are the protection criteria?"
            ),
            artifact_id="T-GAP",
        )],
    )
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    gaps = extract_gap_items(interpret_result)
    assert len(gaps) > 0, "Expected gaps from missing-data transcript"
    synth_result = run_synthesize(inputs, interpret_result, gaps)
    all_content = " ".join(s.content for s in synth_result.sections)
    assert "GAP-" in all_content or "[need additional information]" in all_content


def test_synthesize_title_uses_hint() -> None:
    inputs = EngineInputs(title_hint="My Custom Working Paper")
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    gaps = extract_gap_items(interpret_result)
    synth_result = run_synthesize(inputs, interpret_result, gaps)
    assert synth_result.title == "My Custom Working Paper"


# ---------------------------------------------------------------------------
# VALIDATE stage
# ---------------------------------------------------------------------------


def test_validate_all_sections_present_passes() -> None:
    inputs = _minimal_inputs()
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    gaps = extract_gap_items(interpret_result)
    synth_result = run_synthesize(inputs, interpret_result, gaps)
    validate_result = run_validate(synth_result)
    assert not validate_result.has_errors, f"Unexpected errors: {validate_result.errors}"


def test_validate_no_results_mode_passes() -> None:
    """Validation should pass in no-results mode."""
    inputs = _no_results_inputs()
    observe_result = run_observe(inputs)
    interpret_result = run_interpret(observe_result)
    gaps = extract_gap_items(interpret_result)
    synth_result = run_synthesize(inputs, interpret_result, gaps, quantitative_results_available=False)
    validate_result = run_validate(synth_result)
    assert not validate_result.has_errors, f"Errors: {validate_result.errors}"


def test_validate_detects_missing_sections() -> None:
    """Missing required sections should produce validation errors."""
    from spectrum_systems.modules.working_paper_engine.models import SectionDraft, SynthesizeResult
    # Create a synth result with only 2 sections
    synth_result = SynthesizeResult(
        sections=[
            SectionDraft(section_id="1", title="Introduction", content="intro"),
            SectionDraft(section_id="2", title="Background", content="background"),
        ],
        faq_items=[],
        gap_items=[],
        title="Test",
        quantitative_results_available=False,
    )
    validate_result = run_validate(synth_result)
    assert validate_result.has_errors
    assert any("Missing required sections" in e for e in validate_result.errors)


def test_validate_detects_unsupported_quantitative_claims() -> None:
    """Unsupported quantitative claims should produce validation errors."""
    from spectrum_systems.modules.working_paper_engine.models import SectionDraft, SynthesizeResult
    synth_result = SynthesizeResult(
        sections=[
            SectionDraft(section_id="1", title="Intro", content="intro"),
            SectionDraft(section_id="2", title="Background", content="background"),
            SectionDraft(section_id="3", title="Method", content="method"),
            SectionDraft(section_id="4", title="Params", content="params"),
            SectionDraft(section_id="5", title="Data", content="data"),
            SectionDraft(
                section_id="6",
                title="Results",
                content="NOTICE: Quantitative results are not available. The analysis shows that 85% of links are feasible.",
            ),
            SectionDraft(section_id="7", title="Conclusions", content="Conclusions here."),
        ],
        faq_items=[],
        gap_items=[],
        title="Test",
        quantitative_results_available=False,
    )
    validate_result = run_validate(synth_result)
    assert validate_result.has_errors
    quant_errors = [e for e in validate_result.errors if "quantitative" in e.lower()]
    assert quant_errors, "Expected unsupported quantitative claim error"


def test_validate_detects_results_implication_when_none_available() -> None:
    """Section 6 should not contain results-implication language in no-results mode."""
    from spectrum_systems.modules.working_paper_engine.models import SectionDraft, SynthesizeResult
    synth_result = SynthesizeResult(
        sections=[
            SectionDraft(section_id="1", title="Intro", content="intro"),
            SectionDraft(section_id="2", title="Background", content="background"),
            SectionDraft(section_id="3", title="Method", content="method"),
            SectionDraft(section_id="4", title="Params", content="params"),
            SectionDraft(section_id="5", title="Data", content="data"),
            SectionDraft(
                section_id="6",
                title="Results",
                content="The results indicate feasibility. Analysis shows coexistence is possible.",
            ),
            SectionDraft(section_id="7", title="Conclusions", content="Conclusions."),
        ],
        faq_items=[],
        gap_items=[],
        title="Test",
        quantitative_results_available=False,
    )
    validate_result = run_validate(synth_result)
    assert validate_result.has_errors
    implication_errors = [e for e in validate_result.errors if "implies" in e.lower() or "result" in e.lower()]
    assert implication_errors


def test_validate_detects_overstatement_in_section7() -> None:
    """Section 7 overstatement language should produce validation errors."""
    from spectrum_systems.modules.working_paper_engine.models import SectionDraft, SynthesizeResult
    synth_result = SynthesizeResult(
        sections=[
            SectionDraft(section_id="1", title="Intro", content="intro"),
            SectionDraft(section_id="2", title="Background", content="background"),
            SectionDraft(section_id="3", title="Method", content="method"),
            SectionDraft(section_id="4", title="Params", content="params"),
            SectionDraft(section_id="5", title="Data", content="data"),
            SectionDraft(section_id="6", title="Results", content="NOTICE: Quantitative results are not available."),
            SectionDraft(
                section_id="7",
                title="Conclusions",
                content="This analysis is conclusively proven. Final determination: system is feasible.",
            ),
        ],
        faq_items=[],
        gap_items=[],
        title="Test",
        quantitative_results_available=False,
    )
    validate_result = run_validate(synth_result)
    assert validate_result.has_errors
    overstatement_errors = [e for e in validate_result.errors if "overstat" in e.lower()]
    assert overstatement_errors


# ---------------------------------------------------------------------------
# Full pipeline (golden path)
# ---------------------------------------------------------------------------


def test_run_pipeline_returns_bundle() -> None:
    inputs = _minimal_inputs()
    bundle = run_pipeline(inputs)
    assert "artifact_id" in bundle
    assert bundle["artifact_id"].startswith("WPE-")


def test_run_pipeline_bundle_has_required_keys() -> None:
    inputs = _minimal_inputs()
    bundle = run_pipeline(inputs)
    for key in [
        "artifact_id", "source_artifact_ids", "report", "faq", "gap_register",
        "validation_checklist", "results_readiness", "traceability_requirements",
        "validation", "metadata",
    ]:
        assert key in bundle, f"Missing key: {key}"


def test_run_pipeline_report_has_seven_sections() -> None:
    inputs = _minimal_inputs()
    bundle = run_pipeline(inputs)
    sections = bundle["report"]["sections"]
    assert len(sections) == 7


def test_run_pipeline_no_results_case() -> None:
    """No-results case: quantitative_results_available=False."""
    inputs = _no_results_inputs()
    bundle = run_pipeline(inputs, quantitative_results_available=False)
    rr = bundle["results_readiness"]
    assert rr["quantitative_results_available"] is False
    sec6_content = bundle["report"]["sections"][5]["content"]
    assert "NOTICE" in sec6_content


def test_run_pipeline_schema_valid() -> None:
    """Output bundle must validate against the governed JSON Schema."""
    inputs = _minimal_inputs()
    bundle = run_pipeline(inputs)
    errors = validate_bundle_schema(bundle)
    assert errors == [], f"Schema validation errors: {errors}"


def test_run_pipeline_deterministic() -> None:
    """Identical structured inputs produce structurally identical outputs.

    Note: artifact_id contains a timestamp component so will differ;
    we compare structure rather than full equality.
    """
    inputs = _minimal_inputs()
    bundle1 = run_pipeline(inputs)
    bundle2 = run_pipeline(inputs)
    # Section count, titles, section IDs must be identical
    sections1 = [(s["section_id"], s["title"]) for s in bundle1["report"]["sections"]]
    sections2 = [(s["section_id"], s["title"]) for s in bundle2["report"]["sections"]]
    assert sections1 == sections2
    # Gap count should be identical
    assert len(bundle1["gap_register"]) == len(bundle2["gap_register"])
    # FAQ count should be identical
    assert len(bundle1["faq"]) == len(bundle2["faq"])


def test_run_pipeline_missing_study_plan_case() -> None:
    inputs = _missing_study_plan_inputs()
    bundle = run_pipeline(inputs)
    # Study plan is listed as missing in traceability requirements
    req_artifacts = bundle["traceability_requirements"]["required_artifacts"]
    assert any("study_plan" in a.lower() for a in req_artifacts)


def test_run_pipeline_transcript_heavy_case() -> None:
    inputs = _transcript_heavy_inputs()
    bundle = run_pipeline(inputs)
    assert len(bundle["report"]["sections"]) == 7
    # Missing source docs should be noted in readiness
    missing = bundle["results_readiness"]["missing_elements"]
    assert any("source" in m.lower() for m in missing)


def test_run_pipeline_gap_register_not_empty_for_sparse_inputs() -> None:
    """Sparse inputs with questions and missing data should produce gaps."""
    inputs = EngineInputs(
        transcripts=[TranscriptExcerpt(
            content=(
                "We do not have the measurement data. "
                "The interference thresholds are not defined. "
                "What is the required coordination zone?"
            )
        )],
    )
    bundle = run_pipeline(inputs)
    assert len(bundle["gap_register"]) > 0


# ---------------------------------------------------------------------------
# Render markdown
# ---------------------------------------------------------------------------


def test_render_markdown_returns_string() -> None:
    inputs = _minimal_inputs()
    bundle = run_pipeline(inputs)
    md = render_markdown(bundle)
    assert isinstance(md, str)
    assert len(md) > 100


def test_render_markdown_contains_section_headings() -> None:
    inputs = _minimal_inputs()
    bundle = run_pipeline(inputs)
    md = render_markdown(bundle)
    for i in range(1, 8):
        assert f"Section {i}:" in md


def test_render_markdown_contains_gap_register_section() -> None:
    inputs = _minimal_inputs()
    bundle = run_pipeline(inputs)
    md = render_markdown(bundle)
    assert "Gap Register" in md


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


def _make_inputs_json(tmp_path: Path, **kwargs) -> Path:
    data = {
        "title_hint": "Test Working Paper",
        "study_id": "TEST-001",
        "quantitative_results_available": False,
        "source_documents": [
            {
                "content": "Interference must not exceed the protection threshold. Propagation model is ITM.",
                "artifact_id": "DOC-TEST",
                "title": "Test Study",
            }
        ],
        "transcripts": [
            {
                "content": "What are the interference thresholds? We need the coastal data.",
                "artifact_id": "T-TEST",
                "meeting_title": "Test Meeting",
            }
        ],
        "study_plans": [
            {
                "content": "Assume uniform deployment. Must evaluate all candidate assignments.",
                "artifact_id": "P-TEST",
            }
        ],
    }
    data.update(kwargs)
    p = tmp_path / "inputs.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_cli_help() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--inputs" in result.stdout
    assert "--output" in result.stdout


def test_cli_missing_required_args() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_cli_valid_inputs_json_output(tmp_path: Path) -> None:
    inputs_file = _make_inputs_json(tmp_path)
    output_file = tmp_path / "bundle.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--inputs",
            str(inputs_file),
            "--output",
            str(output_file),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert output_file.is_file()
    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert "artifact_id" in data
    assert len(data["report"]["sections"]) == 7


def test_cli_pretty_report_output(tmp_path: Path) -> None:
    inputs_file = _make_inputs_json(tmp_path)
    output_file = tmp_path / "bundle.json"
    md_file = tmp_path / "report.md"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--inputs",
            str(inputs_file),
            "--output",
            str(output_file),
            "--pretty-report-out",
            str(md_file),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert md_file.is_file()
    content = md_file.read_text(encoding="utf-8")
    assert "Section 1:" in content
    assert "Gap Register" in content


def test_cli_inline_json_input(tmp_path: Path) -> None:
    inline_json = json.dumps({
        "title_hint": "Inline Test",
        "source_documents": [{"content": "Test content about spectrum."}],
        "transcripts": [],
        "study_plans": [],
    })
    output_file = tmp_path / "bundle.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--inputs",
            inline_json,
            "--output",
            str(output_file),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
