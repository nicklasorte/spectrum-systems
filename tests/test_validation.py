"""
Tests for spectrum_systems/modules/validation.py

Covers all eight parts specified in Prompt O:
  Part 1-2  : ValidationFinding / ValidationResult data classes
  Part 3    : validate_case_input
  Part 4    : validate_structured_extraction
  Part 5    : validate_signals
  Part 6    : validate_study_state_document (propagation)
  Part 7    : validate_artifact_package
  Part 8    : validate_meeting_minutes_package (orchestrator + report writer)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from spectrum_systems.modules.validation import (
    CATEGORY_EXTRACTION_ERROR,
    CATEGORY_INPUT_ERROR,
    CATEGORY_PACKAGING_ERROR,
    CATEGORY_SCHEMA_ERROR,
    CATEGORY_SIGNAL_ERROR,
    CATEGORY_STUDY_STATE_ERROR,
    CATEGORY_VALIDATION_ERROR,
    SEV_ERROR,
    SEV_INFO,
    SEV_WARNING,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_PASS_WITH_WARNINGS,
    VALID_CLASSIFICATIONS,
    ValidationFinding,
    ValidationResult,
    validate_artifact_package,
    validate_case_input,
    validate_meeting_minutes_package,
    validate_signals,
    validate_structured_extraction,
    validate_study_state_document,
)
from spectrum_systems.modules.artifact_packager import PACKAGE_FILES, package_artifacts


# ─── Shared fixtures ──────────────────────────────────────────────────────────

VALID_CASE_INPUT: Dict[str, Any] = {
    "case_id": "CASE-001",
    "transcript": "Alice: Good morning. Bob: Let's begin.",
    "template": "meeting_minutes_v1",
}

VALID_EXTRACTION: Dict[str, Any] = {
    "participants": ["Alice", "Bob"],
    "decisions": ["Proceed with plan A"],
    "action_items": [
        {
            "id": "AI-001",
            "text": "Run the interference test",
            "classification": "paper_content_action",
            "confidence": 0.95,
            "target_section": "Testing",
        },
        {
            "id": "AI-002",
            "text": "Confirm vendor lead time",
            "classification": "admin_action",
            "confidence": 0.88,
            "target_section": None,
        },
    ],
}

VALID_SIGNALS: Dict[str, Any] = {
    "questions": [
        {
            "id": "Q-001",
            "text": "What is the margin risk?",
            "priority": "high",
            "status": "open",
            "source_excerpt": "Alice mentioned margin risk at 10:05",
        }
    ],
    "assumptions": [
        {
            "id": "ASM-001",
            "statement": "Antenna delivery will not slip",
            "risk_level": "medium",
            "validation_needed": True,
            "status": "unvalidated",
        }
    ],
    "risks": [
        {
            "id": "RSK-001",
            "description": "Schedule slip if antenna is delayed",
            "severity": "medium",
            "status": "open",
        }
    ],
}

VALID_STUDY_STATE: Dict[str, Any] = {
    "questions": [{"id": "Q-001"}],
    "assumptions": [{"id": "ASM-001"}],
    "risks": [{"id": "RSK-001"}],
    "action_items": [{"id": "AI-001"}, {"id": "AI-002"}],
    "decisions": [],
    "issues": [],
    "evidence": [],
    "data_needs": [],
    "stakeholder_positions": [],
}

# Old-style signals used by artifact_packager / study_state fixtures.
# The existing pipeline (meeting_minutes_pipeline / artifact_packager) still uses
# the v1.0.0 signals schema with "risks_or_open_questions" and "decisions_made".
# The new validation module validates against the updated schema (questions /
# assumptions / risks).  Tests that exercise the packager directly use old-style
# data; tests that exercise the validator orchestrator use VALID_SIGNALS above.
OLD_STYLE_SIGNALS: Dict[str, Any] = {
    "decisions_made": [],
    "risks_or_open_questions": [],
}

# Old-style extraction used by artifact_packager fixtures.
# The packager's build_study_state consumes "action_items" (list of action_id/task
# dicts) from the v1.0.0 extraction shape.  The new validator requires the updated
# shape (id / text / classification / confidence / target_section).  Packager-only
# tests use this; orchestrator/validator tests use VALID_EXTRACTION above.
OLD_STYLE_EXTRACTION: Dict[str, Any] = {
    "action_items": [],
    "decisions_made": [],
}


# ─── Part 1-2: ValidationFinding / ValidationResult ───────────────────────────

class TestValidationFinding:
    def test_has_required_fields(self) -> None:
        f = ValidationFinding(
            id="F-001",
            severity=SEV_ERROR,
            category=CATEGORY_INPUT_ERROR,
            message="Something went wrong",
            artifact_or_stage="case_input",
        )
        assert f.id == "F-001"
        assert f.severity == SEV_ERROR
        assert f.category == CATEGORY_INPUT_ERROR
        assert f.message == "Something went wrong"
        assert f.artifact_or_stage == "case_input"
        assert f.suggested_fix is None

    def test_to_dict_keys(self) -> None:
        f = ValidationFinding(
            id="F-002",
            severity=SEV_WARNING,
            category=CATEGORY_SIGNAL_ERROR,
            message="msg",
            artifact_or_stage="signals",
            suggested_fix="fix it",
        )
        d = f.to_dict()
        for key in ("id", "severity", "category", "message", "artifact_or_stage", "suggested_fix"):
            assert key in d

    def test_suggested_fix_nullable(self) -> None:
        f = ValidationFinding(
            id="F-003",
            severity=SEV_INFO,
            category=CATEGORY_INPUT_ERROR,
            message="info",
            artifact_or_stage="stage",
            suggested_fix=None,
        )
        assert f.to_dict()["suggested_fix"] is None


class TestValidationResult:
    def test_status_fail_when_errors(self) -> None:
        findings = [
            ValidationFinding("F-1", SEV_ERROR, CATEGORY_INPUT_ERROR, "err", "stage")
        ]
        result = ValidationResult(status=STATUS_FAIL, findings=findings)
        assert result.status == STATUS_FAIL
        assert len(result.errors) == 1
        assert len(result.warnings) == 0

    def test_status_pass_with_warnings(self) -> None:
        findings = [
            ValidationFinding("F-2", SEV_WARNING, CATEGORY_PACKAGING_ERROR, "warn", "stage")
        ]
        result = ValidationResult(status=STATUS_PASS_WITH_WARNINGS, findings=findings)
        assert result.status == STATUS_PASS_WITH_WARNINGS
        assert len(result.warnings) == 1
        assert len(result.errors) == 0

    def test_to_dict_has_expected_keys(self) -> None:
        result = ValidationResult(
            status=STATUS_PASS,
            findings=[],
            run_id="run-001",
            validated_at="2026-01-01T00:00:00+00:00",
        )
        d = result.to_dict()
        for key in ("status", "findings", "run_id", "validated_at", "summary", "schema_version"):
            assert key in d

    def test_summary_counts_correct(self) -> None:
        findings = [
            ValidationFinding("F-1", SEV_ERROR, CATEGORY_INPUT_ERROR, "e", "s"),
            ValidationFinding("F-2", SEV_WARNING, CATEGORY_SIGNAL_ERROR, "w", "s"),
            ValidationFinding("F-3", SEV_INFO, CATEGORY_INPUT_ERROR, "i", "s"),
        ]
        result = ValidationResult(status=STATUS_FAIL, findings=findings)
        summary = result.to_dict()["summary"]
        assert summary["errors"] == 1
        assert summary["warnings"] == 1
        assert summary["infos"] == 1


# ─── Part 3: validate_case_input ──────────────────────────────────────────────

class TestValidateCaseInput:
    def test_valid_input_passes(self) -> None:
        assert validate_case_input(VALID_CASE_INPUT) == []

    def test_missing_case_id(self) -> None:
        bad = {**VALID_CASE_INPUT}
        del bad["case_id"]
        findings = validate_case_input(bad)
        assert any(f.severity == SEV_ERROR and f.category == CATEGORY_INPUT_ERROR for f in findings)
        assert any("case_id" in f.message for f in findings)

    def test_empty_case_id(self) -> None:
        bad = {**VALID_CASE_INPUT, "case_id": ""}
        findings = validate_case_input(bad)
        assert any("case_id" in f.message for f in findings)

    def test_missing_transcript(self) -> None:
        bad = {**VALID_CASE_INPUT}
        del bad["transcript"]
        findings = validate_case_input(bad)
        assert any("transcript" in f.message for f in findings)
        assert any(f.category == CATEGORY_INPUT_ERROR for f in findings)

    def test_empty_transcript_classified_as_input_error(self) -> None:
        bad = {**VALID_CASE_INPUT, "transcript": "   "}
        findings = validate_case_input(bad)
        assert any(f.category == CATEGORY_INPUT_ERROR for f in findings)

    def test_non_string_transcript(self) -> None:
        bad = {**VALID_CASE_INPUT, "transcript": 42}
        findings = validate_case_input(bad)
        assert any(f.severity == SEV_ERROR for f in findings)

    def test_missing_template(self) -> None:
        bad = {**VALID_CASE_INPUT}
        del bad["template"]
        findings = validate_case_input(bad)
        assert any("template" in f.message for f in findings)
        assert any(f.category == CATEGORY_INPUT_ERROR for f in findings)

    def test_valid_metadata_passes(self) -> None:
        good = {**VALID_CASE_INPUT, "metadata": {"version": "1.0"}}
        assert validate_case_input(good) == []

    def test_invalid_metadata_type(self) -> None:
        bad = {**VALID_CASE_INPUT, "metadata": "not-a-dict"}
        findings = validate_case_input(bad)
        assert any(f.category == CATEGORY_SCHEMA_ERROR for f in findings)
        assert any("metadata" in f.message for f in findings)

    def test_none_metadata_is_ignored(self) -> None:
        """metadata absent from input is allowed."""
        assert validate_case_input(VALID_CASE_INPUT) == []


# ─── Part 4: validate_structured_extraction ───────────────────────────────────

class TestValidateStructuredExtraction:
    def test_valid_extraction_passes(self) -> None:
        assert validate_structured_extraction(VALID_EXTRACTION) == []

    def test_not_dict_returns_error(self) -> None:
        findings = validate_structured_extraction([])  # type: ignore[arg-type]
        assert any(f.severity == SEV_ERROR for f in findings)

    def test_missing_participants(self) -> None:
        bad = {k: v for k, v in VALID_EXTRACTION.items() if k != "participants"}
        findings = validate_structured_extraction(bad)
        assert any("participants" in f.message for f in findings)
        assert any(f.category == CATEGORY_EXTRACTION_ERROR for f in findings)

    def test_missing_decisions(self) -> None:
        bad = {k: v for k, v in VALID_EXTRACTION.items() if k != "decisions"}
        findings = validate_structured_extraction(bad)
        assert any("decisions" in f.message for f in findings)

    def test_missing_action_items(self) -> None:
        bad = {k: v for k, v in VALID_EXTRACTION.items() if k != "action_items"}
        findings = validate_structured_extraction(bad)
        assert any("action_items" in f.message for f in findings)

    def test_action_items_not_list(self) -> None:
        bad = {**VALID_EXTRACTION, "action_items": "wrong"}
        findings = validate_structured_extraction(bad)
        assert any(f.category == CATEGORY_SCHEMA_ERROR for f in findings)

    def test_action_item_missing_id(self) -> None:
        item = {k: v for k, v in VALID_EXTRACTION["action_items"][0].items() if k != "id"}
        bad = {**VALID_EXTRACTION, "action_items": [item]}
        findings = validate_structured_extraction(bad)
        assert any("'id'" in f.message for f in findings)

    def test_action_item_missing_text(self) -> None:
        item = {k: v for k, v in VALID_EXTRACTION["action_items"][0].items() if k != "text"}
        bad = {**VALID_EXTRACTION, "action_items": [item]}
        findings = validate_structured_extraction(bad)
        assert any("'text'" in f.message for f in findings)

    def test_action_item_missing_classification(self) -> None:
        item = {k: v for k, v in VALID_EXTRACTION["action_items"][0].items() if k != "classification"}
        bad = {**VALID_EXTRACTION, "action_items": [item]}
        findings = validate_structured_extraction(bad)
        assert any("'classification'" in f.message for f in findings)

    def test_action_item_missing_confidence(self) -> None:
        item = {k: v for k, v in VALID_EXTRACTION["action_items"][0].items() if k != "confidence"}
        bad = {**VALID_EXTRACTION, "action_items": [item]}
        findings = validate_structured_extraction(bad)
        assert any("'confidence'" in f.message for f in findings)

    def test_action_item_missing_target_section_key(self) -> None:
        item = {k: v for k, v in VALID_EXTRACTION["action_items"][0].items() if k != "target_section"}
        bad = {**VALID_EXTRACTION, "action_items": [item]}
        findings = validate_structured_extraction(bad)
        assert any("target_section" in f.message for f in findings)

    def test_action_item_target_section_null_is_valid(self) -> None:
        item = {**VALID_EXTRACTION["action_items"][0], "target_section": None}
        good = {**VALID_EXTRACTION, "action_items": [item]}
        assert validate_structured_extraction(good) == []

    def test_invalid_classification_value(self) -> None:
        item = {**VALID_EXTRACTION["action_items"][0], "classification": "bad_class"}
        bad = {**VALID_EXTRACTION, "action_items": [item]}
        findings = validate_structured_extraction(bad)
        assert any(f.category == CATEGORY_SCHEMA_ERROR for f in findings)
        assert any("bad_class" in f.message for f in findings)

    def test_all_valid_classifications_accepted(self) -> None:
        for cls in VALID_CLASSIFICATIONS:
            item = {**VALID_EXTRACTION["action_items"][0], "classification": cls}
            good = {**VALID_EXTRACTION, "action_items": [item]}
            assert validate_structured_extraction(good) == [], f"Should accept: {cls}"

    def test_empty_action_items_is_valid(self) -> None:
        good = {**VALID_EXTRACTION, "action_items": []}
        assert validate_structured_extraction(good) == []


# ─── Part 5: validate_signals ─────────────────────────────────────────────────

class TestValidateSignals:
    def test_valid_signals_passes(self) -> None:
        assert validate_signals(VALID_SIGNALS) == []

    def test_not_dict_returns_error(self) -> None:
        findings = validate_signals([])  # type: ignore[arg-type]
        assert any(f.severity == SEV_ERROR for f in findings)

    def test_missing_questions_key(self) -> None:
        bad = {k: v for k, v in VALID_SIGNALS.items() if k != "questions"}
        findings = validate_signals(bad)
        assert any("questions" in f.message for f in findings)
        assert any(f.category == CATEGORY_SIGNAL_ERROR for f in findings)

    def test_missing_assumptions_key(self) -> None:
        bad = {k: v for k, v in VALID_SIGNALS.items() if k != "assumptions"}
        findings = validate_signals(bad)
        assert any("assumptions" in f.message for f in findings)

    def test_missing_risks_key(self) -> None:
        bad = {k: v for k, v in VALID_SIGNALS.items() if k != "risks"}
        findings = validate_signals(bad)
        assert any("risks" in f.message for f in findings)

    def test_empty_arrays_allowed(self) -> None:
        empty = {"questions": [], "assumptions": [], "risks": []}
        assert validate_signals(empty) == []

    def test_question_missing_id(self) -> None:
        q = {k: v for k, v in VALID_SIGNALS["questions"][0].items() if k != "id"}
        bad = {**VALID_SIGNALS, "questions": [q]}
        findings = validate_signals(bad)
        assert any("'id'" in f.message for f in findings)

    def test_question_missing_text(self) -> None:
        q = {k: v for k, v in VALID_SIGNALS["questions"][0].items() if k != "text"}
        bad = {**VALID_SIGNALS, "questions": [q]}
        findings = validate_signals(bad)
        assert any("'text'" in f.message for f in findings)

    def test_question_missing_priority(self) -> None:
        q = {k: v for k, v in VALID_SIGNALS["questions"][0].items() if k != "priority"}
        bad = {**VALID_SIGNALS, "questions": [q]}
        findings = validate_signals(bad)
        assert any("'priority'" in f.message for f in findings)

    def test_question_missing_status(self) -> None:
        q = {k: v for k, v in VALID_SIGNALS["questions"][0].items() if k != "status"}
        bad = {**VALID_SIGNALS, "questions": [q]}
        findings = validate_signals(bad)
        assert any("'status'" in f.message for f in findings)

    def test_question_missing_source_excerpt(self) -> None:
        q = {k: v for k, v in VALID_SIGNALS["questions"][0].items() if k != "source_excerpt"}
        bad = {**VALID_SIGNALS, "questions": [q]}
        findings = validate_signals(bad)
        assert any("'source_excerpt'" in f.message for f in findings)

    def test_assumption_missing_statement(self) -> None:
        a = {k: v for k, v in VALID_SIGNALS["assumptions"][0].items() if k != "statement"}
        bad = {**VALID_SIGNALS, "assumptions": [a]}
        findings = validate_signals(bad)
        assert any("'statement'" in f.message for f in findings)

    def test_assumption_missing_risk_level(self) -> None:
        a = {k: v for k, v in VALID_SIGNALS["assumptions"][0].items() if k != "risk_level"}
        bad = {**VALID_SIGNALS, "assumptions": [a]}
        findings = validate_signals(bad)
        assert any("'risk_level'" in f.message for f in findings)

    def test_assumption_missing_validation_needed(self) -> None:
        a = {k: v for k, v in VALID_SIGNALS["assumptions"][0].items() if k != "validation_needed"}
        bad = {**VALID_SIGNALS, "assumptions": [a]}
        findings = validate_signals(bad)
        assert any("'validation_needed'" in f.message for f in findings)

    def test_risk_missing_description(self) -> None:
        r = {k: v for k, v in VALID_SIGNALS["risks"][0].items() if k != "description"}
        bad = {**VALID_SIGNALS, "risks": [r]}
        findings = validate_signals(bad)
        assert any("'description'" in f.message for f in findings)

    def test_risk_missing_severity(self) -> None:
        r = {k: v for k, v in VALID_SIGNALS["risks"][0].items() if k != "severity"}
        bad = {**VALID_SIGNALS, "risks": [r]}
        findings = validate_signals(bad)
        assert any("'severity'" in f.message for f in findings)

    def test_risk_missing_status(self) -> None:
        r = {k: v for k, v in VALID_SIGNALS["risks"][0].items() if k != "status"}
        bad = {**VALID_SIGNALS, "risks": [r]}
        findings = validate_signals(bad)
        assert any("'status'" in f.message for f in findings)

    def test_list_wrong_type(self) -> None:
        bad = {**VALID_SIGNALS, "risks": "not-a-list"}
        findings = validate_signals(bad)
        assert any(f.category == CATEGORY_SCHEMA_ERROR for f in findings)


# ─── Part 6: validate_study_state_document ────────────────────────────────────

class TestValidateStudyStateDocument:
    def test_valid_state_no_propagation_check_passes(self) -> None:
        assert validate_study_state_document(VALID_STUDY_STATE) == []

    def test_not_dict_returns_error(self) -> None:
        findings = validate_study_state_document([])  # type: ignore[arg-type]
        assert any(f.severity == SEV_ERROR for f in findings)

    def test_missing_required_key(self) -> None:
        bad = {k: v for k, v in VALID_STUDY_STATE.items() if k != "action_items"}
        findings = validate_study_state_document(bad)
        assert any("action_items" in f.message for f in findings)
        assert any(f.category == CATEGORY_STUDY_STATE_ERROR for f in findings)

    def test_required_key_wrong_type(self) -> None:
        bad = {**VALID_STUDY_STATE, "risks": "not-a-list"}
        findings = validate_study_state_document(bad)
        assert any(f.category == CATEGORY_SCHEMA_ERROR for f in findings)

    def test_propagation_count_match_passes(self) -> None:
        findings = validate_study_state_document(
            VALID_STUDY_STATE, signals=VALID_SIGNALS, extraction=VALID_EXTRACTION
        )
        assert not any(f.category == CATEGORY_STUDY_STATE_ERROR for f in findings)

    def test_propagation_count_mismatch_flags_warning(self) -> None:
        drifted = {**VALID_STUDY_STATE, "risks": []}
        findings = validate_study_state_document(
            drifted, signals=VALID_SIGNALS, extraction=VALID_EXTRACTION
        )
        assert any(
            f.severity == SEV_WARNING and f.category == CATEGORY_STUDY_STATE_ERROR
            for f in findings
        )

    def test_propagation_id_drift_flags_warning(self) -> None:
        drifted = {**VALID_STUDY_STATE, "risks": [{"id": "RSK-999"}]}
        findings = validate_study_state_document(
            drifted, signals=VALID_SIGNALS, extraction=VALID_EXTRACTION
        )
        assert any(
            f.severity == SEV_WARNING and "RSK" in f.message
            for f in findings
        )

    def test_action_items_propagation_mismatch(self) -> None:
        drifted = {**VALID_STUDY_STATE, "action_items": [{"id": "AI-001"}]}
        findings = validate_study_state_document(
            drifted, signals=VALID_SIGNALS, extraction=VALID_EXTRACTION
        )
        assert any(f.severity == SEV_WARNING for f in findings)

    def test_propagation_skipped_without_signals(self) -> None:
        """No propagation findings when signals/extraction not supplied."""
        findings = validate_study_state_document(VALID_STUDY_STATE)
        assert all(f.category != CATEGORY_STUDY_STATE_ERROR for f in findings)


# ─── Part 7: validate_artifact_package ───────────────────────────────────────

class TestValidateArtifactPackage:
    def test_valid_package_passes_with_docx_stub_warning(self, tmp_path: Path) -> None:
        package_artifacts(
            run_id="run-pkg-001",
            structured_extraction=OLD_STYLE_EXTRACTION,
            signals=OLD_STYLE_SIGNALS,
            artifacts_root=tmp_path,
        )
        package_dir = tmp_path / "run-pkg-001" / "meeting_minutes"
        findings = validate_artifact_package(package_dir)
        # Only warning (stub DOCX), no errors.
        assert all(f.severity != SEV_ERROR for f in findings)
        assert any(f.severity == SEV_WARNING and "stub" in f.message.lower() for f in findings)

    def test_valid_package_with_real_docx_passes_clean(self, tmp_path: Path) -> None:
        package_artifacts(
            run_id="run-pkg-002",
            structured_extraction=OLD_STYLE_EXTRACTION,
            signals=OLD_STYLE_SIGNALS,
            artifacts_root=tmp_path,
            docx_bytes=b"PK real docx content",
        )
        package_dir = tmp_path / "run-pkg-002" / "meeting_minutes"
        findings = validate_artifact_package(package_dir)
        assert findings == []

    def test_missing_file_classified_as_packaging_error(self, tmp_path: Path) -> None:
        package_artifacts(
            run_id="run-pkg-003",
            structured_extraction=OLD_STYLE_EXTRACTION,
            signals=OLD_STYLE_SIGNALS,
            artifacts_root=tmp_path,
        )
        package_dir = tmp_path / "run-pkg-003" / "meeting_minutes"
        (package_dir / "signals.json").unlink()
        findings = validate_artifact_package(package_dir)
        assert any(
            f.severity == SEV_ERROR
            and f.category == CATEGORY_PACKAGING_ERROR
            and "signals.json" in f.message
            for f in findings
        )

    def test_nonexistent_dir_returns_error(self, tmp_path: Path) -> None:
        findings = validate_artifact_package(tmp_path / "nonexistent")
        assert any(f.severity == SEV_ERROR and f.category == CATEGORY_PACKAGING_ERROR for f in findings)

    def test_all_package_files_covered(self, tmp_path: Path) -> None:
        """Remove each required file in turn and verify an error is emitted."""
        for filename in PACKAGE_FILES:
            package_artifacts(
                run_id=f"run-cover-{filename[:6]}",
                structured_extraction=OLD_STYLE_EXTRACTION,
                signals=OLD_STYLE_SIGNALS,
                artifacts_root=tmp_path,
                docx_bytes=b"PK real",
            )
            package_dir = tmp_path / f"run-cover-{filename[:6]}" / "meeting_minutes"
            (package_dir / filename).unlink()
            findings = validate_artifact_package(package_dir)
            assert any(
                f.severity == SEV_ERROR and filename in f.message for f in findings
            ), f"Expected error for missing {filename}"


# ─── Part 8: validate_meeting_minutes_package ─────────────────────────────────

def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


class TestValidateMeetingMinutesPackage:
    def _build_package(self, tmp_path: Path, run_id: str = "run-orch-001") -> Path:
        """Write a minimal but valid package using new-schema–compliant artifacts."""
        package_dir = tmp_path / run_id / "meeting_minutes"
        package_dir.mkdir(parents=True, exist_ok=True)
        _write_json(package_dir / "structured_extraction.json", VALID_EXTRACTION)
        _write_json(package_dir / "signals.json", VALID_SIGNALS)
        _write_json(package_dir / "study_state.json", VALID_STUDY_STATE)
        _write_json(package_dir / "recommendations.json", {"recommendations": []})
        _write_json(package_dir / "execution_metadata.json", {"stub": True})
        # Real DOCX bytes to avoid stub warning.
        (package_dir / "meeting_minutes.docx").write_bytes(b"PK real docx")
        # Write a placeholder validation_report.json.
        _write_json(package_dir / "validation_report.json", {"stub": True})
        return package_dir

    def test_valid_package_returns_pass(self, tmp_path: Path) -> None:
        package_dir = self._build_package(tmp_path)
        result = validate_meeting_minutes_package(package_dir, write_report=False)
        assert result.status == STATUS_PASS
        assert result.findings == []

    def test_writes_validation_report(self, tmp_path: Path) -> None:
        package_dir = self._build_package(tmp_path)
        validate_meeting_minutes_package(package_dir, write_report=True)
        report_path = package_dir / "validation_report.json"
        assert report_path.exists()
        data = json.loads(report_path.read_text(encoding="utf-8"))
        assert "status" in data
        assert "findings" in data
        assert "summary" in data

    def test_validation_report_json_is_valid(self, tmp_path: Path) -> None:
        package_dir = self._build_package(tmp_path)
        result = validate_meeting_minutes_package(package_dir, write_report=True)
        report = json.loads((package_dir / "validation_report.json").read_text())
        assert report["status"] == result.status
        assert report["summary"]["errors"] == len(result.errors)

    def test_case_input_validated_when_supplied(self, tmp_path: Path) -> None:
        package_dir = self._build_package(tmp_path)
        bad_input = {**VALID_CASE_INPUT, "transcript": ""}
        result = validate_meeting_minutes_package(
            package_dir, case_input=bad_input, write_report=False
        )
        assert result.status == STATUS_FAIL
        assert any(f.category == CATEGORY_INPUT_ERROR for f in result.findings)

    def test_missing_file_causes_fail(self, tmp_path: Path) -> None:
        package_dir = self._build_package(tmp_path, run_id="run-miss-001")
        (package_dir / "signals.json").unlink()
        result = validate_meeting_minutes_package(package_dir, write_report=False)
        assert result.status == STATUS_FAIL
        assert any(f.category == CATEGORY_PACKAGING_ERROR for f in result.findings)

    def test_run_id_derived_from_parent_dir(self, tmp_path: Path) -> None:
        package_dir = self._build_package(tmp_path, run_id="run-derived-42")
        result = validate_meeting_minutes_package(package_dir, write_report=False)
        assert result.run_id == "run-derived-42"

    def test_explicit_run_id_used(self, tmp_path: Path) -> None:
        package_dir = self._build_package(tmp_path)
        result = validate_meeting_minutes_package(
            package_dir, run_id="run-explicit-99", write_report=False
        )
        assert result.run_id == "run-explicit-99"

    def test_validated_at_is_present(self, tmp_path: Path) -> None:
        package_dir = self._build_package(tmp_path)
        result = validate_meeting_minutes_package(package_dir, write_report=False)
        assert result.validated_at != ""

    def test_corrupt_json_produces_validation_error(self, tmp_path: Path) -> None:
        package_dir = self._build_package(tmp_path, run_id="run-corrupt-001")
        (package_dir / "signals.json").write_text("{invalid json", encoding="utf-8")
        result = validate_meeting_minutes_package(package_dir, write_report=False)
        assert result.status == STATUS_FAIL
        assert any(f.category == CATEGORY_VALIDATION_ERROR for f in result.findings)

    def test_stub_docx_triggers_warning(self, tmp_path: Path) -> None:
        package_dir = self._build_package(tmp_path, run_id="run-stub-docx")
        # Replace real DOCX with a stub marker.
        stub = json.dumps({"stub": True, "run_id": "run-stub-docx"}, indent=2)
        (package_dir / "meeting_minutes.docx").write_bytes(stub.encode("utf-8"))
        result = validate_meeting_minutes_package(package_dir, write_report=False)
        assert any(f.severity == SEV_WARNING for f in result.findings)
        assert result.status in (STATUS_PASS_WITH_WARNINGS, STATUS_PASS)

    def test_new_schema_signals_validated(self, tmp_path: Path) -> None:
        """New-schema signals (questions/assumptions/risks) validate cleanly."""
        package_dir = self._build_package(tmp_path, run_id="run-new-sig")
        _write_json(package_dir / "signals.json", VALID_SIGNALS)
        result = validate_meeting_minutes_package(package_dir, write_report=False)
        # Should pass (or warn on propagation drift from old study_state); no errors.
        assert result.status != STATUS_FAIL or not any(
            f.category == CATEGORY_SIGNAL_ERROR for f in result.errors
        )

    def test_full_valid_pipeline_integration(self, tmp_path: Path) -> None:
        """End-to-end: package_artifacts → overwrite with new-schema data → validate."""
        from spectrum_systems.modules.artifact_packager import package_artifacts
        pkg_result = package_artifacts(
            run_id="run-e2e-001",
            structured_extraction=OLD_STYLE_EXTRACTION,
            signals=OLD_STYLE_SIGNALS,
            artifacts_root=tmp_path,
            docx_bytes=b"PK real docx",
        )
        package_dir = Path(pkg_result["package_dir"])
        # Overwrite with new-schema–compliant data so the validator passes.
        _write_json(package_dir / "structured_extraction.json", VALID_EXTRACTION)
        _write_json(package_dir / "signals.json", VALID_SIGNALS)
        _write_json(package_dir / "study_state.json", VALID_STUDY_STATE)
        result = validate_meeting_minutes_package(package_dir, write_report=True)
        # Package is valid; only possible findings are propagation warnings.
        assert result.status in (STATUS_PASS, STATUS_PASS_WITH_WARNINGS)
        assert len(result.errors) == 0
