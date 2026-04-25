"""
H01B Hardening Tests — Severity Integrity, Hash Canonicalization, Source Grounding

H01B-1: S4 severity must always be blocking
H01B-3: content_hash is deterministic and excludes trace/timestamp
H01B-5: issue source_segment_ids required; decisions require source_reference or rationale
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from spectrum_systems.modules.runtime.hash_utils import compute_content_hash

_SCHEMA_DIR = (
    Path(__file__).parent.parent.parent / "contracts" / "schemas" / "transcript_pipeline"
)


def _load_schema(name: str) -> Dict[str, Any]:
    path = _SCHEMA_DIR / f"{name}.schema.json"
    assert path.exists(), f"Schema missing: {path}"
    return json.loads(path.read_text())


def _validate(schema: Dict[str, Any], instance: Dict[str, Any]) -> None:
    v = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(v.iter_errors(instance))
    if errors:
        raise ValidationError("; ".join(e.message for e in errors[:3]))


def _trace() -> Dict[str, str]:
    return {"trace_id": "a" * 32, "span_id": "b" * 16}


def _provenance() -> Dict[str, Any]:
    return {"produced_by": "test", "input_artifact_ids": []}


# ---------------------------------------------------------------------------
# H01B-1: Severity integrity — S4 must be blocking
# ---------------------------------------------------------------------------

class TestS4SeverityIntegrity:
    """S4 findings must always set blocking=true. S4+blocking=false is a schema violation."""

    def _valid_review(self) -> Dict[str, Any]:
        return {
            "artifact_id": "RVA-H01B-TEST001",
            "artifact_type": "review_artifact",
            "schema_ref": "transcript_pipeline/review_artifact",
            "schema_version": "1.0.0",
            "content_hash": "sha256:" + "a" * 64,
            "trace": _trace(),
            "provenance": _provenance(),
            "created_at": "2026-04-25T00:00:00+00:00",
            "reviewed_artifact_id": "PDA-001",
            "reviewed_artifact_type": "paper_draft_artifact",
            "findings": [],
            "review_decision": "approve",
            "reviewer_id": "agent-test",
        }

    def test_s4_with_blocking_true_passes(self) -> None:
        schema = _load_schema("review_artifact")
        artifact = self._valid_review()
        artifact["findings"] = [
            {
                "finding_id": "F-001",
                "severity": "S4",
                "description": "Critical halt condition detected.",
                "blocking": True,
            }
        ]
        _validate(schema, artifact)

    def test_s4_with_blocking_false_fails(self) -> None:
        schema = _load_schema("review_artifact")
        artifact = self._valid_review()
        artifact["findings"] = [
            {
                "finding_id": "F-001",
                "severity": "S4",
                "description": "Severity ladder violation — marked non-blocking.",
                "blocking": False,
            }
        ]
        with pytest.raises(ValidationError):
            _validate(schema, artifact)

    def test_s4_without_blocking_field_fails(self) -> None:
        schema = _load_schema("review_artifact")
        artifact = self._valid_review()
        artifact["findings"] = [
            {
                "finding_id": "F-001",
                "severity": "S4",
                "description": "No blocking field provided.",
            }
        ]
        with pytest.raises(ValidationError):
            _validate(schema, artifact)

    def test_s3_without_blocking_is_valid(self) -> None:
        schema = _load_schema("review_artifact")
        artifact = self._valid_review()
        artifact["findings"] = [
            {
                "finding_id": "F-001",
                "severity": "S3",
                "description": "High severity, blocking field optional.",
            }
        ]
        _validate(schema, artifact)

    def test_s2_with_blocking_false_is_valid(self) -> None:
        schema = _load_schema("review_artifact")
        artifact = self._valid_review()
        artifact["findings"] = [
            {
                "finding_id": "F-001",
                "severity": "S2",
                "description": "Medium severity, blocking=false is permitted.",
                "blocking": False,
            }
        ]
        _validate(schema, artifact)

    def test_multiple_findings_any_s4_must_be_blocking(self) -> None:
        schema = _load_schema("review_artifact")
        artifact = self._valid_review()
        artifact["findings"] = [
            {"finding_id": "F-001", "severity": "S2", "description": "Minor issue.", "blocking": False},
            {"finding_id": "F-002", "severity": "S4", "description": "Halt condition.", "blocking": False},
        ]
        with pytest.raises(ValidationError):
            _validate(schema, artifact)


# ---------------------------------------------------------------------------
# H01B-3: Content hash canonicalization
# ---------------------------------------------------------------------------

class TestContentHashCanonicalization:
    """compute_content_hash must be deterministic, field-order-independent,
    and exclude content_hash / trace / created_at."""

    def _base_payload(self) -> Dict[str, Any]:
        return {
            "artifact_id": "TXA-HASHTEST001",
            "artifact_type": "transcript_artifact",
            "schema_ref": "transcript_pipeline/transcript_artifact",
            "schema_version": "1.0.0",
            "provenance": {"produced_by": "test", "input_artifact_ids": []},
            "source_format": "txt",
            "raw_text": "Hello world.",
        }

    def test_same_payload_produces_identical_hash(self) -> None:
        payload = self._base_payload()
        h1 = compute_content_hash(payload)
        h2 = compute_content_hash(payload)
        assert h1 == h2

    def test_reordered_json_produces_identical_hash(self) -> None:
        payload = self._base_payload()
        reordered = dict(reversed(list(payload.items())))
        assert compute_content_hash(payload) == compute_content_hash(reordered)

    def test_modified_payload_produces_different_hash(self) -> None:
        p1 = self._base_payload()
        p2 = {**p1, "raw_text": "Different content."}
        assert compute_content_hash(p1) != compute_content_hash(p2)

    def test_hash_excludes_content_hash_self_reference(self) -> None:
        payload = self._base_payload()
        h_without = compute_content_hash(payload)
        payload_with_hash = {**payload, "content_hash": "sha256:" + "0" * 64}
        h_with = compute_content_hash(payload_with_hash)
        assert h_without == h_with

    def test_hash_excludes_trace_metadata(self) -> None:
        payload = self._base_payload()
        h_without_trace = compute_content_hash(payload)
        payload_with_trace = {
            **payload,
            "trace": {"trace_id": "a" * 32, "span_id": "b" * 16},
        }
        h_with_trace = compute_content_hash(payload_with_trace)
        assert h_without_trace == h_with_trace

    def test_hash_excludes_created_at_timestamp(self) -> None:
        payload = self._base_payload()
        h_without_ts = compute_content_hash(payload)
        payload_ts1 = {**payload, "created_at": "2026-01-01T00:00:00+00:00"}
        payload_ts2 = {**payload, "created_at": "2026-04-25T12:34:56+00:00"}
        assert compute_content_hash(payload_ts1) == h_without_ts
        assert compute_content_hash(payload_ts2) == h_without_ts

    def test_hash_is_sha256_prefixed(self) -> None:
        h = compute_content_hash(self._base_payload())
        assert h.startswith("sha256:")
        assert len(h) == 71  # len("sha256:") + 64

    def test_different_trace_same_content_same_hash(self) -> None:
        payload = self._base_payload()
        p1 = {**payload, "trace": {"trace_id": "a" * 32, "span_id": "b" * 16}}
        p2 = {**payload, "trace": {"trace_id": "c" * 32, "span_id": "d" * 16}}
        assert compute_content_hash(p1) == compute_content_hash(p2)

    def test_different_created_at_same_content_same_hash(self) -> None:
        payload = self._base_payload()
        p1 = {**payload, "created_at": "2026-01-01T00:00:00+00:00"}
        p2 = {**payload, "created_at": "2099-12-31T23:59:59+00:00"}
        assert compute_content_hash(p1) == compute_content_hash(p2)


# ---------------------------------------------------------------------------
# H01B-5: Source grounding — issue_registry and meeting_minutes schemas
# ---------------------------------------------------------------------------

class TestIssueSourceGrounding:
    """Issues must include source_segment_ids (required, minItems 1)."""

    def _valid_issue_registry(self) -> Dict[str, Any]:
        return {
            "artifact_id": "IRA-SRCTEST001",
            "artifact_type": "issue_registry_artifact",
            "schema_ref": "transcript_pipeline/issue_registry_artifact",
            "schema_version": "1.0.0",
            "content_hash": "sha256:" + "a" * 64,
            "trace": _trace(),
            "provenance": _provenance(),
            "created_at": "2026-04-25T00:00:00+00:00",
            "source_artifact_id": "MMA-001",
            "issues": [
                {
                    "issue_id": "ISS-001",
                    "title": "Missing documentation",
                    "description": "No API docs found.",
                    "severity": "high",
                    "source_segment_ids": ["SEG-001"],
                }
            ],
        }

    def test_valid_issue_with_source_segment_ids_passes(self) -> None:
        schema = _load_schema("issue_registry_artifact")
        _validate(schema, self._valid_issue_registry())

    def test_issue_missing_source_segment_ids_fails(self) -> None:
        schema = _load_schema("issue_registry_artifact")
        artifact = self._valid_issue_registry()
        del artifact["issues"][0]["source_segment_ids"]
        with pytest.raises(ValidationError):
            _validate(schema, artifact)

    def test_issue_with_empty_source_segment_ids_fails(self) -> None:
        schema = _load_schema("issue_registry_artifact")
        artifact = self._valid_issue_registry()
        artifact["issues"][0]["source_segment_ids"] = []
        with pytest.raises(ValidationError):
            _validate(schema, artifact)

    def test_issue_with_multiple_source_segment_ids_passes(self) -> None:
        schema = _load_schema("issue_registry_artifact")
        artifact = self._valid_issue_registry()
        artifact["issues"][0]["source_segment_ids"] = ["SEG-001", "SEG-002", "SEG-003"]
        _validate(schema, artifact)

    def test_empty_issues_array_is_valid(self) -> None:
        schema = _load_schema("issue_registry_artifact")
        artifact = self._valid_issue_registry()
        artifact["issues"] = []
        _validate(schema, artifact)


class TestDecisionSourceGrounding:
    """Decisions must include source_reference OR rationale for traceability."""

    def _valid_minutes(self) -> Dict[str, Any]:
        return {
            "artifact_id": "MMA-SRCTEST001",
            "artifact_type": "meeting_minutes_artifact",
            "schema_ref": "transcript_pipeline/meeting_minutes_artifact",
            "schema_version": "1.0.0",
            "content_hash": "sha256:" + "a" * 64,
            "trace": _trace(),
            "provenance": _provenance(),
            "created_at": "2026-04-25T00:00:00+00:00",
            "source_artifact_id": "NTX-001",
            "summary": "Architecture review meeting.",
            "decisions": [],
            "action_items": [],
        }

    def test_decision_with_rationale_passes(self) -> None:
        schema = _load_schema("meeting_minutes_artifact")
        artifact = self._valid_minutes()
        artifact["decisions"] = [
            {
                "decision_id": "D-001",
                "description": "Adopt hash_utils canonical policy.",
                "rationale": "Ensures deterministic hashing across all pipeline stages.",
            }
        ]
        _validate(schema, artifact)

    def test_decision_with_source_reference_passes(self) -> None:
        schema = _load_schema("meeting_minutes_artifact")
        artifact = self._valid_minutes()
        artifact["decisions"] = [
            {
                "decision_id": "D-001",
                "description": "Adopt hash_utils canonical policy.",
                "source_reference": "TXA-001::segment::0012",
            }
        ]
        _validate(schema, artifact)

    def test_decision_with_both_rationale_and_source_passes(self) -> None:
        schema = _load_schema("meeting_minutes_artifact")
        artifact = self._valid_minutes()
        artifact["decisions"] = [
            {
                "decision_id": "D-001",
                "description": "Adopt canonical hashing.",
                "rationale": "Prevents replay attacks.",
                "source_reference": "TXA-001::segment::0012",
            }
        ]
        _validate(schema, artifact)

    def test_decision_missing_both_rationale_and_source_fails(self) -> None:
        schema = _load_schema("meeting_minutes_artifact")
        artifact = self._valid_minutes()
        artifact["decisions"] = [
            {
                "decision_id": "D-001",
                "description": "A decision without traceability origin.",
            }
        ]
        with pytest.raises(ValidationError):
            _validate(schema, artifact)

    def test_empty_decisions_array_is_valid(self) -> None:
        schema = _load_schema("meeting_minutes_artifact")
        artifact = self._valid_minutes()
        artifact["decisions"] = []
        _validate(schema, artifact)
