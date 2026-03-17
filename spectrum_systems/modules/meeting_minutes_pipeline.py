"""
Meeting Minutes Pipeline — spectrum_systems/modules/meeting_minutes_pipeline.py

Implements the canonical meeting-minutes processing pipeline:

    load → extract → signals → build_study_state → package

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
from .study_state import build_study_state


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
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """
    Run the full meeting-minutes pipeline end to end.

    Stages:
        1. load              — accept transcript text
        2. extract           — normalize structured_extraction
        3. signals           — normalize signals
        4. build_study_state — construct study_state document
        5. package           — write canonical artifact package

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
    logger:
        Optional logger instance.  A default logger is created if not provided.

    Returns
    -------
    dict
        Package summary from stage_package: run_id, package_dir, files, validation.
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

    return package_result
