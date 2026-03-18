"""
Tests for the Human Feedback Capture System (Prompt AO).

Covers:
- Schema validation: valid and invalid feedback records
- HumanFeedbackRecord: from_dict / to_dict round-trip
- HumanFeedbackRecord: edited_text required for edit/rewrite actions
- FeedbackStore: save, load, list, link_to_artifact
- FeedbackStore: duplicate save raises FileExistsError
- FeedbackStore: load non-existent raises FileNotFoundError
- FeedbackStore: list_feedback with filters
- create_feedback_from_review: happy path
- create_feedback_from_review: validation failure raises ValueError
- validate_feedback: returns errors for invalid records
- attach_feedback_to_artifact: idempotent linking
- extract_claims: plain string
- extract_claims: structured dict with sections
- extract_claims: structured dict with claims list
- extract_claims: bullet point splitting
- extract_claims: structured dict with decisions list
- ReviewSession: start_session populates claims
- ReviewSession: iterate_claims yields all claims
- ReviewSession: record_feedback creates valid record
- ReviewSession: record_feedback unknown claim raises ValueError
- ReviewSession: close_session returns correct summary
- ReviewSession: start_session twice raises RuntimeError
- map_feedback_to_error_type: explicit failure_type mapping
- map_feedback_to_error_type: unclear falls back to action
- EvalRunner.apply_feedback_overrides: populates overrides field
- EvalRunner.apply_feedback_overrides: original result unchanged
- EvalRunner.apply_feedback_overrides: human_disagrees_with_system flag
"""
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime, timezone

import pytest

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------

