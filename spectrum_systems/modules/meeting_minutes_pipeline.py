"""
Meeting Minutes Pipeline — spectrum_systems/modules/meeting_minutes_pipeline.py

Implements the canonical meeting-minutes processing pipeline:

    load → extract → signals → build_study_state → package → working_paper

Each stage is a pure function that accepts structured inputs and returns
structured outputs.  The pipeline is designed for deterministic, reproducible
execution.

Usage (programmatic):
    from spectrum_systems.modules.meeting_minutes_pipeline import run_pipeline

    result = run_pipeline(
        run_id="run-abc123",
        transcript_text="...",
        structured_extraction={...},
        signals={...},
        artifacts_root=Path("artifacts"),
    )

The pipeline does not call any external services.  Callers are responsible
for supplying pre-extracted structured_extraction and signals documents.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .artifact_packager import package_artifacts
from .slide_intelligence import build_slide_intelligence_packet
from .study_state import build_study_state
from .working_paper_generator import generate_working_paper


# ─── Logging ──────────────────────────────────────────────────────────────────

def _get_logger(name: str = "meeting_minutes_pipeline") -> logging.Logger:
    return logging.getLogger(name)


# ─── Stage 1: Load ────────────────────────────────────────────────────────────

def stage_load(transcript_text: str, run_id: str, logger: logging.Logger) -> Dict[str, Any]:
    """
    Load stage: accept raw transcript text and produce a load result.

    Returns a dict with run metadata and the raw transcript ready for extraction.
    """
    logger.info(json.dumps({"event": "pipeline.load", "run_id": run_id, "chars": len(transcript_text)}))
    return {
        "run_id": run_id,
        "transcript": transcript_text,
        "loaded_at": datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat(),
    }


# ─── Stage 2: Extract ─────────────────────────────────────────────────────────

def stage_extract(
    load_result: Dict[str, Any],
    structured_extraction: Dict[str, Any],
    logger: logging.Logger,
) -> Dict[str, Any]:
    """
    Extract stage: validate and normalize a pre-supplied structured_extraction.

    In the current module-first architecture, extraction is performed by an
    external engine (e.g. SYS-006) and passed in as structured_extraction.
    This stage validates the document shape and propagates run metadata.
    """
    run_id = load_result["run_id"]
    action_count = len(structured_extraction.get("action_items", []))
    decision_count = len(structured_extraction.get("decisions_made", []))
    logger.info(
        json.dumps(
            {
                "event": "pipeline.extract",
                "run_id": run_id,
                "action_items": action_count,
                "decisions": decision_count,
            }
        )
    )
    return {
        "run_id": run_id,
        "structured_extraction": structured_extraction,
        "extraction_stats": {
            "action_items": action_count,
            "decisions": decision_count,
        },
    }


# ─── Stage 3: Signals ─────────────────────────────────────────────────────────

def stage_signals(
    extract_result: Dict[str, Any],
    signals: Dict[str, Any],
    logger: logging.Logger,
) -> Dict[str, Any]:
    """
    Signals stage: validate and normalize a pre-supplied signals document.

    Signals are produced by the signal extraction layer (SYS-006) and passed
    in.  This stage validates the document shape and propagates run metadata.
    """
    run_id = extract_result["run_id"]
    risks_count = len(signals.get("risks_or_open_questions", [])) if isinstance(signals, dict) else 0
    decisions_count = len(signals.get("decisions_made", [])) if isinstance(signals, dict) else 0
    logger.info(
        json.dumps(
            {
                "event": "pipeline.signals",
                "run_id": run_id,
                "risks_or_open_questions": risks_count,
                "decisions_made": decisions_count,
            }
        )
    )
    return {
        "run_id": run_id,
        "structured_extraction": extract_result["structured_extraction"],
        "signals": signals,
        "signal_stats": {
            "risks_or_open_questions": risks_count,
            "decisions_made": decisions_count,
        },
    }


# ─── Stage 4: Build Study State ───────────────────────────────────────────────

def stage_build_study_state(
    signals_result: Dict[str, Any],
    logger: logging.Logger,
) -> Dict[str, Any]:
    """
    Build study state stage: construct the study_state document.

    Populates action_items from structured_extraction and risks/decisions
    from signals.  Other study_state keys are initialized empty.
    """
    run_id = signals_result["run_id"]
    state = build_study_state(
        structured_extraction=signals_result["structured_extraction"],
        signals=signals_result["signals"],
    )
    logger.info(
        json.dumps(
            {
                "event": "pipeline.build_study_state",
                "run_id": run_id,
                "action_items": len(state.get("action_items", [])),
                "risks": len(state.get("risks", [])),
                "decisions": len(state.get("decisions", [])),
            }
        )
    )
    return {
        "run_id": run_id,
        "structured_extraction": signals_result["structured_extraction"],
        "signals": signals_result["signals"],
        "study_state": state,
    }


# ─── Stage 5: Package ─────────────────────────────────────────────────────────

def stage_package(
    study_state_result: Dict[str, Any],
    artifacts_root: Path,
    docx_bytes: Optional[bytes],
    execution_metadata: Optional[Dict[str, Any]],
    logger: logging.Logger,
) -> Dict[str, Any]:
    """
    Package stage: write the canonical artifact package.

    Calls artifact_packager.package_artifacts() which always emits all seven
    required files, using stubs for any that the caller does not supply.
    """
    run_id = study_state_result["run_id"]
    result = package_artifacts(
        run_id=run_id,
        structured_extraction=study_state_result["structured_extraction"],
        signals=study_state_result["signals"],
        artifacts_root=artifacts_root,
        docx_bytes=docx_bytes,
        execution_metadata=execution_metadata,
    )
    logger.info(
        json.dumps(
            {
                "event": "pipeline.package",
                "run_id": run_id,
                "package_dir": result["package_dir"],
                "validation_passed": result["validation"]["passed"],
                "validation_errors": result["validation"]["errors"],
            }
        )
    )
    return result


# ─── Run ID builder ───────────────────────────────────────────────────────────

def build_run_id(transcript_text: str) -> str:
    """Generate a deterministic run_id from the transcript content."""
    digest = hashlib.sha256(transcript_text.encode()).hexdigest()[:12]
    return f"run-{digest}"


# ─── Full pipeline ────────────────────────────────────────────────────────────

def run_pipeline(
    transcript_text: str,
    structured_extraction: Dict[str, Any],
    signals: Dict[str, Any],
    run_id: Optional[str] = None,
    artifacts_root: Path = Path("artifacts"),
    docx_bytes: Optional[bytes] = None,
    execution_metadata: Optional[Dict[str, Any]] = None,
    slide_deck: Optional[Dict[str, Any]] = None,
    gap_analysis: Optional[Dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """
    Run the full meeting-minutes pipeline end to end.

    Stages:
        1. load              — accept transcript text
        2. extract           — normalize structured_extraction
        3. signals           — normalize signals
        4. build_study_state — construct study_state document
        5. slide_intelligence — (optional) process slide deck artifact
        6. package           — write canonical artifact package
        7. working_paper     — generate structured working paper from all inputs

    Parameters
    ----------
    transcript_text:
        Raw transcript text (used for run_id derivation and provenance).
    structured_extraction:
        Pre-extracted structured extraction document (from SYS-006 or equivalent).
    signals:
        Pre-extracted signals document (from SYS-006 or equivalent).
    run_id:
        Optional run identifier.  Derived from transcript content if not supplied.
    artifacts_root:
        Root directory for artifact output.  Defaults to ``artifacts/``.
    docx_bytes:
        Optional raw DOCX bytes.  A stub marker is written if not provided.
    execution_metadata:
        Optional execution metadata dict.  A stub is written if not provided.
    slide_deck:
        Optional governed slide-deck artifact dict.  When provided the slide
        intelligence layer is run and its output is attached to the package
        result under the ``slide_intelligence`` key.  The pipeline does **not**
        fail if this argument is absent or ``None``.
    gap_analysis:
        Optional gap analysis document.  When provided it is passed to the
        working paper generator to enrich risks, questions, and gap sections.
        The pipeline does **not** fail if this argument is absent or ``None``.
    logger:
        Optional logger instance.  A default logger is created if not provided.

    Returns
    -------
    dict
        Package summary from stage_package: run_id, package_dir, files,
        validation, and (if slides present) slide_intelligence, and
        always a ``working_paper`` key with the structured working paper.
    """
    if logger is None:
        logger = _get_logger()

    effective_run_id = run_id or build_run_id(transcript_text)

    load_result = stage_load(transcript_text, effective_run_id, logger)
    extract_result = stage_extract(load_result, structured_extraction, logger)
    signals_result = stage_signals(extract_result, signals, logger)
    study_state_result = stage_build_study_state(signals_result, logger)
    package_result = stage_package(
        study_state_result,
        artifacts_root=artifacts_root,
        docx_bytes=docx_bytes,
        execution_metadata=execution_metadata,
        logger=logger,
    )

    # Optional slide intelligence stage — does not fail if slide_deck is absent.
    slide_signals: Optional[Dict[str, Any]] = None
    if slide_deck is not None:
        try:
            transcript_artifact = {"text": transcript_text}
            slide_packet = build_slide_intelligence_packet(
                slide_deck,
                transcript_artifact=transcript_artifact,
            )
            logger.info(
                json.dumps(
                    {
                        "event": "pipeline.slide_intelligence",
                        "run_id": effective_run_id,
                        "slides": len(slide_deck.get("slides", [])),
                        "validation_status": slide_packet.get("validation_status"),
                    }
                )
            )
            package_result["slide_intelligence"] = slide_packet
            slide_signals = slide_packet
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                json.dumps(
                    {
                        "event": "pipeline.slide_intelligence.error",
                        "run_id": effective_run_id,
                        "error": str(exc),
                    }
                )
            )

    # Build effective gap_analysis for working paper and pipeline output.
    # When slide intelligence was run, merge its canonical analysis_gaps into
    # the gap_analysis dict under the canonical_gaps key so downstream
    # consumers (meeting_minutes_record) can access machine-readable gaps.
    effective_gap_analysis: Optional[Dict[str, Any]] = (
        dict(gap_analysis) if gap_analysis else None
    )
    if slide_signals is not None:
        analysis_gaps = slide_signals.get("analysis_gaps") or []
        if analysis_gaps:
            if effective_gap_analysis is None:
                effective_gap_analysis = {}
            # Populate canonical_gaps from slide intelligence; do not
            # overwrite a value already supplied by the caller.
            if "canonical_gaps" not in effective_gap_analysis:
                effective_gap_analysis["canonical_gaps"] = list(analysis_gaps)
    if effective_gap_analysis is not None:
        package_result["gap_analysis"] = effective_gap_analysis

    # Working paper generation stage — always runs; gracefully handles missing inputs.
    try:
        working_paper = generate_working_paper(
            structured_extraction,
            slide_signals=slide_signals,
            gap_analysis=effective_gap_analysis,
        )
        logger.info(
            json.dumps(
                {
                    "event": "pipeline.working_paper",
                    "run_id": effective_run_id,
                    "key_findings": len(working_paper.get("key_findings", [])),
                    "questions": len(working_paper.get("open_questions_for_agencies", [])),
                    "traceability_entries": len(
                        working_paper.get("appendix", {}).get("source_traceability", [])
                    ),
                }
            )
        )
        package_result["working_paper"] = working_paper
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            json.dumps(
                {
                    "event": "pipeline.working_paper.error",
                    "run_id": effective_run_id,
                    "error": str(exc),
                }
            )
        )

    return package_result
