"""
Artifact Packager Module — spectrum_systems/modules/artifact_packager.py

Writes a deterministic, canonical artifact package for a single meeting-minutes
run to the following structure:

    /artifacts/<run_id>/meeting_minutes/
        meeting_minutes.docx          (stub if not produced by caller)
        structured_extraction.json
        signals.json
        study_state.json
        recommendations.json          (stub if not provided)
        validation_report.json        (stub if not provided)
        execution_metadata.json       (stub if not provided)

Design rules:
- All seven files are always emitted.  Missing inputs produce stubs.
- Folder structure is deterministic: run_id → artifact class → files.
- File names are fixed; no dynamic naming within the package.
- All JSON files are written with indent=2 and sort_keys=True for reproducibility.
- Callers must supply structured_extraction and signals; all other inputs are
  optional and fall back to stubs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import json

from .study_state import build_study_state, validate_study_state

# ─── Constants ────────────────────────────────────────────────────────────────

ARTIFACT_CLASS = "meeting_minutes"
SCHEMA_VERSION = "1.0.0"

# Names of all files emitted in each package.
PACKAGE_FILES = [
    "meeting_minutes.docx",
    "structured_extraction.json",
    "signals.json",
    "study_state.json",
    "recommendations.json",
    "validation_report.json",
    "execution_metadata.json",
]


# ─── Stub builders ────────────────────────────────────────────────────────────

def _stub_docx_marker(run_id: str) -> bytes:
    """Return a minimal UTF-8 marker file used when no real DOCX is available."""
    marker = {
        "stub": True,
        "run_id": run_id,
        "artifact_class": ARTIFACT_CLASS,
        "note": "DOCX not produced in this run; replace with rendered document.",
    }
    return json.dumps(marker, indent=2, sort_keys=True).encode("utf-8")


def _stub_recommendations(run_id: str) -> Dict[str, Any]:
    return {
        "stub": True,
        "run_id": run_id,
        "schema_version": SCHEMA_VERSION,
        "recommendations": [],
        "note": "Recommendations not yet generated for this run.",
    }


def _stub_validation_report(run_id: str) -> Dict[str, Any]:
    return {
        "stub": True,
        "run_id": run_id,
        "schema_version": SCHEMA_VERSION,
        "passed": None,
        "errors": [],
        "warnings": [],
        "note": "Validation not yet run for this package.",
    }


def _stub_execution_metadata(run_id: str, timestamp: str) -> Dict[str, Any]:
    return {
        "stub": True,
        "run_id": run_id,
        "schema_version": SCHEMA_VERSION,
        "generated_at": timestamp,
        "pipeline": "meeting_minutes",
        "stages_completed": [],
        "note": "Execution metadata not provided by caller.",
    }


# ─── Writer helpers ───────────────────────────────────────────────────────────

def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


# ─── Validation ───────────────────────────────────────────────────────────────

def validate_package(package_dir: Path) -> Dict[str, Any]:
    """
    Validate an artifact package directory.

    Checks:
    1. All required files exist.
    2. study_state.json contains required top-level keys.
    3. action_items in study_state are mapped from structured_extraction.
    4. signals are propagated into study_state risks and decisions.

    Returns a report dict with ``passed`` (bool) and ``errors`` (list[str]).
    """
    errors: list[str] = []

    # 1. Required files exist.
    for filename in PACKAGE_FILES:
        if not (package_dir / filename).exists():
            errors.append(f"Missing required file: {filename}")

    study_state_path = package_dir / "study_state.json"
    if not study_state_path.exists():
        return {"passed": False, "errors": errors}

    # 2. study_state.json has required keys.
    try:
        state = json.loads(study_state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"Cannot read study_state.json: {exc}")
        return {"passed": False, "errors": errors}

    schema_errors = validate_study_state(state)
    errors.extend(schema_errors)

    # 3. action_items mapped from structured_extraction.
    extraction_path = package_dir / "structured_extraction.json"
    if extraction_path.exists():
        try:
            extraction = json.loads(extraction_path.read_text(encoding="utf-8"))
            extraction_ai = extraction.get("action_items", [])
            state_ai = state.get("action_items", [])
            if len(extraction_ai) != len(state_ai):
                errors.append(
                    f"action_items count mismatch: structured_extraction has "
                    f"{len(extraction_ai)}, study_state has {len(state_ai)}"
                )
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"Cannot read structured_extraction.json: {exc}")

    # 4. Signals propagated into risks and decisions.
    signals_path = package_dir / "signals.json"
    if signals_path.exists():
        try:
            signals = json.loads(signals_path.read_text(encoding="utf-8"))
            signals_risks = signals.get("risks_or_open_questions", []) if isinstance(signals, dict) else []
            signals_decisions = signals.get("decisions_made", []) if isinstance(signals, dict) else []
            state_risks = state.get("risks", [])
            state_decisions = state.get("decisions", [])
            if len(signals_risks) != len(state_risks):
                errors.append(
                    f"risks count mismatch: signals has {len(signals_risks)}, "
                    f"study_state has {len(state_risks)}"
                )
            if len(signals_decisions) != len(state_decisions):
                errors.append(
                    f"decisions count mismatch: signals has {len(signals_decisions)}, "
                    f"study_state has {len(state_decisions)}"
                )
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"Cannot read signals.json: {exc}")

    return {"passed": len(errors) == 0, "errors": errors}


# ─── Main packager ────────────────────────────────────────────────────────────

def package_artifacts(
    run_id: str,
    structured_extraction: Dict[str, Any],
    signals: Dict[str, Any],
    artifacts_root: Path = Path("artifacts"),
    docx_bytes: Optional[bytes] = None,
    recommendations: Optional[Dict[str, Any]] = None,
    validation_report: Optional[Dict[str, Any]] = None,
    execution_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Write the canonical artifact package for a single meeting-minutes run.

    Parameters
    ----------
    run_id:
        Unique identifier for the run (e.g. "run-abc123def456").
    structured_extraction:
        Full structured extraction document from the meeting minutes engine.
    signals:
        Signals document from the signal extraction stage.
    artifacts_root:
        Root directory under which packages are written.
        Defaults to ``artifacts/`` relative to the working directory.
    docx_bytes:
        Raw bytes of the rendered DOCX file, or None to emit a stub marker.
    recommendations:
        Recommendations document, or None to emit a stub.
    validation_report:
        Validation report document, or None to emit a stub.
    execution_metadata:
        Execution metadata document, or None to emit a stub.

    Returns
    -------
    dict
        A summary with keys: ``run_id``, ``package_dir``, ``files``, ``validation``.
    """
    timestamp = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
    package_dir = artifacts_root / run_id / ARTIFACT_CLASS
    package_dir.mkdir(parents=True, exist_ok=True)

    # Build study state.
    study_state = build_study_state(structured_extraction, signals)

    # Write DOCX (or stub).
    docx_path = package_dir / "meeting_minutes.docx"
    docx_path.write_bytes(docx_bytes if docx_bytes is not None else _stub_docx_marker(run_id))

    # Write JSON artifacts.
    _write_json(package_dir / "structured_extraction.json", structured_extraction)
    _write_json(package_dir / "signals.json", signals)
    _write_json(package_dir / "study_state.json", study_state)
    _write_json(
        package_dir / "recommendations.json",
        recommendations if recommendations is not None else _stub_recommendations(run_id),
    )
    _write_json(
        package_dir / "execution_metadata.json",
        execution_metadata if execution_metadata is not None else _stub_execution_metadata(run_id, timestamp),
    )

    # Write a placeholder validation_report.json so all seven files exist before
    # validate_package() runs its file-existence checks.
    _write_json(package_dir / "validation_report.json", _stub_validation_report(run_id))

    # Validate the fully-written package and replace the placeholder.
    written_validation = validate_package(package_dir)
    if validation_report is not None:
        # Merge caller-supplied report with package validation results.
        merged = {**validation_report, "package_validation": written_validation}
        _write_json(package_dir / "validation_report.json", merged)
    else:
        _write_json(package_dir / "validation_report.json", {
            **_stub_validation_report(run_id),
            "stub": False,
            "package_validation": written_validation,
        })

    files = {name: str(package_dir / name) for name in PACKAGE_FILES}
    return {
        "run_id": run_id,
        "package_dir": str(package_dir),
        "files": files,
        "validation": written_validation,
    }
