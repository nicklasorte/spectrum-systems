"""
service.py — top-level orchestrator for the Working Paper Engine pipeline.

Runs the 4-stage pipeline:
  OBSERVE → INTERPRET → SYNTHESIZE → VALIDATE

Returns a governed WorkingPaperBundle.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .artifacts import assemble_bundle
from .interpret import interpret
from .models import (
    SourceDocumentExcerpt,
    SourceType,
    StudyPlanExcerpt,
    TranscriptExcerpt,
    WorkingPaperBundle,
    WorkingPaperInputs,
)
from .observe import observe
from .synthesize import synthesize
from .validate import validate


def run_pipeline(inputs: WorkingPaperInputs) -> WorkingPaperBundle:
    """
    Run the full Working Paper Engine pipeline.

    Stages:
      1. OBSERVE  — extract and tag raw items from all inputs
      2. INTERPRET — map items into structured concern buckets
      3. SYNTHESIZE — generate sections, FAQ, gap register, readiness
      4. VALIDATE — check output for errors, warnings, and consistency

    Returns a WorkingPaperBundle with all governed outputs.
    """
    # Stage 1: OBSERVE
    observed_items = observe(inputs)

    # Stage 2: INTERPRET
    concerns = interpret(observed_items)

    # Stage 3: SYNTHESIZE
    sections, faq, gaps, readiness, traceability = synthesize(inputs, concerns)

    # Stage 4: VALIDATE
    validation_result = validate(sections, faq, gaps, readiness, traceability)

    # Assemble final bundle
    artifact_id = f"WPE-{uuid.uuid4().hex[:12].upper()}"
    created_at = datetime.now(timezone.utc).isoformat()

    bundle = assemble_bundle(
        artifact_id=artifact_id,
        inputs=inputs,
        sections=sections,
        faq=faq,
        gaps=gaps,
        readiness=readiness,
        traceability=traceability,
        validation=validation_result,
        created_at=created_at,
    )

    return bundle


def inputs_from_dict(data: Dict[str, Any]) -> WorkingPaperInputs:
    """
    Build a WorkingPaperInputs from a plain dict (e.g., loaded from JSON).

    Expected keys (all optional except 'title'):
      title                : str
      context_description  : str
      band_description     : str
      source_documents     : list of {artifact_id, locator, content, title}
      transcripts          : list of {artifact_id, locator, speaker, content}
      study_plan_excerpts  : list of {artifact_id, locator, content, objective}
    """
    source_documents = [
        SourceDocumentExcerpt(
            artifact_id=d.get("artifact_id", f"doc-{i}"),
            locator=d.get("locator", ""),
            content=d.get("content", ""),
            title=d.get("title", ""),
        )
        for i, d in enumerate(data.get("source_documents", []))
    ]

    transcripts = [
        TranscriptExcerpt(
            artifact_id=t.get("artifact_id", f"tx-{i}"),
            locator=t.get("locator", ""),
            speaker=t.get("speaker", ""),
            content=t.get("content", ""),
        )
        for i, t in enumerate(data.get("transcripts", []))
    ]

    study_plan_excerpts = [
        StudyPlanExcerpt(
            artifact_id=s.get("artifact_id", f"sp-{i}"),
            locator=s.get("locator", ""),
            content=s.get("content", ""),
            objective=s.get("objective", ""),
        )
        for i, s in enumerate(data.get("study_plan_excerpts", []))
    ]

    return WorkingPaperInputs(
        title=data.get("title", "Untitled Working Paper"),
        context_description=data.get("context_description", ""),
        band_description=data.get("band_description", ""),
        source_documents=source_documents,
        transcripts=transcripts,
        study_plan_excerpts=study_plan_excerpts,
    )
