"""
Validation Module — spectrum_systems/modules/validation.py

Implements validation for the meeting-minutes workflow artifacts and
intermediate state.  Produces structured ValidationResult objects and
writes validation_report.json.

Failure categories
------------------
- input_error        : normalized case input is malformed or missing
- extraction_error   : structured_extraction is missing required keys/items
- signal_error       : signals.json is missing required keys/items
- study_state_error  : study_state.json fails propagation or schema checks
- schema_error       : a required key exists but has an unexpected type/value
- packaging_error    : artifact package is missing one or more required files
- validation_error   : the validator itself encountered an unexpected problem

Finding severity levels
-----------------------
- info     : informational; no action required
- warning  : degraded output; run may still be usable
- error    : hard failure; run result is invalid

Validation result statuses
--------------------------
- pass              : no errors, no warnings
- pass_with_warnings: warnings present but no errors
- fail              : one or more errors present
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .artifact_packager import PACKAGE_FILES
from .study_state import REQUIRED_KEYS as STUDY_STATE_REQUIRED_KEYS


# ─── Constants ────────────────────────────────────────────────────────────────

SCHEMA_VERSION = "1.0.0"

# Valid action item classification values (Part 4).
VALID_CLASSIFICATIONS = {
    "paper_content_action",
    "paper_open_issue",
    "paper_followup_analysis",
    "admin_action",
}

# Failure category constants.
CATEGORY_INPUT_ERROR = "input_error"
CATEGORY_EXTRACTION_ERROR = "extraction_error"
CATEGORY_SIGNAL_ERROR = "signal_error"
CATEGORY_STUDY_STATE_ERROR = "study_state_error"
CATEGORY_SCHEMA_ERROR = "schema_error"
CATEGORY_PACKAGING_ERROR = "packaging_error"
CATEGORY_VALIDATION_ERROR = "validation_error"

# Severity constants.
SEV_INFO = "info"
SEV_WARNING = "warning"
SEV_ERROR = "error"

# Status constants.
STATUS_PASS = "pass"
STATUS_PASS_WITH_WARNINGS = "pass_with_warnings"
STATUS_FAIL = "fail"


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class ValidationFinding:
    """A single validation finding."""

    id: str
    severity: str          # info | warning | error
    category: str          # failure category constant
    message: str
    artifact_or_stage: str
    suggested_fix: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    """Aggregated result of a validation run."""

    status: str                                    # pass | pass_with_warnings | fail
    findings: List[ValidationFinding] = field(default_factory=list)
    run_id: str = ""
    validated_at: str = ""
    schema_version: str = SCHEMA_VERSION

    # ── Derived helpers ───────────────────────────────────────────────────────

    @property
    def errors(self) -> List[ValidationFinding]:
        return [f for f in self.findings if f.severity == SEV_ERROR]

    @property
    def warnings(self) -> List[ValidationFinding]:
        return [f for f in self.findings if f.severity == SEV_WARNING]

    @property
    def infos(self) -> List[ValidationFinding]:
        return [f for f in self.findings if f.severity == SEV_INFO]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "validated_at": self.validated_at,
            "status": self.status,
            "findings": [f.to_dict() for f in self.findings],
            "summary": {
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "infos": len(self.infos),
            },
        }


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _finding_id() -> str:
    return f"F-{uuid.uuid4().hex[:8].upper()}"


def _compute_status(findings: List[ValidationFinding]) -> str:
    if any(f.severity == SEV_ERROR for f in findings):
        return STATUS_FAIL
    if any(f.severity == SEV_WARNING for f in findings):
        return STATUS_PASS_WITH_WARNINGS
    return STATUS_PASS


def _make_finding(
    severity: str,
    category: str,
    message: str,
    artifact_or_stage: str,
    suggested_fix: Optional[str] = None,
) -> ValidationFinding:
    return ValidationFinding(
        id=_finding_id(),
        severity=severity,
        category=category,
        message=message,
        artifact_or_stage=artifact_or_stage,
        suggested_fix=suggested_fix,
    )


# ─── Part 3: Input Validation ─────────────────────────────────────────────────

def validate_case_input(case_input: Dict[str, Any]) -> List[ValidationFinding]:
    """
    Validate normalized case input.

    Checks:
    - case_id is present and non-empty
    - transcript is present and non-empty
    - template is present and non-empty
    - metadata (if present) is a dict with valid shape

    If transcript normalization has clearly failed (empty/null transcript),
    the finding is classified as input_error.
    """
    findings: List[ValidationFinding] = []
    stage = "case_input"

    # case_id
    case_id = case_input.get("case_id")
    if not case_id:
        findings.append(
            _make_finding(
                SEV_ERROR,
                CATEGORY_INPUT_ERROR,
                "case_id is missing or empty",
                stage,
                "Provide a non-empty case_id string in the case input.",
            )
        )

    # transcript
    transcript = case_input.get("transcript")
    if transcript is None:
        findings.append(
            _make_finding(
                SEV_ERROR,
                CATEGORY_INPUT_ERROR,
                "transcript is missing from case input",
                stage,
                "Include the transcript text in case_input['transcript'].",
            )
        )
    elif not isinstance(transcript, str) or not transcript.strip():
        findings.append(
            _make_finding(
                SEV_ERROR,
                CATEGORY_INPUT_ERROR,
                "transcript normalization failed: transcript is empty or not a string",
                stage,
                "Ensure the transcript is a non-empty string before passing to the pipeline.",
            )
        )

    # template
    template = case_input.get("template")
    if not template:
        findings.append(
            _make_finding(
                SEV_ERROR,
                CATEGORY_INPUT_ERROR,
                "template is missing or empty",
                stage,
                "Provide a template identifier or template path in case_input['template'].",
            )
        )

    # metadata — optional; if present must be a dict
    metadata = case_input.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            findings.append(
                _make_finding(
                    SEV_ERROR,
                    CATEGORY_SCHEMA_ERROR,
                    f"metadata must be a dict when present, got {type(metadata).__name__}",
                    stage,
                    "Pass metadata as a JSON object / Python dict.",
                )
            )

    return findings


# ─── Part 4: Structured Extraction Validation ─────────────────────────────────

def validate_structured_extraction(extraction: Dict[str, Any]) -> List[ValidationFinding]:
    """
    Validate a structured_extraction document.

    Required top-level keys: participants, decisions, action_items.
    Each action_item must have: id, text, classification, confidence,
    and target_section (value may be null but key must be present).
    classification must be one of VALID_CLASSIFICATIONS.
    """
    findings: List[ValidationFinding] = []
    stage = "structured_extraction"

    if not isinstance(extraction, dict):
        findings.append(
            _make_finding(
                SEV_ERROR,
                CATEGORY_EXTRACTION_ERROR,
                "structured_extraction must be a JSON object",
                stage,
                "Ensure structured_extraction.json is a JSON object at the top level.",
            )
        )
        return findings

    # Required top-level keys.
    for key in ("participants", "decisions", "action_items"):
        if key not in extraction:
            findings.append(
                _make_finding(
                    SEV_ERROR,
                    CATEGORY_EXTRACTION_ERROR,
                    f"structured_extraction is missing required top-level key: '{key}'",
                    stage,
                    f"Add a '{key}' key to structured_extraction (may be an empty list).",
                )
            )
        elif not isinstance(extraction[key], list):
            findings.append(
                _make_finding(
                    SEV_ERROR,
                    CATEGORY_SCHEMA_ERROR,
                    f"structured_extraction['{key}'] must be a list, "
                    f"got {type(extraction[key]).__name__}",
                    stage,
                    f"Change '{key}' to a JSON array.",
                )
            )

    # action_items item-level validation.
    action_items = extraction.get("action_items", [])
    if isinstance(action_items, list):
        for idx, item in enumerate(action_items):
            prefix = f"action_items[{idx}]"
            if not isinstance(item, dict):
                findings.append(
                    _make_finding(
                        SEV_ERROR,
                        CATEGORY_SCHEMA_ERROR,
                        f"{prefix} must be a JSON object",
                        stage,
                        "Each action item must be a JSON object.",
                    )
                )
                continue

            # Required scalar fields.
            for req_field in ("id", "text", "classification", "confidence"):
                if req_field not in item:
                    findings.append(
                        _make_finding(
                            SEV_ERROR,
                            CATEGORY_EXTRACTION_ERROR,
                            f"{prefix} is missing required field: '{req_field}'",
                            stage,
                            f"Add '{req_field}' to each action item.",
                        )
                    )

            # target_section must be a key (value may be null).
            if "target_section" not in item:
                findings.append(
                    _make_finding(
                        SEV_ERROR,
                        CATEGORY_EXTRACTION_ERROR,
                        f"{prefix} is missing key 'target_section' "
                        "(value may be null but key must be present)",
                        stage,
                        "Include 'target_section': null if no section is known.",
                    )
                )

            # classification value must be from the allowed set.
            classification = item.get("classification")
            if classification is not None and classification not in VALID_CLASSIFICATIONS:
                findings.append(
                    _make_finding(
                        SEV_ERROR,
                        CATEGORY_SCHEMA_ERROR,
                        f"{prefix} has invalid classification: {classification!r}. "
                        f"Must be one of: {sorted(VALID_CLASSIFICATIONS)}",
                        stage,
                        "Set classification to one of: "
                        + ", ".join(sorted(VALID_CLASSIFICATIONS)),
                    )
                )

    return findings


# ─── Part 5: Signal Validation ────────────────────────────────────────────────

def _validate_signal_items(
    items: Any,
    list_key: str,
    required_fields: List[str],
    stage: str,
) -> List[ValidationFinding]:
    """Validate a list of signal items share a common required-field contract."""
    findings: List[ValidationFinding] = []
    if not isinstance(items, list):
        findings.append(
            _make_finding(
                SEV_ERROR,
                CATEGORY_SCHEMA_ERROR,
                f"signals['{list_key}'] must be a list, got {type(items).__name__}",
                stage,
                f"Change signals['{list_key}'] to a JSON array.",
            )
        )
        return findings

    for idx, item in enumerate(items):
        prefix = f"{list_key}[{idx}]"
        if not isinstance(item, dict):
            findings.append(
                _make_finding(
                    SEV_ERROR,
                    CATEGORY_SCHEMA_ERROR,
                    f"signals.{prefix} must be a JSON object",
                    stage,
                    f"Each item in signals['{list_key}'] must be a JSON object.",
                )
            )
            continue
        for req_field in required_fields:
            if req_field not in item:
                findings.append(
                    _make_finding(
                        SEV_ERROR,
                        CATEGORY_SIGNAL_ERROR,
                        f"signals.{prefix} is missing required field: '{req_field}'",
                        stage,
                        f"Add '{req_field}' to each item in signals['{list_key}'].",
                    )
                )
    return findings


def validate_signals(signals: Dict[str, Any]) -> List[ValidationFinding]:
    """
    Validate a signals.json document.

    Required top-level keys: questions, assumptions, risks.
    Empty arrays are allowed, but keys must exist.

    questions  items: id, text, priority, status, source_excerpt
    assumptions items: id, statement, risk_level, validation_needed, status
    risks items: id, description, severity, status
    """
    findings: List[ValidationFinding] = []
    stage = "signals"

    if not isinstance(signals, dict):
        findings.append(
            _make_finding(
                SEV_ERROR,
                CATEGORY_SIGNAL_ERROR,
                "signals must be a JSON object",
                stage,
                "Ensure signals.json is a JSON object at the top level.",
            )
        )
        return findings

    for key in ("questions", "assumptions", "risks"):
        if key not in signals:
            findings.append(
                _make_finding(
                    SEV_ERROR,
                    CATEGORY_SIGNAL_ERROR,
                    f"signals is missing required top-level key: '{key}'",
                    stage,
                    f"Add a '{key}' key to signals (may be an empty array).",
                )
            )

    # Item-level validation.
    question_fields = ["id", "text", "priority", "status", "source_excerpt"]
    findings.extend(
        _validate_signal_items(
            signals.get("questions", []), "questions", question_fields, stage
        )
    )

    assumption_fields = ["id", "statement", "risk_level", "validation_needed", "status"]
    findings.extend(
        _validate_signal_items(
            signals.get("assumptions", []), "assumptions", assumption_fields, stage
        )
    )

    risk_fields = ["id", "description", "severity", "status"]
    findings.extend(
        _validate_signal_items(
            signals.get("risks", []), "risks", risk_fields, stage
        )
    )

    return findings


# ─── Part 6: Study State Validation ──────────────────────────────────────────

def validate_study_state_document(
    state: Dict[str, Any],
    signals: Optional[Dict[str, Any]] = None,
    extraction: Optional[Dict[str, Any]] = None,
) -> List[ValidationFinding]:
    """
    Validate a study_state.json document.

    Checks:
    1. All required top-level keys are present and are lists.
    2. Propagation rules:
       - questions IDs/count from signals.questions
       - assumptions IDs/count from signals.assumptions
       - risks IDs/count from signals.risks
       - action_items IDs/count from structured_extraction.action_items
    """
    findings: List[ValidationFinding] = []
    stage = "study_state"

    if not isinstance(state, dict):
        findings.append(
            _make_finding(
                SEV_ERROR,
                CATEGORY_STUDY_STATE_ERROR,
                "study_state must be a JSON object",
                stage,
                "Ensure study_state.json is a JSON object at the top level.",
            )
        )
        return findings

    # Required keys.
    for key in STUDY_STATE_REQUIRED_KEYS:
        if key not in state:
            findings.append(
                _make_finding(
                    SEV_ERROR,
                    CATEGORY_STUDY_STATE_ERROR,
                    f"study_state is missing required key: '{key}'",
                    stage,
                    f"Add '{key}' to study_state (may be an empty list).",
                )
            )
        elif not isinstance(state[key], list):
            findings.append(
                _make_finding(
                    SEV_ERROR,
                    CATEGORY_SCHEMA_ERROR,
                    f"study_state['{key}'] must be a list, "
                    f"got {type(state[key]).__name__}",
                    stage,
                    f"Change '{key}' to a JSON array.",
                )
            )

    # Propagation checks.
    if signals is not None and isinstance(signals, dict):
        # questions
        _check_propagation(
            findings,
            stage,
            source_name="signals.questions",
            source_items=signals.get("questions", []),
            target_name="study_state.questions",
            target_items=state.get("questions", []),
        )
        # assumptions
        _check_propagation(
            findings,
            stage,
            source_name="signals.assumptions",
            source_items=signals.get("assumptions", []),
            target_name="study_state.assumptions",
            target_items=state.get("assumptions", []),
        )
        # risks
        _check_propagation(
            findings,
            stage,
            source_name="signals.risks",
            source_items=signals.get("risks", []),
            target_name="study_state.risks",
            target_items=state.get("risks", []),
        )

    if extraction is not None and isinstance(extraction, dict):
        # action_items
        _check_propagation(
            findings,
            stage,
            source_name="structured_extraction.action_items",
            source_items=extraction.get("action_items", []),
            target_name="study_state.action_items",
            target_items=state.get("action_items", []),
        )

    return findings


def _check_propagation(
    findings: List[ValidationFinding],
    stage: str,
    source_name: str,
    source_items: Any,
    target_name: str,
    target_items: Any,
) -> None:
    """Compare source and target item counts and IDs; append drift findings."""
    if not isinstance(source_items, list) or not isinstance(target_items, list):
        return

    if len(source_items) != len(target_items):
        findings.append(
            _make_finding(
                SEV_WARNING,
                CATEGORY_STUDY_STATE_ERROR,
                f"Propagation drift: {source_name} has {len(source_items)} items "
                f"but {target_name} has {len(target_items)} items",
                stage,
                f"Ensure all items from {source_name} are propagated into {target_name}.",
            )
        )
        return

    # ID-level drift check (if items are dicts with an 'id' key).
    source_ids = [
        item.get("id") for item in source_items if isinstance(item, dict) and "id" in item
    ]
    target_ids = [
        item.get("id") for item in target_items if isinstance(item, dict) and "id" in item
    ]
    if source_ids and target_ids and set(source_ids) != set(target_ids):
        missing = set(source_ids) - set(target_ids)
        extra = set(target_ids) - set(source_ids)
        detail_parts = []
        if missing:
            detail_parts.append(f"missing in {target_name}: {sorted(missing)}")
        if extra:
            detail_parts.append(f"extra in {target_name}: {sorted(extra)}")
        findings.append(
            _make_finding(
                SEV_WARNING,
                CATEGORY_STUDY_STATE_ERROR,
                f"ID drift between {source_name} and {target_name}: "
                + "; ".join(detail_parts),
                stage,
                f"Verify that all IDs from {source_name} are preserved in {target_name}.",
            )
        )


# ─── Part 7: Artifact Package Validation ──────────────────────────────────────

def validate_artifact_package(package_dir: Path) -> List[ValidationFinding]:
    """
    Validate that the artifact package directory contains all required files.

    Required files:
        meeting_minutes.docx
        structured_extraction.json
        signals.json
        study_state.json
        recommendations.json
        validation_report.json
        execution_metadata.json

    A DOCX that is a JSON stub marker generates a warning (not an error)
    because the current pipeline intentionally stubs it.
    """
    findings: List[ValidationFinding] = []
    stage = "artifact_package"

    if not package_dir.is_dir():
        findings.append(
            _make_finding(
                SEV_ERROR,
                CATEGORY_PACKAGING_ERROR,
                f"Artifact package directory does not exist: {package_dir}",
                stage,
                "Ensure the pipeline has run and written the package directory.",
            )
        )
        return findings

    for filename in PACKAGE_FILES:
        path = package_dir / filename
        if not path.exists():
            findings.append(
                _make_finding(
                    SEV_ERROR,
                    CATEGORY_PACKAGING_ERROR,
                    f"Required artifact file is missing: {filename}",
                    stage,
                    f"Ensure the pipeline writes {filename} to {package_dir}.",
                )
            )

    # Check if meeting_minutes.docx is a stub (warn, do not fail).
    docx_path = package_dir / "meeting_minutes.docx"
    if docx_path.exists():
        try:
            content = docx_path.read_bytes().decode("utf-8", errors="replace")
            data = json.loads(content)
            if data.get("stub") is True:
                findings.append(
                    _make_finding(
                        SEV_WARNING,
                        CATEGORY_PACKAGING_ERROR,
                        "meeting_minutes.docx is a stub marker; "
                        "no rendered DOCX was produced in this run",
                        stage,
                        "Replace the stub with a real rendered DOCX before delivery.",
                    )
                )
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Not a JSON stub — treat as a real DOCX; nothing to warn about.
            pass

    return findings


# ─── Part 8: Orchestrator + report writer ─────────────────────────────────────

def validate_meeting_minutes_package(
    package_dir: Path,
    case_input: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    write_report: bool = True,
) -> ValidationResult:
    """
    Orchestrate all validation checks for a meeting-minutes artifact package.

    Reads structured_extraction.json, signals.json, and study_state.json from
    *package_dir* and runs:

    1. Input validation (if case_input supplied)
    2. Structured extraction validation
    3. Signals validation
    4. Study state validation (with propagation checks)
    5. Artifact package validation

    Parameters
    ----------
    package_dir:
        Path to the canonical artifact package directory
        (e.g. ``artifacts/<run_id>/meeting_minutes/``).
    case_input:
        Optional normalized case input dict.  Input validation is skipped if
        not provided.
    run_id:
        Optional run identifier.  Derived from ``package_dir`` name if omitted.
    write_report:
        Whether to write ``validation_report.json`` into *package_dir*.

    Returns
    -------
    ValidationResult
    """
    effective_run_id = run_id or package_dir.parent.name
    validated_at = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()

    findings: List[ValidationFinding] = []

    # 1. Case input.
    if case_input is not None:
        findings.extend(validate_case_input(case_input))

    # 2–4. Load JSON artifacts from package_dir.
    extraction: Optional[Dict[str, Any]] = None
    signals_doc: Optional[Dict[str, Any]] = None
    state_doc: Optional[Dict[str, Any]] = None

    for filename, varname in [
        ("structured_extraction.json", "extraction"),
        ("signals.json", "signals_doc"),
        ("study_state.json", "state_doc"),
    ]:
        path = package_dir / filename
        if path.exists():
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
                if varname == "extraction":
                    extraction = doc
                elif varname == "signals_doc":
                    signals_doc = doc
                else:
                    state_doc = doc
            except (json.JSONDecodeError, OSError) as exc:
                findings.append(
                    _make_finding(
                        SEV_ERROR,
                        CATEGORY_VALIDATION_ERROR,
                        f"Cannot read {filename}: {exc}",
                        filename,
                        f"Ensure {filename} is valid JSON.",
                    )
                )

    if extraction is not None:
        findings.extend(validate_structured_extraction(extraction))

    if signals_doc is not None:
        findings.extend(validate_signals(signals_doc))

    if state_doc is not None:
        findings.extend(
            validate_study_state_document(
                state_doc,
                signals=signals_doc,
                extraction=extraction,
            )
        )

    # 5. Artifact package validation.
    findings.extend(validate_artifact_package(package_dir))

    status = _compute_status(findings)
    result = ValidationResult(
        status=status,
        findings=findings,
        run_id=effective_run_id,
        validated_at=validated_at,
        schema_version=SCHEMA_VERSION,
    )

    if write_report:
        report_path = package_dir / "validation_report.json"
        try:
            report_path.write_text(
                json.dumps(result.to_dict(), indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError as exc:
            # Append a finding rather than raising; the caller still gets the result.
            result.findings.append(
                _make_finding(
                    SEV_ERROR,
                    CATEGORY_VALIDATION_ERROR,
                    f"Could not write validation_report.json: {exc}",
                    "validation_report.json",
                    "Check write permissions on the package directory.",
                )
            )
            result.status = STATUS_FAIL

    return result