from spectrum_systems.modules.feedback.human_feedback import (
    HumanFeedbackRecord,
    FeedbackStore,
)
from spectrum_systems.modules.feedback.feedback_ingest import (
    create_feedback_from_review,
    validate_feedback,
    attach_feedback_to_artifact,
)
from spectrum_systems.modules.feedback.claim_extraction import (
    ClaimUnit,
    extract_claims,
)
from spectrum_systems.modules.feedback.review_session import ReviewSession
from spectrum_systems.modules.feedback.feedback_mapping import map_feedback_to_error_type
from spectrum_systems.modules.evaluation.error_taxonomy import ErrorType
from spectrum_systems.modules.evaluation.eval_runner import (
    EvalResult,
    EvalRunner,
    LatencySummary,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _make_valid_record(**overrides) -> HumanFeedbackRecord:
    """Return a minimal valid HumanFeedbackRecord."""
    defaults = dict(
        artifact_id="artifact-001",
        artifact_type="working_paper",
        target_level="claim",
        target_id="claim-abc",
        reviewer_id="reviewer-1",
        reviewer_role="engineer",
        action="accept",
        original_text="The system operates at 5 GHz.",
        rationale="Matches transcript verbatim.",
        source_of_truth="transcript",
        failure_type="unclear",
        severity="low",
        golden_dataset=False,
        prompts=False,
        retrieval_memory=False,
    )
    defaults.update(overrides)
    return HumanFeedbackRecord(**defaults)


def _store_in_tmpdir() -> FeedbackStore:
    """Return a FeedbackStore backed by a temp directory."""
    tmp = tempfile.mkdtemp()
    return FeedbackStore(store_dir=Path(tmp))


def _minimal_eval_result() -> EvalResult:
    """Return a minimal valid EvalResult for testing."""
    return EvalResult(
        case_id="case-001",
        pass_fail=True,
        structural_score=0.9,
        semantic_score=0.85,
        grounding_score=1.0,
        latency_summary=LatencySummary(total_latency_ms=500),
    )


# ---------------------------------------------------------------------------
# HumanFeedbackRecord: schema validation
# ---------------------------------------------------------------------------


class TestHumanFeedbackRecordValidation:
    def test_valid_record_has_no_errors(self):
        record = _make_valid_record()
        errors = record.validate_against_schema()
        assert errors == []

    def test_missing_artifact_id(self):
        record = _make_valid_record(artifact_id="")
        errors = record.validate_against_schema()
        assert any("artifact_id" in e for e in errors)

    def test_invalid_artifact_type(self):
        record = _make_valid_record(artifact_type="not_a_type")
        errors = record.validate_against_schema()
        assert any("artifact_type" in e for e in errors)

    def test_invalid_target_level(self):
        record = _make_valid_record(target_level="paragraph")
        errors = record.validate_against_schema()
        assert any("target_level" in e for e in errors)

    def test_invalid_reviewer_role(self):
        record = _make_valid_record(reviewer_role="intern")
        errors = record.validate_against_schema()
        assert any("reviewer_role" in e for e in errors)

    def test_invalid_action(self):
        record = _make_valid_record(action="ignore")
        errors = record.validate_against_schema()
        assert any("action" in e for e in errors)

    def test_invalid_failure_type(self):
        record = _make_valid_record(failure_type="bad_type")
        errors = record.validate_against_schema()
        assert any("failure_type" in e for e in errors)

    def test_invalid_severity(self):
        record = _make_valid_record(severity="fatal")
        errors = record.validate_against_schema()
        assert any("severity" in e for e in errors)

    def test_edit_action_requires_edited_text(self):
        for action in ("minor_edit", "major_edit", "rewrite"):
            record = _make_valid_record(action=action, edited_text=None)
            errors = record.validate_against_schema()
            assert any("edited_text" in e for e in errors), f"Expected edited_text error for {action}"

    def test_edit_action_with_edited_text_is_valid(self):
        record = _make_valid_record(action="minor_edit", edited_text="Corrected text here.")
        errors = record.validate_against_schema()
        assert errors == []

    def test_accept_without_edited_text_is_valid(self):
        record = _make_valid_record(action="accept", edited_text=None)
        errors = record.validate_against_schema()
        assert errors == []

    def test_missing_rationale(self):
        record = _make_valid_record(rationale="")
        errors = record.validate_against_schema()
        assert any("rationale" in e for e in errors)

    def test_invalid_source_of_truth(self):
        record = _make_valid_record(source_of_truth="internet")
        errors = record.validate_against_schema()
        assert any("source_of_truth" in e for e in errors)

    def test_should_update_must_be_booleans(self):
        record = _make_valid_record()
        record.golden_dataset = "yes"  # type: ignore[assignment]
        errors = record.validate_against_schema()
        assert any("golden_dataset" in e for e in errors)


# ---------------------------------------------------------------------------
# HumanFeedbackRecord: serialisation round-trip
# ---------------------------------------------------------------------------


class TestHumanFeedbackRecordSerialization:
    def test_to_dict_keys(self):
        record = _make_valid_record()
        d = record.to_dict()
        required_keys = {
            "feedback_id", "artifact_id", "artifact_type", "target_level",
            "target_id", "reviewer", "action", "original_text", "edited_text",
            "rationale", "source_of_truth", "failure_type", "severity",
            "should_update", "timestamp",
        }
        assert required_keys == set(d.keys())

    def test_reviewer_subdict(self):
        record = _make_valid_record()
        d = record.to_dict()
        assert d["reviewer"]["reviewer_id"] == record.reviewer_id
        assert d["reviewer"]["reviewer_role"] == record.reviewer_role

    def test_should_update_subdict(self):
        record = _make_valid_record(golden_dataset=True, prompts=False, retrieval_memory=True)
        d = record.to_dict()
        assert d["should_update"]["golden_dataset"] is True
        assert d["should_update"]["prompts"] is False
        assert d["should_update"]["retrieval_memory"] is True

    def test_from_dict_round_trip(self):
        record = _make_valid_record()
        d = record.to_dict()
        restored = HumanFeedbackRecord.from_dict(d)
        assert restored.feedback_id == record.feedback_id
        assert restored.artifact_id == record.artifact_id
        assert restored.action == record.action
        assert restored.reviewer_id == record.reviewer_id
        assert restored.reviewer_role == record.reviewer_role
        assert restored.golden_dataset == record.golden_dataset

    def test_from_dict_preserves_edited_text(self):
        record = _make_valid_record(action="minor_edit", edited_text="Fixed text.")
        d = record.to_dict()
        restored = HumanFeedbackRecord.from_dict(d)
        assert restored.edited_text == "Fixed text."

    def test_feedback_id_auto_generated(self):
        record = _make_valid_record()
        assert record.feedback_id  # not empty
        # Should look like a UUID
        assert len(record.feedback_id) == 36

    def test_timestamp_auto_generated(self):
        record = _make_valid_record()
        # Should be parseable as ISO-8601
        datetime.fromisoformat(record.timestamp)


# ---------------------------------------------------------------------------
# FeedbackStore
# ---------------------------------------------------------------------------


class TestFeedbackStore:
    def test_save_and_load_round_trip(self):
        store = _store_in_tmpdir()
        record = _make_valid_record()
        store.save_feedback(record)
        loaded = store.load_feedback(record.feedback_id)
        assert loaded.feedback_id == record.feedback_id
        assert loaded.action == record.action

    def test_save_invalid_record_raises(self):
        store = _store_in_tmpdir()
        record = _make_valid_record(artifact_type="bad_type")
        with pytest.raises(ValueError, match="validation"):
            store.save_feedback(record)

    def test_save_duplicate_raises(self):
        store = _store_in_tmpdir()
        record = _make_valid_record()
        store.save_feedback(record)
        with pytest.raises(FileExistsError):
            store.save_feedback(record)

    def test_load_nonexistent_raises(self):
        store = _store_in_tmpdir()
        with pytest.raises(FileNotFoundError):
            store.load_feedback("does-not-exist")

    def test_list_feedback_empty(self):
        store = _store_in_tmpdir()
        assert store.list_feedback() == []

    def test_list_feedback_returns_all(self):
        store = _store_in_tmpdir()
        r1 = _make_valid_record(artifact_id="art-1")
        r2 = _make_valid_record(artifact_id="art-2")
        store.save_feedback(r1)
        store.save_feedback(r2)
        records = store.list_feedback()
        assert len(records) == 2

    def test_list_feedback_filter_by_artifact_id(self):
        store = _store_in_tmpdir()
        r1 = _make_valid_record(artifact_id="art-1")
        r2 = _make_valid_record(artifact_id="art-2")
        store.save_feedback(r1)
        store.save_feedback(r2)
        results = store.list_feedback(filters={"artifact_id": "art-1"})
        assert len(results) == 1
        assert results[0].artifact_id == "art-1"

    def test_list_feedback_filter_by_severity(self):
        store = _store_in_tmpdir()
        r1 = _make_valid_record(severity="high")
        r2 = _make_valid_record(severity="low")
        store.save_feedback(r1)
        store.save_feedback(r2)
        results = store.list_feedback(filters={"severity": "high"})
        assert len(results) == 1
        assert results[0].severity == "high"

    def test_link_to_artifact_returns_feedback_ids(self):
        store = _store_in_tmpdir()
        r1 = _make_valid_record(artifact_id="art-x")
        store.save_feedback(r1)
        linked = store.link_to_artifact("art-x")
        assert r1.feedback_id in linked

    def test_link_to_artifact_no_feedback(self):
        store = _store_in_tmpdir()
        assert store.link_to_artifact("no-such-artifact") == []


# ---------------------------------------------------------------------------
# feedback_ingest
# ---------------------------------------------------------------------------


class TestFeedbackIngest:
    def _artifact(self) -> Dict[str, Any]:
        return {"artifact_id": "wp-001", "artifact_type": "working_paper"}

    def _reviewer_input(self, **overrides) -> Dict[str, Any]:
        base: Dict[str, Any] = {
            "reviewer_id": "user-1",
            "reviewer_role": "engineer",
            "target_level": "claim",
            "target_id": "claim-1",
            "action": "accept",
            "original_text": "The link budget is 3 dB.",
            "rationale": "Confirmed in transcript.",
            "source_of_truth": "transcript",
            "failure_type": "unclear",
            "severity": "low",
            "should_update": {"golden_dataset": False, "prompts": False, "retrieval_memory": False},
        }
        base.update(overrides)
        return base

    def test_create_feedback_happy_path(self):
        store = _store_in_tmpdir()
        record = create_feedback_from_review(
            artifact=self._artifact(),
            reviewer_input=self._reviewer_input(),
            store=store,
        )
        assert record.feedback_id
        assert record.artifact_id == "wp-001"

    def test_create_feedback_persisted(self):
        store = _store_in_tmpdir()
        record = create_feedback_from_review(
            artifact=self._artifact(),
            reviewer_input=self._reviewer_input(),
            store=store,
        )
        loaded = store.load_feedback(record.feedback_id)
        assert loaded.feedback_id == record.feedback_id

    def test_create_feedback_validation_failure_raises(self):
        store = _store_in_tmpdir()
        inp = self._reviewer_input(artifact_type="bad_type")
        with pytest.raises((ValueError, KeyError)):
            create_feedback_from_review(
                artifact={"artifact_id": "x", "artifact_type": "bad_type"},
                reviewer_input=inp,
                store=store,
            )

    def test_validate_feedback_valid(self):
        record = _make_valid_record()
        errors = validate_feedback(record)
        assert errors == []

    def test_validate_feedback_invalid(self):
        record = _make_valid_record(severity="extreme")
        errors = validate_feedback(record)
        assert len(errors) > 0

    def test_attach_feedback_to_artifact(self):
        store = _store_in_tmpdir()
        record = _make_valid_record(artifact_id="art-99")
        store.save_feedback(record)
        attach_feedback_to_artifact("art-99", record.feedback_id, store=store)
        linked = store.link_to_artifact("art-99")
        assert record.feedback_id in linked

    def test_attach_feedback_nonexistent_record_raises(self):
        store = _store_in_tmpdir()
        with pytest.raises(FileNotFoundError):
            attach_feedback_to_artifact("art-99", "fake-id", store=store)


# ---------------------------------------------------------------------------
# claim_extraction
# ---------------------------------------------------------------------------


class TestClaimExtraction:
    def test_plain_string_single_sentence(self):
        claims = extract_claims("The system operates at 5 GHz.")
        assert len(claims) == 1
        assert claims[0].claim_text == "The system operates at 5 GHz."
        assert claims[0].section_id == "root"

    def test_plain_string_multiple_sentences(self):
        text = "First claim. Second claim. Third claim."
        claims = extract_claims(text)
        assert len(claims) == 3

    def test_plain_string_bullet_points(self):
        text = "- Item one\n- Item two\n- Item three"
        claims = extract_claims(text)
        assert len(claims) == 3
        assert claims[0].claim_text == "Item one"

    def test_numbered_list(self):
        text = "1. First item\n2. Second item"
        claims = extract_claims(text)
        assert len(claims) == 2

    def test_structured_dict_sections(self):
        doc = {
            "sections": [
                {"section_id": "sec-1", "text": "Claim A. Claim B."},
                {"section_id": "sec-2", "text": "Claim C."},
            ]
        }
        claims = extract_claims(doc)
        assert len(claims) == 3
        sec_ids = {c.section_id for c in claims}
        assert "sec-1" in sec_ids
        assert "sec-2" in sec_ids

    def test_structured_dict_claims_list(self):
        doc = {
            "claims": [
                "The antenna gain is 12 dBi.",
                "The noise figure is 3 dB.",
            ]
        }
        claims = extract_claims(doc)
        assert len(claims) == 2
        assert claims[0].section_id == "root"

    def test_structured_dict_decisions_list(self):
        doc = {
            "decisions": [
                {"text": "Proceed with 5G deployment."},
                {"text": "Defer spectrum auction."},
            ]
        }
        claims = extract_claims(doc)
        assert len(claims) == 2
        assert claims[0].section_id == "decisions"

    def test_claim_unit_has_unique_ids(self):
        claims = extract_claims("First. Second. Third.")
        ids = [c.claim_id for c in claims]
        assert len(ids) == len(set(ids))

    def test_claim_unit_to_dict(self):
        claim = ClaimUnit(
            claim_id="c1",
            claim_text="Test text.",
            section_id="sec-1",
            source_index=0,
        )
        d = claim.to_dict()
        assert d["claim_id"] == "c1"
        assert d["claim_text"] == "Test text."
        assert d["section_id"] == "sec-1"
        assert d["source_index"] == 0

    def test_empty_string_returns_no_claims(self):
        claims = extract_claims("")
        assert claims == []

    def test_empty_dict_returns_no_claims(self):
        claims = extract_claims({})
        assert claims == []

    def test_section_with_nested_claims(self):
        doc = {
            "sections": [
                {
                    "section_id": "s1",
                    "claims": ["Claim alpha.", "Claim beta."],
                }
            ]
        }
        claims = extract_claims(doc)
        assert len(claims) == 2
        assert all(c.section_id == "s1" for c in claims)


# ---------------------------------------------------------------------------
# ReviewSession
# ---------------------------------------------------------------------------


class TestReviewSession:
    def _session(self, store=None, artifact=None) -> ReviewSession:
        if artifact is None:
            artifact = "First claim. Second claim."
        return ReviewSession(
            artifact_id="art-session-001",
            reviewer_id="reviewer-42",
            reviewer_role="engineer",
            artifact=artifact,
            artifact_type="working_paper",
            store=store or _store_in_tmpdir(),
        )

    def _feedback(self, **overrides) -> Dict[str, Any]:
        base: Dict[str, Any] = {
            "action": "accept",
            "rationale": "OK.",
            "source_of_truth": "transcript",
            "failure_type": "unclear",
            "severity": "low",
            "should_update": {
                "golden_dataset": False,
                "prompts": False,
                "retrieval_memory": False,
            },
        }
        base.update(overrides)
        return base

    def test_start_session_extracts_claims(self):
        session = self._session()
        session.start_session()
        assert len(session.claims) >= 1

    def test_iterate_claims_yields_claim_units(self):
        session = self._session()
        session.start_session()
        claims = list(session.iterate_claims())
        assert all(isinstance(c, ClaimUnit) for c in claims)

    def test_record_feedback_creates_record(self):
        session = self._session()
        session.start_session()
        claim = session.claims[0]
        record = session.record_feedback(claim.claim_id, self._feedback())
        assert record.feedback_id
        assert record.target_id == claim.claim_id
        assert record.action == "accept"

    def test_record_feedback_unknown_claim_raises(self):
        session = self._session()
        session.start_session()
        with pytest.raises(ValueError, match="not found"):
            session.record_feedback("nonexistent-claim-id", self._feedback())

    def test_close_session_returns_summary(self):
        session = self._session()
        session.start_session()
        claim = session.claims[0]
        session.record_feedback(claim.claim_id, self._feedback())
        summary = session.close_session()
        assert summary["artifact_id"] == "art-session-001"
        assert summary["reviewed_claims"] == 1
        assert len(summary["feedback_ids"]) == 1

    def test_close_session_total_matches_claims(self):
        session = self._session()
        session.start_session()
        summary = session.close_session()
        assert summary["total_claims"] == len(session.claims)

    def test_start_session_twice_raises(self):
        session = self._session()
        session.start_session()
        with pytest.raises(RuntimeError, match="already active"):
            session.start_session()

    def test_record_feedback_before_start_raises(self):
        session = self._session()
        with pytest.raises(RuntimeError, match="not active"):
            session.record_feedback("any-id", self._feedback())

    def test_iterate_claims_before_start_raises(self):
        session = self._session()
        with pytest.raises(RuntimeError, match="not active"):
            list(session.iterate_claims())

    def test_close_before_start_raises(self):
        session = self._session()
        with pytest.raises(RuntimeError, match="not active"):
            session.close_session()

    def test_session_with_structured_artifact(self):
        artifact = {
            "sections": [
                {"section_id": "intro", "text": "The system runs at 5 GHz. It uses OFDM."},
            ]
        }
        session = self._session(artifact=artifact)
        session.start_session()
        assert len(session.claims) >= 2

    def test_session_is_not_active_after_close(self):
        session = self._session()
        session.start_session()
        session.close_session()
        assert not session.is_active

    def test_skipped_claims_counted_correctly(self):
        session = self._session(artifact="Claim one. Claim two. Claim three.")
        session.start_session()
        # Only record feedback for the first claim
        session.record_feedback(session.claims[0].claim_id, self._feedback())
        summary = session.close_session()
        assert summary["skipped_claims"] == summary["total_claims"] - 1


# ---------------------------------------------------------------------------
# feedback_mapping
# ---------------------------------------------------------------------------


class TestFeedbackMapping:
    def test_extraction_error_maps_correctly(self):
        record = _make_valid_record(failure_type="extraction_error")
        assert map_feedback_to_error_type(record) == ErrorType.extraction_error

    def test_reasoning_error_maps_correctly(self):
        record = _make_valid_record(failure_type="reasoning_error")
        assert map_feedback_to_error_type(record) == ErrorType.reasoning_error

    def test_grounding_failure_maps_correctly(self):
        record = _make_valid_record(failure_type="grounding_failure")
        assert map_feedback_to_error_type(record) == ErrorType.grounding_failure

    def test_hallucination_maps_correctly(self):
        record = _make_valid_record(failure_type="hallucination")
        assert map_feedback_to_error_type(record) == ErrorType.hallucination

    def test_schema_violation_maps_correctly(self):
        record = _make_valid_record(failure_type="schema_violation")
        assert map_feedback_to_error_type(record) == ErrorType.schema_violation

    def test_unclear_reject_falls_back_to_reasoning_error(self):
        record = _make_valid_record(failure_type="unclear", action="reject")
        assert map_feedback_to_error_type(record) == ErrorType.reasoning_error

    def test_unclear_rewrite_falls_back_to_reasoning_error(self):
        record = _make_valid_record(
            failure_type="unclear",
            action="rewrite",
            edited_text="Corrected text.",
        )
        assert map_feedback_to_error_type(record) == ErrorType.reasoning_error

    def test_unclear_needs_support_falls_back_to_grounding_failure(self):
        record = _make_valid_record(failure_type="unclear", action="needs_support")
        assert map_feedback_to_error_type(record) == ErrorType.grounding_failure

    def test_unclear_major_edit_falls_back_to_extraction_error(self):
        record = _make_valid_record(
            failure_type="unclear",
            action="major_edit",
            edited_text="New text.",
        )
        assert map_feedback_to_error_type(record) == ErrorType.extraction_error

    def test_return_type_is_error_type(self):
        record = _make_valid_record()
        result = map_feedback_to_error_type(record)
        assert isinstance(result, ErrorType)


# ---------------------------------------------------------------------------
# EvalRunner.apply_feedback_overrides
# ---------------------------------------------------------------------------


class TestApplyFeedbackOverrides:
    def _runner(self):
        class _StubEngine:
            def run(self, transcript, config):
                return {"pass_results": [], "intermediate_artifacts": {}}
        return EvalRunner(reasoning_engine=_StubEngine())

    def test_overrides_field_populated(self):
        runner = self._runner()
        result = _minimal_eval_result()
        feedback_records = [
            {
                "feedback_id": str(uuid.uuid4()),
                "target_id": "claim-1",
                "action": "reject",
                "failure_type": "reasoning_error",
                "severity": "high",
                "original_text": "The answer is 42.",
                "edited_text": None,
            }
        ]
        updated = runner.apply_feedback_overrides(result, feedback_records)
        assert len(updated.human_feedback_overrides) == 1
        assert updated.human_feedback_overrides[0]["target_id"] == "claim-1"

    def test_original_result_unchanged(self):
        runner = self._runner()
        result = _minimal_eval_result()
        runner.apply_feedback_overrides(result, [
            {
                "feedback_id": "f1",
                "target_id": "claim-1",
                "action": "reject",
                "failure_type": "reasoning_error",
                "severity": "high",
                "original_text": "X",
                "edited_text": None,
            }
        ])
        # Original should not be mutated
        assert result.human_feedback_overrides == []

    def test_human_disagrees_with_system_flag_for_reject(self):
        runner = self._runner()
        result = _minimal_eval_result()
        updated = runner.apply_feedback_overrides(result, [
            {
                "feedback_id": "f1",
                "target_id": "claim-1",
                "action": "reject",
                "failure_type": "reasoning_error",
                "severity": "high",
                "original_text": "X",
                "edited_text": None,
            }
        ])
        assert updated.human_feedback_overrides[0]["human_disagrees_with_system"] is True

    def test_human_disagrees_with_system_flag_for_accept(self):
        runner = self._runner()
        result = _minimal_eval_result()
        updated = runner.apply_feedback_overrides(result, [
            {
                "feedback_id": "f2",
                "target_id": "claim-2",
                "action": "accept",
                "failure_type": "unclear",
                "severity": "low",
                "original_text": "Y",
                "edited_text": None,
            }
        ])
        assert updated.human_feedback_overrides[0]["human_disagrees_with_system"] is False

    def test_empty_feedback_list_produces_empty_overrides(self):
        runner = self._runner()
        result = _minimal_eval_result()
        updated = runner.apply_feedback_overrides(result, [])
        assert updated.human_feedback_overrides == []

    def test_multiple_feedback_records(self):
        runner = self._runner()
        result = _minimal_eval_result()
        feedback_records = [
            {
                "feedback_id": str(uuid.uuid4()),
                "target_id": f"claim-{i}",
                "action": "accept",
                "failure_type": "unclear",
                "severity": "low",
                "original_text": f"Claim {i}",
                "edited_text": None,
            }
            for i in range(5)
        ]
        updated = runner.apply_feedback_overrides(result, feedback_records)
        assert len(updated.human_feedback_overrides) == 5

    def test_to_dict_includes_overrides(self):
        runner = self._runner()
        result = _minimal_eval_result()
        updated = runner.apply_feedback_overrides(result, [
            {
                "feedback_id": "f3",
                "target_id": "claim-3",
                "action": "minor_edit",
                "failure_type": "extraction_error",
                "severity": "medium",
                "original_text": "Z",
                "edited_text": "Fixed Z.",
            }
        ])
        d = updated.to_dict()
        assert "human_feedback_overrides" in d
        assert len(d["human_feedback_overrides"]) == 1
