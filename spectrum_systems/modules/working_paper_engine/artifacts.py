"""
Working Paper Engine — artifacts.py

Assembles the final governed JSON output bundle from pipeline stage results.

Design principles
-----------------
- Bundle assembly is deterministic and schema-aligned.
- All IDs are stable for identical inputs (content-addressed where possible).
- Provenance mode and metadata are always populated.
- The output bundle is ready for downstream schema validation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator, ValidationError

from spectrum_systems.modules.working_paper_engine.models import (
    ChecklistItem,
    EngineInputs,
    FAQItem,
    GapItem,
    GapType,
    ImpactLevel,
    ProvenanceMode,
    SynthesizeResult,
    ValidateResult,
    ValidationCategory,
)

_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "contracts" / "schemas"
_BUNDLE_SCHEMA_PATH = _SCHEMA_DIR / "working_paper_bundle.schema.json"

ENGINE_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Standard validation checklist items included in every bundle
# ---------------------------------------------------------------------------

_STANDARD_CHECKLIST: List[ChecklistItem] = [
    ChecklistItem("VAL-001", "Source artifacts are identified and referenced.", ValidationCategory.TRACEABILITY),
    ChecklistItem("VAL-002", "All sections 1–7 are present.", ValidationCategory.COMPLETENESS),
    ChecklistItem("VAL-003", "Section 6 does not imply results if none are available.", ValidationCategory.SAFETY),
    ChecklistItem("VAL-004", "Section 7 does not overstate findings.", ValidationCategory.SAFETY),
    ChecklistItem("VAL-005", "No unsupported quantitative claims appear in the report.", ValidationCategory.SAFETY),
    ChecklistItem("VAL-006", "FAQ items are mapped to existing report sections.", ValidationCategory.TRACEABILITY),
    ChecklistItem("VAL-007", "Gap register items are mapped to existing report sections.", ValidationCategory.TRACEABILITY),
    ChecklistItem("VAL-008", "Blocking gaps are visible in Section 7.", ValidationCategory.COMPLETENESS),
    ChecklistItem("VAL-009", "Results-readiness flag is consistent with Section 6 content.", ValidationCategory.CONSISTENCY),
    ChecklistItem("VAL-010", "Study plan traceability requirements are documented.", ValidationCategory.TRACEABILITY),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _artifact_id(seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12].upper()
    return f"WPE-{digest}"


def _section_to_dict(section: Any) -> Dict[str, Any]:
    return {
        "section_id": section.section_id,
        "title": section.title,
        "content": section.content,
    }


def _faq_to_dict(faq: FAQItem) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "faq_id": faq.faq_id,
        "section_ref": faq.section_ref,
        "question": faq.question,
        "source_refs": faq.source_refs,
    }
    if faq.answer:
        d["answer"] = faq.answer
    return d


def _gap_to_dict(gap: GapItem) -> Dict[str, Any]:
    return {
        "gap_id": gap.gap_id,
        "description": gap.description,
        "section_ref": gap.section_ref,
        "gap_type": gap.gap_type.value if isinstance(gap.gap_type, GapType) else gap.gap_type,
        "impact": gap.impact.value if isinstance(gap.impact, ImpactLevel) else gap.impact,
        "blocking": gap.blocking,
        "suggested_resolution": gap.suggested_resolution,
        "source_refs": gap.source_refs,
    }


def _checklist_to_dict(item: ChecklistItem) -> Dict[str, Any]:
    return {
        "check_id": item.check_id,
        "text": item.text,
        "category": item.category.value if isinstance(item.category, ValidationCategory) else item.category,
    }


def _build_input_summary(inputs: EngineInputs) -> Dict[str, Any]:
    return {
        "source_document_count": len(inputs.source_documents),
        "transcript_count": len(inputs.transcripts),
        "study_plan_count": len(inputs.study_plans),
        "title_hint": inputs.title_hint or "",
        "study_id": inputs.study_id or "",
    }


def _build_traceability_requirements(
    inputs: EngineInputs,
    gap_items: List[GapItem],
) -> Dict[str, Any]:
    required_artifacts = ["source_documents", "meeting_transcripts", "study_plan"]
    if len(inputs.source_documents) == 0:
        required_artifacts.append("source_documents (MISSING — must be provided)")
    if len(inputs.transcripts) == 0:
        required_artifacts.append("meeting_transcripts (MISSING — none provided)")
    if len(inputs.study_plans) == 0:
        required_artifacts.append("study_plan (MISSING — none provided)")

    required_mappings = [
        "claim-to-source mapping for all findings",
        "assumption-to-source mapping for all stated assumptions",
        "constraint-to-source mapping for all protection criteria",
    ]

    required_reproducibility = [
        "complete source document set",
        "meeting transcript set",
        "study plan / tasking guidance document",
        "engine version pin",
        "input JSON or structured input files",
    ]

    return {
        "required_artifacts": required_artifacts,
        "required_mappings": required_mappings,
        "required_reproducibility_inputs": required_reproducibility,
    }


def assemble_bundle(
    inputs: EngineInputs,
    synth_result: SynthesizeResult,
    validate_result: ValidateResult,
    provenance_mode: ProvenanceMode = ProvenanceMode.BEST_EFFORT,
) -> Dict[str, Any]:
    """Assemble the final governed JSON output bundle.

    Parameters
    ----------
    inputs:
        Original engine inputs.
    synth_result:
        Output from the SYNTHESIZE stage.
    validate_result:
        Output from the VALIDATE stage.
    provenance_mode:
        Provenance tracking mode used during generation.

    Returns
    -------
    dict
        The full governed output bundle as a plain Python dict, ready for
        JSON serialization.
    """
    created_at = _now_iso()
    seed = f"{synth_result.title}|{created_at}|{len(synth_result.sections)}"
    artifact_id = _artifact_id(seed)

    source_ids = (
        [d.artifact_id for d in inputs.source_documents if d.artifact_id]
        + [t.artifact_id for t in inputs.transcripts if t.artifact_id]
        + [p.artifact_id for p in inputs.study_plans if p.artifact_id]
    )

    # Determine missing elements for results readiness
    missing_elements: List[str] = []
    if len(inputs.source_documents) == 0:
        missing_elements.append("source documents")
    if len(inputs.study_plans) == 0:
        missing_elements.append("study plan / tasking guidance")
    blocking_gaps = [g for g in synth_result.gap_items if g.blocking]
    for g in blocking_gaps[:5]:
        missing_elements.append(f"resolve {g.gap_id}: {g.description[:60]}")

    if synth_result.quantitative_results_available:
        readiness_notes = "Quantitative results are available. Paper is in results-reporting mode."
    else:
        readiness_notes = (
            "Quantitative results are not yet available. "
            f"{len(blocking_gaps)} blocking gap(s) must be resolved before results can be reported. "
            "Section 6 is in results-framework mode."
        )

    bundle: Dict[str, Any] = {
        "artifact_id": artifact_id,
        "source_artifact_ids": source_ids,
        "report": {
            "title": synth_result.title,
            "sections": [_section_to_dict(s) for s in synth_result.sections],
        },
        "faq": [_faq_to_dict(f) for f in synth_result.faq_items],
        "gap_register": [_gap_to_dict(g) for g in synth_result.gap_items],
        "validation_checklist": [_checklist_to_dict(c) for c in _STANDARD_CHECKLIST],
        "results_readiness": {
            "quantitative_results_available": synth_result.quantitative_results_available,
            "missing_elements": missing_elements,
            "readiness_notes": readiness_notes,
        },
        "traceability_requirements": _build_traceability_requirements(
            inputs, synth_result.gap_items
        ),
        "validation": {
            "passes": validate_result.passes,
            "warnings": validate_result.warnings,
            "errors": validate_result.errors,
        },
        "metadata": {
            "engine_version": ENGINE_VERSION,
            "created_at": created_at,
            "input_summary": _build_input_summary(inputs),
            "provenance_mode": provenance_mode.value
            if isinstance(provenance_mode, ProvenanceMode)
            else provenance_mode,
        },
    }

    return bundle


def validate_bundle_schema(bundle: Dict[str, Any]) -> List[str]:
    """Validate the bundle against the governed JSON Schema.

    Returns a list of validation error messages. Empty list means valid.
    """
    if not _BUNDLE_SCHEMA_PATH.exists():
        return [f"Bundle schema not found at {_BUNDLE_SCHEMA_PATH}"]

    schema = json.loads(_BUNDLE_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = [str(e.message) for e in validator.iter_errors(bundle)]
    return errors


def render_markdown(bundle: Dict[str, Any]) -> str:
    """Render a human-readable Markdown version of the bundle.

    Parameters
    ----------
    bundle:
        The assembled output bundle dict.

    Returns
    -------
    str
        Markdown text suitable for a working paper review document.
    """
    report = bundle.get("report", {})
    lines: List[str] = []

    lines.append(f"# {report.get('title', 'Working Paper')}")
    lines.append("")
    lines.append(f"**Artifact ID:** {bundle.get('artifact_id', '')}")
    lines.append(f"**Generated:** {bundle.get('metadata', {}).get('created_at', '')}")
    lines.append(f"**Engine Version:** {bundle.get('metadata', {}).get('engine_version', '')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for section in report.get("sections", []):
        lines.append(f"## Section {section['section_id']}: {section['title']}")
        lines.append("")
        lines.append(section["content"])
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## FAQ")
    lines.append("")
    faq = bundle.get("faq", [])
    if faq:
        for item in faq:
            lines.append(f"**{item['faq_id']} (Section {item['section_ref']}):** {item['question']}")
            if item.get("answer"):
                lines.append(f"*Answer:* {item['answer']}")
            lines.append("")
    else:
        lines.append("*No FAQ items extracted.*")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Gap Register")
    lines.append("")
    gaps = bundle.get("gap_register", [])
    if gaps:
        for gap in gaps:
            blocking = " **(BLOCKING)**" if gap.get("blocking") else ""
            lines.append(
                f"- **{gap['gap_id']}** [{gap['gap_type']} / {gap['impact']}]{blocking}: "
                f"{gap['description']}"
            )
            lines.append(f"  - Section: {gap['section_ref']}")
            lines.append(f"  - Resolution: {gap['suggested_resolution']}")
            lines.append("")
    else:
        lines.append("*No gaps identified.*")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Results Readiness")
    lines.append("")
    rr = bundle.get("results_readiness", {})
    avail = rr.get("quantitative_results_available", False)
    lines.append(f"**Quantitative Results Available:** {'Yes' if avail else 'No'}")
    lines.append(f"**Notes:** {rr.get('readiness_notes', '')}")
    missing = rr.get("missing_elements", [])
    if missing:
        lines.append("")
        lines.append("**Missing Elements:**")
        for item in missing:
            lines.append(f"- {item}")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Validation Summary")
    lines.append("")
    val = bundle.get("validation", {})
    passes = val.get("passes", [])
    warnings = val.get("warnings", [])
    errors = val.get("errors", [])
    lines.append(f"**Passes:** {len(passes)}  **Warnings:** {len(warnings)}  **Errors:** {len(errors)}")
    lines.append("")
    if errors:
        lines.append("**Errors:**")
        for e in errors:
            lines.append(f"- ❌ {e}")
        lines.append("")
    if warnings:
        lines.append("**Warnings:**")
        for w in warnings:
            lines.append(f"- ⚠️ {w}")
        lines.append("")

    return "\n".join(lines)
