"""Tests for BN — Trace Persistence Layer (trace_store.py).

Covers:
 1.  persist_trace writes a valid envelope to disk
 2.  load_trace retrieves the exact trace that was persisted
 3.  list_traces returns correct trace IDs
 4.  delete_trace removes the file
 5.  persist_trace rejects a trace missing trace_id
 6.  persist_trace rejects a non-dict trace
 7.  load_trace raises TraceNotFoundError for unknown trace_id
 8.  delete_trace raises TraceNotFoundError for unknown trace_id
 9.  validate_persisted_trace returns empty list for valid envelope
10.  validate_persisted_trace returns errors for invalid envelope
11.  persist_trace is idempotent (overwriting same trace_id)
12.  list_traces returns empty list when directory does not exist
13.  envelope contains expected metadata fields
14.  atomic write prevents partial files on read
15.  list_traces is sorted
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.trace_store import (  # noqa: E402
    ENVELOPE_VERSION,
    TraceNotFoundError,
    TraceStoreError,
    delete_trace,
    list_traces,
    load_trace,
    persist_trace,
    validate_persisted_trace,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_store(tmp_path):
    """Return a temporary traces storage directory."""
    return tmp_path / "traces"


def _make_trace(trace_id: str = "test-trace-id-001") -> Dict[str, Any]:
    """Build a minimal valid trace dict."""
    return {
        "trace_id": trace_id,
        "root_span_id": None,
        "spans": [],
        "artifacts": [],
        "start_time": "2025-01-01T00:00:00+00:00",
        "end_time": None,
        "context": {},
        "schema_version": "1.0.0",
    }


def _make_trace_with_span(trace_id: str = "test-trace-with-span") -> Dict[str, Any]:
    """Build a trace with one closed span."""
    span_id = "span-001"
    return {
        "trace_id": trace_id,
        "root_span_id": span_id,
        "spans": [
            {
                "span_id": span_id,
                "trace_id": trace_id,
                "parent_span_id": None,
                "name": "root_op",
                "status": "ok",
                "start_time": "2025-01-01T00:00:00+00:00",
                "end_time": "2025-01-01T00:00:01+00:00",
                "events": [
                    {
                        "event_type": "test_event",
                        "timestamp": "2025-01-01T00:00:00+00:00",
                        "payload": {"key": "value"},
                    }
                ],
            }
        ],
        "artifacts": [
            {
                "artifact_id": "ART-001",
                "artifact_type": "test_artifact",
                "attached_at": "2025-01-01T00:00:01+00:00",
                "parent_span_id": span_id,
            }
        ],
        "start_time": "2025-01-01T00:00:00+00:00",
        "end_time": "2025-01-01T00:00:01+00:00",
        "context": {"run_id": "run-001"},
        "schema_version": "1.0.0",
    }


# ---------------------------------------------------------------------------
# Test 1: persist_trace writes a valid envelope to disk
# ---------------------------------------------------------------------------

class TestPersistTrace:
    def test_persist_trace_returns_storage_path(self, tmp_store):
        trace = _make_trace()
        storage_path = persist_trace(trace, base_dir=tmp_store)
        assert isinstance(storage_path, str)
        assert len(storage_path) > 0

    def test_persist_trace_creates_file(self, tmp_store):
        trace = _make_trace("trace-abc")
        persist_trace(trace, base_dir=tmp_store)
        expected = tmp_store / "trace-abc.json"
        assert expected.exists()

    def test_persist_trace_file_is_valid_json(self, tmp_store):
        trace = _make_trace("trace-json-001")
        persist_trace(trace, base_dir=tmp_store)
        raw = (tmp_store / "trace-json-001.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_persist_trace_preserves_trace_id(self, tmp_store):
        trace = _make_trace("trace-preserve-001")
        persist_trace(trace, base_dir=tmp_store)
        raw_data = json.loads((tmp_store / "trace-preserve-001.json").read_text("utf-8"))
        assert raw_data["trace"]["trace_id"] == "trace-preserve-001"

    def test_persist_trace_with_spans_and_artifacts(self, tmp_store):
        trace = _make_trace_with_span("trace-full-001")
        storage_path = persist_trace(trace, base_dir=tmp_store)
        assert (tmp_store / "trace-full-001.json").exists()


# ---------------------------------------------------------------------------
# Test 2: load_trace retrieves the exact trace that was persisted
# ---------------------------------------------------------------------------

class TestLoadTrace:
    def test_load_trace_returns_envelope(self, tmp_store):
        trace = _make_trace("trace-load-001")
        persist_trace(trace, base_dir=tmp_store)
        envelope = load_trace("trace-load-001", base_dir=tmp_store)
        assert isinstance(envelope, dict)
        assert envelope["trace"]["trace_id"] == "trace-load-001"

    def test_load_trace_round_trip_preserves_spans(self, tmp_store):
        trace = _make_trace_with_span("trace-roundtrip")
        persist_trace(trace, base_dir=tmp_store)
        envelope = load_trace("trace-roundtrip", base_dir=tmp_store)
        spans = envelope["trace"]["spans"]
        assert len(spans) == 1
        assert spans[0]["name"] == "root_op"
        assert spans[0]["status"] == "ok"

    def test_load_trace_round_trip_preserves_artifacts(self, tmp_store):
        trace = _make_trace_with_span("trace-artifacts-rt")
        persist_trace(trace, base_dir=tmp_store)
        envelope = load_trace("trace-artifacts-rt", base_dir=tmp_store)
        arts = envelope["trace"]["artifacts"]
        assert len(arts) == 1
        assert arts[0]["artifact_id"] == "ART-001"

    def test_load_trace_round_trip_preserves_context(self, tmp_store):
        trace = _make_trace_with_span("trace-context-rt")
        persist_trace(trace, base_dir=tmp_store)
        envelope = load_trace("trace-context-rt", base_dir=tmp_store)
        assert envelope["trace"]["context"]["run_id"] == "run-001"


# ---------------------------------------------------------------------------
# Test 3: list_traces returns correct trace IDs
# ---------------------------------------------------------------------------

class TestListTraces:
    def test_list_traces_returns_persisted_ids(self, tmp_store):
        persist_trace(_make_trace("t-alpha"), base_dir=tmp_store)
        persist_trace(_make_trace("t-beta"), base_dir=tmp_store)
        ids = list_traces(base_dir=tmp_store)
        assert "t-alpha" in ids
        assert "t-beta" in ids

    def test_list_traces_excludes_non_json(self, tmp_store):
        tmp_store.mkdir(parents=True, exist_ok=True)
        (tmp_store / "README.txt").write_text("not a trace")
        persist_trace(_make_trace("t-only-json"), base_dir=tmp_store)
        ids = list_traces(base_dir=tmp_store)
        assert "README" not in ids
        assert "t-only-json" in ids

    def test_list_traces_count_matches(self, tmp_store):
        for i in range(3):
            persist_trace(_make_trace(f"trace-{i}"), base_dir=tmp_store)
        ids = list_traces(base_dir=tmp_store)
        assert len(ids) == 3


# ---------------------------------------------------------------------------
# Test 4: delete_trace removes the file
# ---------------------------------------------------------------------------

class TestDeleteTrace:
    def test_delete_trace_removes_file(self, tmp_store):
        persist_trace(_make_trace("trace-del-001"), base_dir=tmp_store)
        delete_trace("trace-del-001", base_dir=tmp_store)
        assert not (tmp_store / "trace-del-001.json").exists()

    def test_delete_trace_no_longer_in_list(self, tmp_store):
        persist_trace(_make_trace("trace-del-002"), base_dir=tmp_store)
        delete_trace("trace-del-002", base_dir=tmp_store)
        assert "trace-del-002" not in list_traces(base_dir=tmp_store)


# ---------------------------------------------------------------------------
# Test 5: persist_trace rejects a trace missing trace_id
# ---------------------------------------------------------------------------

class TestPersistTraceValidation:
    def test_persist_trace_rejects_missing_trace_id(self, tmp_store):
        trace = _make_trace()
        del trace["trace_id"]
        with pytest.raises(TraceStoreError):
            persist_trace(trace, base_dir=tmp_store)

    def test_persist_trace_rejects_empty_trace_id(self, tmp_store):
        trace = _make_trace()
        trace["trace_id"] = ""
        with pytest.raises(TraceStoreError):
            persist_trace(trace, base_dir=tmp_store)


# ---------------------------------------------------------------------------
# Test 6: persist_trace rejects a non-dict trace
# ---------------------------------------------------------------------------

class TestPersistTraceTypeCheck:
    def test_persist_trace_rejects_string(self, tmp_store):
        with pytest.raises(TraceStoreError):
            persist_trace("not a dict", base_dir=tmp_store)  # type: ignore[arg-type]

    def test_persist_trace_rejects_none(self, tmp_store):
        with pytest.raises(TraceStoreError):
            persist_trace(None, base_dir=tmp_store)  # type: ignore[arg-type]

    def test_persist_trace_rejects_list(self, tmp_store):
        with pytest.raises(TraceStoreError):
            persist_trace([], base_dir=tmp_store)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test 7: load_trace raises TraceNotFoundError for unknown trace_id
# ---------------------------------------------------------------------------

class TestLoadTraceErrors:
    def test_load_trace_raises_for_unknown_id(self, tmp_store):
        with pytest.raises(TraceNotFoundError):
            load_trace("does-not-exist", base_dir=tmp_store)

    def test_load_trace_raises_for_corrupt_json(self, tmp_store):
        tmp_store.mkdir(parents=True, exist_ok=True)
        (tmp_store / "bad-trace.json").write_text("{not valid json", encoding="utf-8")
        with pytest.raises(TraceStoreError):
            load_trace("bad-trace", base_dir=tmp_store)


# ---------------------------------------------------------------------------
# Test 8: delete_trace raises TraceNotFoundError for unknown trace_id
# ---------------------------------------------------------------------------

class TestDeleteTraceErrors:
    def test_delete_trace_raises_for_unknown_id(self, tmp_store):
        with pytest.raises(TraceNotFoundError):
            delete_trace("does-not-exist", base_dir=tmp_store)


# ---------------------------------------------------------------------------
# Test 9: validate_persisted_trace returns empty list for valid envelope
# ---------------------------------------------------------------------------

class TestValidatePersistedTrace:
    def test_valid_envelope_returns_no_errors(self, tmp_store):
        trace = _make_trace("trace-valid-env")
        persist_trace(trace, base_dir=tmp_store)
        envelope = load_trace("trace-valid-env", base_dir=tmp_store)
        errors = validate_persisted_trace(envelope)
        assert errors == []

    def test_valid_envelope_with_spans(self, tmp_store):
        trace = _make_trace_with_span("trace-valid-spans")
        persist_trace(trace, base_dir=tmp_store)
        envelope = load_trace("trace-valid-spans", base_dir=tmp_store)
        errors = validate_persisted_trace(envelope)
        assert errors == []


# ---------------------------------------------------------------------------
# Test 10: validate_persisted_trace returns errors for invalid envelope
# ---------------------------------------------------------------------------

class TestValidatePersistedTraceErrors:
    def test_invalid_envelope_missing_trace(self):
        envelope = {
            "envelope_version": ENVELOPE_VERSION,
            "persisted_at": "2025-01-01T00:00:00+00:00",
            "storage_path": "data/traces/test.json",
            # missing "trace"
        }
        errors = validate_persisted_trace(envelope)
        assert len(errors) > 0

    def test_invalid_envelope_wrong_version(self):
        trace = _make_trace("test-001")
        envelope = {
            "envelope_version": "99.0.0",  # wrong version
            "persisted_at": "2025-01-01T00:00:00+00:00",
            "storage_path": "data/traces/test-001.json",
            "trace": trace,
        }
        errors = validate_persisted_trace(envelope)
        assert len(errors) > 0

    def test_non_dict_input_returns_error(self):
        errors = validate_persisted_trace("not a dict")  # type: ignore[arg-type]
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# Test 11: persist_trace is idempotent (overwriting same trace_id)
# ---------------------------------------------------------------------------

class TestPersistTraceIdempotent:
    def test_overwrite_same_trace_id(self, tmp_store):
        trace = _make_trace("trace-overwrite")
        persist_trace(trace, base_dir=tmp_store)
        # Modify and re-persist
        trace["context"] = {"updated": True}
        persist_trace(trace, base_dir=tmp_store)
        # Only one file should exist
        files = list(tmp_store.glob("trace-overwrite.json"))
        assert len(files) == 1
        # Content should reflect the latest write
        envelope = load_trace("trace-overwrite", base_dir=tmp_store)
        assert envelope["trace"]["context"]["updated"] is True


# ---------------------------------------------------------------------------
# Test 12: list_traces returns empty list when directory does not exist
# ---------------------------------------------------------------------------

class TestListTracesEmpty:
    def test_list_traces_empty_when_dir_missing(self, tmp_store):
        # tmp_store does not exist yet
        assert not tmp_store.exists()
        ids = list_traces(base_dir=tmp_store)
        assert ids == []

    def test_list_traces_empty_when_dir_empty(self, tmp_store):
        tmp_store.mkdir(parents=True)
        ids = list_traces(base_dir=tmp_store)
        assert ids == []


# ---------------------------------------------------------------------------
# Test 13: envelope contains expected metadata fields
# ---------------------------------------------------------------------------

class TestEnvelopeMetadata:
    def test_envelope_has_version(self, tmp_store):
        persist_trace(_make_trace("trace-meta-001"), base_dir=tmp_store)
        envelope = load_trace("trace-meta-001", base_dir=tmp_store)
        assert envelope["envelope_version"] == ENVELOPE_VERSION

    def test_envelope_has_persisted_at(self, tmp_store):
        persist_trace(_make_trace("trace-meta-002"), base_dir=tmp_store)
        envelope = load_trace("trace-meta-002", base_dir=tmp_store)
        assert "persisted_at" in envelope
        assert isinstance(envelope["persisted_at"], str)
        assert len(envelope["persisted_at"]) > 0

    def test_envelope_has_storage_path(self, tmp_store):
        persist_trace(_make_trace("trace-meta-003"), base_dir=tmp_store)
        envelope = load_trace("trace-meta-003", base_dir=tmp_store)
        assert "storage_path" in envelope
        assert "trace-meta-003" in envelope["storage_path"]


# ---------------------------------------------------------------------------
# Test 14: load_trace validates schema on read (corrupt envelope detected)
# ---------------------------------------------------------------------------

class TestLoadTraceSchemaValidation:
    def test_load_trace_rejects_corrupt_envelope(self, tmp_store):
        tmp_store.mkdir(parents=True, exist_ok=True)
        # Write a file that is valid JSON but not a valid envelope
        corrupt = {"not": "an envelope"}
        (tmp_store / "trace-corrupt.json").write_text(
            json.dumps(corrupt), encoding="utf-8"
        )
        with pytest.raises(TraceStoreError, match="schema validation"):
            load_trace("trace-corrupt", base_dir=tmp_store)


# ---------------------------------------------------------------------------
# Test 15: list_traces is sorted
# ---------------------------------------------------------------------------

class TestListTracesSorted:
    def test_list_traces_is_alphabetically_sorted(self, tmp_store):
        for tid in ["trace-z", "trace-a", "trace-m"]:
            persist_trace(_make_trace(tid), base_dir=tmp_store)
        ids = list_traces(base_dir=tmp_store)
        assert ids == sorted(ids)
