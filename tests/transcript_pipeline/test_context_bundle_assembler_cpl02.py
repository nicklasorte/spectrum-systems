"""
CPL-02 — Context Bundle Assembler tests.

Coverage:
  * Schema audit positive + negative (segments, source_turn_id, manifest_hash)
  * Deterministic 1:1 projection from speaker_turns
  * Replay determinism (manifest_hash, content_hash, ordering)
  * PQX harness integration (artifact registered, record emitted, trace propagated)
  * Referential integrity (orphan, duplicate, count mismatch)
  * Bad-input campaign (missing speaker_turns, corrupted turn_id, empty,
    mismatched source_artifact_id, drift)
  * Red-team regressions (fake/forged segments, reorder, partial coverage,
    duplicate segment ids).
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from spectrum_systems.modules.orchestration.pqx_step_harness import PQXExecutionError
from spectrum_systems.modules.runtime.artifact_store import (
    ArtifactStore,
    compute_content_hash,
)
from spectrum_systems.modules.transcript_pipeline.context_bundle_assembler import (
    ARTIFACT_TYPE,
    ASSEMBLY_STRATEGY,
    PRODUCED_BY,
    SCHEMA_REF,
    SCHEMA_VERSION,
    ContextBundleAssemblyError,
    assemble_context_bundle,
    assemble_context_bundle_via_pqx,
)
from spectrum_systems.modules.transcript_pipeline.transcript_ingestor import (
    ingest_transcript,
    ingest_transcript_via_pqx,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCHEMA_PATH = (
    Path(__file__).parent.parent.parent
    / "contracts"
    / "schemas"
    / "transcript_pipeline"
    / "context_bundle.schema.json"
)


def _load_schema() -> Dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_load_schema(), format_checker=FormatChecker())


def _frozen_clock() -> datetime:
    return datetime(2026, 4, 27, 0, 0, 0, tzinfo=timezone.utc)


def _build_transcript_payload() -> Dict[str, Any]:
    """Produce a deterministic transcript_artifact payload for assembler tests."""
    payload = ingest_transcript(
        str(FIXTURES_DIR / "valid_transcript.txt"),
        trace_id="a" * 32,
        span_id="b" * 16,
        run_id="run-cpl02-fixture",
    )
    payload["content_hash"] = compute_content_hash(payload)
    return payload


# ---------------------------------------------------------------------------
# CPL-02-1 — Schema audit
# ---------------------------------------------------------------------------


class TestSchemaAudit:
    def test_schema_declares_segments_and_manifest_hash(self) -> None:
        schema = _load_schema()
        props = schema["properties"]
        assert "segments" in props
        assert "manifest_hash" in props
        assert props["segments"]["minItems"] == 1
        assert "segment" in schema["$defs"]

    def test_schema_rejects_unknown_fields(self) -> None:
        schema = _load_schema()
        assert schema.get("additionalProperties") is False

    def test_segment_requires_source_turn_id(self) -> None:
        schema = _load_schema()
        required = schema["$defs"]["segment"]["required"]
        for field in ("segment_id", "speaker", "text", "source_turn_id", "line_index"):
            assert field in required

    def test_payload_validates(self) -> None:
        bundle = assemble_context_bundle(
            _build_transcript_payload(),
            trace_id="a" * 32,
            span_id="b" * 16,
            clock=_frozen_clock,
        )
        bundle["content_hash"] = compute_content_hash(bundle)
        errors = list(_validator().iter_errors(bundle))
        assert not errors, f"valid bundle failed schema: {[e.message for e in errors]}"

    def test_segment_with_unknown_field_rejected(self) -> None:
        bundle = assemble_context_bundle(
            _build_transcript_payload(),
            trace_id="a" * 32,
            span_id="b" * 16,
            clock=_frozen_clock,
        )
        bundle["segments"][0]["rogue"] = "no"
        bundle["content_hash"] = compute_content_hash(bundle)
        errors = list(_validator().iter_errors(bundle))
        assert errors, "schema must reject extra segment fields"


# ---------------------------------------------------------------------------
# CPL-02-2 — Pure projection
# ---------------------------------------------------------------------------


class TestProjection:
    def test_projection_is_one_to_one(self) -> None:
        transcript = _build_transcript_payload()
        bundle = assemble_context_bundle(
            transcript,
            trace_id="a" * 32,
            span_id="b" * 16,
            clock=_frozen_clock,
        )
        assert len(bundle["segments"]) == len(transcript["speaker_turns"])
        for seg, turn in zip(bundle["segments"], transcript["speaker_turns"]):
            assert seg["speaker"] == turn["speaker"]
            assert seg["text"] == turn["text"]
            assert seg["source_turn_id"] == turn["turn_id"]
            assert seg["line_index"] == turn["line_index"]

    def test_segment_ids_are_deterministic(self) -> None:
        bundle = assemble_context_bundle(
            _build_transcript_payload(),
            trace_id="a" * 32,
            span_id="b" * 16,
            clock=_frozen_clock,
        )
        for idx, seg in enumerate(bundle["segments"]):
            assert seg["segment_id"] == f"SEG-{idx + 1:04d}"

    def test_assembler_envelope_shape(self) -> None:
        bundle = assemble_context_bundle(
            _build_transcript_payload(),
            trace_id="a" * 32,
            span_id="b" * 16,
            clock=_frozen_clock,
        )
        assert bundle["artifact_type"] == ARTIFACT_TYPE
        assert bundle["schema_ref"] == SCHEMA_REF
        assert bundle["schema_version"] == SCHEMA_VERSION
        assert bundle["assembly_strategy"] == ASSEMBLY_STRATEGY
        assert bundle["provenance"]["produced_by"] == PRODUCED_BY
        assert bundle["provenance"]["input_artifact_ids"] == [bundle["source_artifact_id"]]
        assert bundle["source_artifact_id"].startswith("TXA-")
        assert bundle["artifact_id"].startswith("CTX-")
        assert "content_hash" not in bundle, "assembler must not compute content_hash"

    def test_assembler_does_not_mutate_input(self) -> None:
        transcript = _build_transcript_payload()
        snapshot = copy.deepcopy(transcript)
        assemble_context_bundle(
            transcript,
            trace_id="a" * 32,
            span_id="b" * 16,
            clock=_frozen_clock,
        )
        assert transcript == snapshot, "assembler must not mutate the source transcript"


# ---------------------------------------------------------------------------
# CPL-02-5 — Replay determinism
# ---------------------------------------------------------------------------


class TestReplayDeterminism:
    def test_same_input_yields_identical_segments_and_manifest(self) -> None:
        transcript = _build_transcript_payload()
        a = assemble_context_bundle(
            transcript, trace_id="a" * 32, span_id="b" * 16, clock=_frozen_clock
        )
        b = assemble_context_bundle(
            transcript, trace_id="c" * 32, span_id="d" * 16, clock=_frozen_clock
        )
        assert a["segments"] == b["segments"]
        assert a["manifest_hash"] == b["manifest_hash"]
        assert a["artifact_id"] == b["artifact_id"]

    def test_content_hash_is_replay_stable(self) -> None:
        transcript = _build_transcript_payload()
        a = assemble_context_bundle(
            transcript, trace_id="a" * 32, span_id="b" * 16, clock=_frozen_clock
        )
        b = assemble_context_bundle(
            transcript, trace_id="c" * 32, span_id="d" * 16, clock=_frozen_clock
        )
        assert compute_content_hash(a) == compute_content_hash(b)

    def test_reordering_segments_changes_manifest_hash(self) -> None:
        transcript = _build_transcript_payload()
        bundle = assemble_context_bundle(
            transcript, trace_id="a" * 32, span_id="b" * 16, clock=_frozen_clock
        )
        reordered = list(reversed(bundle["segments"]))
        # Force different ordering through the public hash function
        from spectrum_systems.modules.transcript_pipeline.context_bundle_assembler import (
            _compute_manifest_hash,
        )
        assert _compute_manifest_hash(reordered) != bundle["manifest_hash"]

    def test_manifest_hash_independent_of_envelope(self) -> None:
        """manifest_hash must not change when envelope (trace, time, run_id) changes."""
        transcript = _build_transcript_payload()
        a = assemble_context_bundle(
            transcript, trace_id="a" * 32, span_id="b" * 16, clock=_frozen_clock
        )
        b = assemble_context_bundle(
            transcript,
            trace_id="9" * 32,
            span_id="0" * 16,
            run_id="different-run",
            clock=lambda: datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        assert a["manifest_hash"] == b["manifest_hash"]


# ---------------------------------------------------------------------------
# CPL-02-3 — PQX integration
# ---------------------------------------------------------------------------


class TestPQXIntegration:
    def _ingested(self, store: ArtifactStore) -> Dict[str, Any]:
        result = ingest_transcript_via_pqx(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            store,
            run_id="run-cpl02-pqx",
        )
        return result["output_artifact"]

    def test_assembly_via_pqx_registers_artifact(self) -> None:
        store = ArtifactStore()
        transcript = self._ingested(store)
        result = assemble_context_bundle_via_pqx(
            transcript,
            store,
            run_id="run-cpl02-pqx",
        )
        bundle = result["output_artifact"]
        record = result["execution_record"]
        assert bundle["artifact_type"] == ARTIFACT_TYPE
        assert bundle["source_artifact_id"] == transcript["artifact_id"]
        assert bundle["provenance"]["input_artifact_ids"] == [transcript["artifact_id"]]
        assert "content_hash" in bundle and bundle["content_hash"].startswith("sha256:")
        assert store.artifact_exists(bundle["artifact_id"])
        assert record["status"] == "success"
        assert record["step_name"] == "context_bundle_assembly"
        assert record["output_artifact_id"] == bundle["artifact_id"]

    def test_assembly_via_pqx_inherits_parent_trace(self) -> None:
        store = ArtifactStore()
        transcript = self._ingested(store)
        parent = "f" * 32
        result = assemble_context_bundle_via_pqx(
            transcript, store, parent_trace_id=parent
        )
        assert result["output_artifact"]["trace"]["trace_id"] == parent

    def test_assembly_via_pqx_fails_closed_on_bad_input(self) -> None:
        store = ArtifactStore()
        bad_transcript = {"artifact_type": "transcript_artifact"}
        with pytest.raises(PQXExecutionError) as exc:
            assemble_context_bundle_via_pqx(bad_transcript, store)
        assert exc.value.execution_record["status"] == "failed"
        assert "EXECUTION_EXCEPTION" in exc.value.reason_codes

    def test_assembler_cannot_write_artifact_directly(self) -> None:
        """Module exposes no path to register without PQX."""
        from spectrum_systems.modules.transcript_pipeline import context_bundle_assembler as mod

        public = {name for name in mod.__all__}
        assert "register_artifact" not in public
        # The pure function does not return a content_hash, preventing direct registration.
        bundle = assemble_context_bundle(
            _build_transcript_payload(),
            trace_id="a" * 32,
            span_id="b" * 16,
            clock=_frozen_clock,
        )
        assert "content_hash" not in bundle


# ---------------------------------------------------------------------------
# CPL-02-4 — Referential integrity
# ---------------------------------------------------------------------------


class TestReferentialIntegrity:
    def test_missing_speaker_turns_fails(self) -> None:
        transcript = _build_transcript_payload()
        del transcript["speaker_turns"]
        with pytest.raises(ContextBundleAssemblyError) as exc:
            assemble_context_bundle(transcript, trace_id="a" * 32, span_id="b" * 16)
        assert exc.value.reason_code == "MISSING_SPEAKER_TURNS"

    def test_empty_speaker_turns_fails(self) -> None:
        transcript = _build_transcript_payload()
        transcript["speaker_turns"] = []
        with pytest.raises(ContextBundleAssemblyError) as exc:
            assemble_context_bundle(transcript, trace_id="a" * 32, span_id="b" * 16)
        assert exc.value.reason_code == "EMPTY_SPEAKER_TURNS"

    def test_corrupted_turn_id_fails(self) -> None:
        transcript = _build_transcript_payload()
        transcript["speaker_turns"][0]["turn_id"] = "not-a-turn"
        with pytest.raises(ContextBundleAssemblyError) as exc:
            assemble_context_bundle(transcript, trace_id="a" * 32, span_id="b" * 16)
        assert exc.value.reason_code == "INVALID_TURN_ID"

    def test_duplicate_turn_id_fails(self) -> None:
        transcript = _build_transcript_payload()
        transcript["speaker_turns"][1]["turn_id"] = transcript["speaker_turns"][0]["turn_id"]
        with pytest.raises(ContextBundleAssemblyError) as exc:
            assemble_context_bundle(transcript, trace_id="a" * 32, span_id="b" * 16)
        assert exc.value.reason_code == "DUPLICATE_TURN_ID"

    def test_invalid_artifact_type_fails(self) -> None:
        transcript = _build_transcript_payload()
        transcript["artifact_type"] = "not_a_transcript"
        with pytest.raises(ContextBundleAssemblyError) as exc:
            assemble_context_bundle(transcript, trace_id="a" * 32, span_id="b" * 16)
        assert exc.value.reason_code == "INVALID_SOURCE_ARTIFACT_TYPE"

    def test_invalid_source_artifact_id_fails(self) -> None:
        transcript = _build_transcript_payload()
        transcript["artifact_id"] = "BADID"
        with pytest.raises(ContextBundleAssemblyError) as exc:
            assemble_context_bundle(transcript, trace_id="a" * 32, span_id="b" * 16)
        assert exc.value.reason_code == "INVALID_SOURCE_ARTIFACT_ID"

    def test_non_int_line_index_fails(self) -> None:
        transcript = _build_transcript_payload()
        transcript["speaker_turns"][0]["line_index"] = "0"
        with pytest.raises(ContextBundleAssemblyError) as exc:
            assemble_context_bundle(transcript, trace_id="a" * 32, span_id="b" * 16)
        assert exc.value.reason_code == "INVALID_TURN_LINE_INDEX"

    def test_negative_line_index_fails(self) -> None:
        transcript = _build_transcript_payload()
        transcript["speaker_turns"][0]["line_index"] = -1
        with pytest.raises(ContextBundleAssemblyError) as exc:
            assemble_context_bundle(transcript, trace_id="a" * 32, span_id="b" * 16)
        assert exc.value.reason_code == "INVALID_TURN_LINE_INDEX"

    def test_empty_turn_text_fails(self) -> None:
        transcript = _build_transcript_payload()
        transcript["speaker_turns"][2]["text"] = "   "
        with pytest.raises(ContextBundleAssemblyError) as exc:
            assemble_context_bundle(transcript, trace_id="a" * 32, span_id="b" * 16)
        assert exc.value.reason_code == "INVALID_TURN_TEXT"

    def test_empty_turn_speaker_fails(self) -> None:
        transcript = _build_transcript_payload()
        transcript["speaker_turns"][1]["speaker"] = ""
        with pytest.raises(ContextBundleAssemblyError) as exc:
            assemble_context_bundle(transcript, trace_id="a" * 32, span_id="b" * 16)
        assert exc.value.reason_code == "INVALID_TURN_SPEAKER"

    def test_non_mapping_input_fails(self) -> None:
        with pytest.raises(ContextBundleAssemblyError) as exc:
            assemble_context_bundle("not a dict", trace_id="a" * 32, span_id="b" * 16)  # type: ignore[arg-type]
        assert exc.value.reason_code == "INVALID_INPUT_TYPE"

    def test_invalid_trace_id_fails(self) -> None:
        with pytest.raises(ContextBundleAssemblyError) as exc:
            assemble_context_bundle(
                _build_transcript_payload(), trace_id="too-short", span_id="b" * 16
            )
        assert exc.value.reason_code == "INVALID_TRACE_ID"

    def test_invalid_span_id_fails(self) -> None:
        with pytest.raises(ContextBundleAssemblyError) as exc:
            assemble_context_bundle(
                _build_transcript_payload(), trace_id="a" * 32, span_id="zzz"
            )
        assert exc.value.reason_code == "INVALID_SPAN_ID"


# ---------------------------------------------------------------------------
# CPL-02-7 — Red-team regressions
# ---------------------------------------------------------------------------


class TestRedTeamRegressions:
    """Each test corresponds to a finding in the CPL-02 red-team review."""

    def test_orphan_segment_blocked_by_referential_integrity_helper(self) -> None:
        """If a downstream caller forges a segment with a missing turn, integrity rejects it."""
        from spectrum_systems.modules.transcript_pipeline.context_bundle_assembler import (
            _validate_referential_integrity,
        )
        forged = [
            {
                "segment_id": "SEG-0001",
                "speaker": "Mallory",
                "text": "I was never in the transcript.",
                "source_turn_id": "T-9999",
                "line_index": 0,
            }
        ]
        turns = [
            {"turn_id": "T-0001", "speaker": "Alice", "text": "Hi", "line_index": 0}
        ]
        with pytest.raises(ContextBundleAssemblyError) as exc:
            _validate_referential_integrity(forged, turns, source_artifact_id="TXA-X")
        assert exc.value.reason_code in {"ORPHAN_SEGMENT", "SEGMENT_TURN_DRIFT"}

    def test_segment_drift_detected(self) -> None:
        """If segment[i] points at the right turn but text is changed, drift is caught."""
        from spectrum_systems.modules.transcript_pipeline.context_bundle_assembler import (
            _validate_referential_integrity,
        )
        turns = [
            {"turn_id": "T-0001", "speaker": "Alice", "text": "Hi", "line_index": 0}
        ]
        drifted = [
            {
                "segment_id": "SEG-0001",
                "speaker": "Alice",
                "text": "TAMPERED",
                "source_turn_id": "T-0001",
                "line_index": 0,
            }
        ]
        with pytest.raises(ContextBundleAssemblyError) as exc:
            _validate_referential_integrity(drifted, turns, source_artifact_id="TXA-X")
        assert exc.value.reason_code == "SEGMENT_TURN_DRIFT"

    def test_count_mismatch_detected(self) -> None:
        """Partial transcript coverage (segments < turns) is rejected."""
        from spectrum_systems.modules.transcript_pipeline.context_bundle_assembler import (
            _validate_referential_integrity,
        )
        turns = [
            {"turn_id": "T-0001", "speaker": "Alice", "text": "Hi", "line_index": 0},
            {"turn_id": "T-0002", "speaker": "Bob", "text": "Hello", "line_index": 1},
        ]
        partial = [
            {
                "segment_id": "SEG-0001",
                "speaker": "Alice",
                "text": "Hi",
                "source_turn_id": "T-0001",
                "line_index": 0,
            }
        ]
        with pytest.raises(ContextBundleAssemblyError) as exc:
            _validate_referential_integrity(partial, turns, source_artifact_id="TXA-X")
        assert exc.value.reason_code == "SEGMENT_TURN_COUNT_MISMATCH"

    def test_duplicate_segment_id_detected(self) -> None:
        from spectrum_systems.modules.transcript_pipeline.context_bundle_assembler import (
            _validate_referential_integrity,
        )
        turns = [
            {"turn_id": "T-0001", "speaker": "Alice", "text": "Hi", "line_index": 0},
            {"turn_id": "T-0002", "speaker": "Bob", "text": "Hello", "line_index": 1},
        ]
        forged = [
            {
                "segment_id": "SEG-0001",
                "speaker": "Alice",
                "text": "Hi",
                "source_turn_id": "T-0001",
                "line_index": 0,
            },
            {
                "segment_id": "SEG-0001",  # duplicate
                "speaker": "Bob",
                "text": "Hello",
                "source_turn_id": "T-0002",
                "line_index": 1,
            },
        ]
        with pytest.raises(ContextBundleAssemblyError) as exc:
            _validate_referential_integrity(forged, turns, source_artifact_id="TXA-X")
        assert exc.value.reason_code == "DUPLICATE_SEGMENT_ID"

    def test_artifact_id_changes_when_content_changes(self) -> None:
        """A different transcript content => different manifest_hash => different artifact_id."""
        transcript_a = _build_transcript_payload()
        transcript_b = copy.deepcopy(transcript_a)
        transcript_b["speaker_turns"][0]["text"] = transcript_b["speaker_turns"][0]["text"] + " (edited)"

        bundle_a = assemble_context_bundle(
            transcript_a, trace_id="a" * 32, span_id="b" * 16, clock=_frozen_clock
        )
        bundle_b = assemble_context_bundle(
            transcript_b, trace_id="a" * 32, span_id="b" * 16, clock=_frozen_clock
        )
        assert bundle_a["manifest_hash"] != bundle_b["manifest_hash"]
        assert bundle_a["artifact_id"] != bundle_b["artifact_id"]


# ---------------------------------------------------------------------------
# CPL-02 — Authority-shape vocabulary regression
# ---------------------------------------------------------------------------


_FORBIDDEN_AUTHORITY_TERMS = (
    "enforce",
    "enforced",
    "enforcement",
    "decision",
    "decisions",
    "decided",
    "verdict",
    "adjudication",
    "promotion",
    "promoted",
    "promote",
    "certification",
    "certified",
    "certify",
    "approval",
    "approved",
    "approve",
)


def _scan_for_authority_terms(text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in _FORBIDDEN_AUTHORITY_TERMS if term in lowered]


class TestAuthorityShapeVocabulary:
    """CPL-02 artifacts and module symbols must avoid authority-cluster vocabulary."""

    REPO_ROOT = Path(__file__).parent.parent.parent

    def _load(self, rel_path: str) -> str:
        return (self.REPO_ROOT / rel_path).read_text(encoding="utf-8")

    def test_assembler_module_has_no_enforce_vocabulary(self) -> None:
        text = self._load(
            "spectrum_systems/modules/transcript_pipeline/context_bundle_assembler.py"
        )
        hits = _scan_for_authority_terms(text)
        assert not hits, f"assembler must avoid authority vocabulary, found: {hits}"

    def test_assembler_helper_uses_validate_prefix(self) -> None:
        from spectrum_systems.modules.transcript_pipeline import context_bundle_assembler as mod

        symbol_names = [name for name in dir(mod) if not name.startswith("__")]
        for name in symbol_names:
            assert not name.lower().startswith("enforce"), (
                f"helper {name!r} must use validate/check/guard vocabulary, not enforce"
            )
        assert hasattr(mod, "_validate_referential_integrity")

    def test_review_artifact_has_no_authority_vocabulary(self) -> None:
        text = self._load("contracts/review_artifact/CPL-02_review.json")
        hits = _scan_for_authority_terms(text)
        assert not hits, f"CPL-02_review.json must avoid authority vocabulary, found: {hits}"

    def test_fix_actions_artifact_has_no_authority_vocabulary(self) -> None:
        text = self._load("contracts/review_actions/CPL-02_fix_actions.json")
        hits = _scan_for_authority_terms(text)
        assert not hits, f"CPL-02_fix_actions.json must avoid authority vocabulary, found: {hits}"

    def test_review_doc_has_no_authority_vocabulary(self) -> None:
        text = self._load("docs/reviews/CPL-02_context_bundle_review.md")
        hits = _scan_for_authority_terms(text)
        assert not hits, f"CPL-02 review doc must avoid authority vocabulary, found: {hits}"

    def test_fix_plan_doc_has_no_authority_vocabulary(self) -> None:
        text = self._load("docs/review-actions/CPL-02_fix_plan.md")
        hits = _scan_for_authority_terms(text)
        assert not hits, f"CPL-02 fix plan must avoid authority vocabulary, found: {hits}"
