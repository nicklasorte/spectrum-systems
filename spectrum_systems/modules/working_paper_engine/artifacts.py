"""
artifacts.py — artifact assembly and serialization for the Working Paper Engine.

Responsibilities:
  - Assemble all outputs into a governed WorkingPaperBundle.
  - Serialize the bundle to a dict suitable for JSON output.
  - Build the validation checklist from ValidationFindings.
  - Provide markdown rendering for --pretty-report-out support.
  - Validate the assembled bundle against the JSON schema.

Design constraints:
  - All serialized keys must match the contract schema exactly.
  - Serialization is deterministic — no timestamps from random sources.
  - Schema validation is a best-effort gate; import errors are reported
    as warnings, not hard failures, to avoid blocking offline runs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    BundleMetadata,
    FAQItem,
    GapItem,
    Report,
    ReportSection,
    ResultsReadiness,
    TraceabilityRequirements,
    ValidationFinding,
    ValidationResult,
    WorkingPaperBundle,
    WorkingPaperInputs,
)

ENGINE_VERSION = "1.0.0"

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "schemas"
    / "working_paper_bundle.schema.json"
)


# ---------------------------------------------------------------------------
# Bundle assembly
# ---------------------------------------------------------------------------


def assemble_bundle(
    artifact_id: str,
    inputs: WorkingPaperInputs,
    sections: List[ReportSection],
    faq: List[FAQItem],
    gaps: List[GapItem],
    readiness: ResultsReadiness,
    traceability: TraceabilityRequirements,
    validation: ValidationResult,
    created_at: str,
) -> WorkingPaperBundle:
    """Assemble all pipeline outputs into a governed WorkingPaperBundle."""
    source_ids: List[str] = (
        [d.artifact_id for d in inputs.source_documents]
        + [t.artifact_id for t in inputs.transcripts]
        + [s.artifact_id for s in inputs.study_plan_excerpts]
    )

    input_summary: Dict[str, Any] = {
        "title": inputs.title,
        "num_source_documents": len(inputs.source_documents),
        "num_transcripts": len(inputs.transcripts),
        "num_study_plan_excerpts": len(inputs.study_plan_excerpts),
    }

    # Validation checklist = one entry per ValidationFinding (all severities)
    checklist: List[ValidationFinding] = (
        validation.passes + validation.warnings + validation.errors
    )

    metadata = BundleMetadata(
        engine_version=ENGINE_VERSION,
        created_at=created_at,
        input_summary=input_summary,
        provenance_mode="best_effort",
    )

    return WorkingPaperBundle(
        artifact_id=artifact_id,
        source_artifact_ids=source_ids,
        report=Report(title=inputs.title, sections=sections),
        faq=faq,
        gap_register=gaps,
        validation_checklist=checklist,
        results_readiness=readiness,
        traceability_requirements=traceability,
        validation=validation,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def bundle_to_dict(bundle: WorkingPaperBundle) -> Dict[str, Any]:
    """Convert a WorkingPaperBundle to a JSON-serializable dict."""
    return {
        "artifact_id": bundle.artifact_id,
        "source_artifact_ids": list(bundle.source_artifact_ids),
        "report": {
            "title": bundle.report.title,
            "sections": [
                {
                    "section_id": s.section_id,
                    "title": s.title,
                    "content": s.content,
                }
                for s in bundle.report.sections
            ],
        },
        "faq": [
            {
                "faq_id": f.faq_id,
                "section_ref": f.section_ref,
                "question": f.question,
                "source_refs": list(f.source_refs),
            }
            for f in bundle.faq
        ],
        "gap_register": [
            {
                "gap_id": g.gap_id,
                "description": g.description,
                "section_ref": g.section_ref,
                "gap_type": g.gap_type.value,
                "impact": g.impact.value,
                "blocking": g.blocking,
                "suggested_resolution": g.suggested_resolution,
                "source_refs": list(g.source_refs),
            }
            for g in bundle.gap_register
        ],
        "validation_checklist": [
            {
                "check_id": c.check_id,
                "text": c.text,
                "category": c.category.value,
                "severity": c.severity.value,
                "detail": c.detail,
            }
            for c in bundle.validation_checklist
        ],
        "results_readiness": {
            "quantitative_results_available": bundle.results_readiness.quantitative_results_available,
            "missing_elements": list(bundle.results_readiness.missing_elements),
            "readiness_notes": bundle.results_readiness.readiness_notes,
        },
        "traceability_requirements": {
            "required_artifacts": list(bundle.traceability_requirements.required_artifacts),
            "required_mappings": list(bundle.traceability_requirements.required_mappings),
            "required_reproducibility_inputs": list(
                bundle.traceability_requirements.required_reproducibility_inputs
            ),
        },
        "validation": {
            "passes": [_finding_to_dict(f) for f in bundle.validation.passes],
            "warnings": [_finding_to_dict(f) for f in bundle.validation.warnings],
            "errors": [_finding_to_dict(f) for f in bundle.validation.errors],
        },
        "metadata": {
            "engine_version": bundle.metadata.engine_version,
            "created_at": bundle.metadata.created_at,
            "input_summary": dict(bundle.metadata.input_summary),
            "provenance_mode": bundle.metadata.provenance_mode,
        },
    }


def _finding_to_dict(f: ValidationFinding) -> Dict[str, Any]:
    return {
        "check_id": f.check_id,
        "text": f.text,
        "category": f.category.value,
        "severity": f.severity.value,
        "detail": f.detail,
    }


# ---------------------------------------------------------------------------
# Schema validation (best-effort)
# ---------------------------------------------------------------------------


def validate_bundle_schema(bundle_dict: Dict[str, Any]) -> List[str]:
    """
    Validate the serialized bundle against the JSON schema.
    Returns a list of error messages (empty = valid).
    """
    if not SCHEMA_PATH.exists():
        return [f"Schema file not found at {SCHEMA_PATH}"]
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return ["jsonschema not installed; schema validation skipped"]
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(bundle_dict))
    return [e.message for e in errors]


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def bundle_to_markdown(bundle: WorkingPaperBundle) -> str:
    """Render the bundle as a human-readable Markdown string."""
    lines: List[str] = []

    lines.append(f"# {bundle.report.title}")
    lines.append("")
    lines.append(
        f"> **DRAFT / PRE-DECISIONAL** — Working Paper Engine v{bundle.metadata.engine_version}"
    )
    lines.append(f"> Generated: {bundle.metadata.created_at}")
    lines.append("")

    for section in bundle.report.sections:
        lines.append(f"## Section {section.section_id}: {section.title}")
        lines.append("")
        lines.append(section.content)
        lines.append("")

    if bundle.faq:
        lines.append("## Frequently Asked Questions")
        lines.append("")
        for faq in bundle.faq:
            lines.append(f"**{faq.faq_id}** *(Section {faq.section_ref})*")
            lines.append(f"Q: {faq.question}")
            lines.append("")

    if bundle.gap_register:
        lines.append("## Gap Register")
        lines.append("")
        lines.append("| Gap ID | Description | Section | Type | Impact | Blocking |")
        lines.append("|--------|-------------|---------|------|--------|---------|")
        for gap in bundle.gap_register:
            desc = gap.description[:80].replace("|", "/")
            blocking = "Yes" if gap.blocking else "No"
            lines.append(
                f"| {gap.gap_id} | {desc} | {gap.section_ref} | "
                f"{gap.gap_type.value} | {gap.impact.value} | {blocking} |"
            )
        lines.append("")

    lines.append("## Results Readiness")
    lines.append("")
    rr = bundle.results_readiness
    lines.append(
        f"**Quantitative results available:** {'Yes' if rr.quantitative_results_available else 'No'}"
    )
    lines.append(f"**Notes:** {rr.readiness_notes}")
    if rr.missing_elements:
        lines.append("")
        lines.append("**Missing elements:**")
        for el in rr.missing_elements:
            lines.append(f"- {el}")
    lines.append("")

    # Validation summary
    v = bundle.validation
    lines.append("## Validation Summary")
    lines.append("")
    lines.append(f"- Passes: {len(v.passes)}")
    lines.append(f"- Warnings: {len(v.warnings)}")
    lines.append(f"- Errors: {len(v.errors)}")
    if v.errors:
        lines.append("")
        lines.append("**Errors:**")
        for e in v.errors:
            lines.append(f"- [{e.check_id}] {e.text}")
            if e.detail:
                lines.append(f"  - Detail: {e.detail}")
    if v.warnings:
        lines.append("")
        lines.append("**Warnings:**")
        for w in v.warnings:
            lines.append(f"- [{w.check_id}] {w.text}")
    lines.append("")

    return "\n".join(lines)
