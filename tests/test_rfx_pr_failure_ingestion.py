"""Tests for rfx_pr_failure_ingestion (RFX-N17)."""

from spectrum_systems.modules.runtime.rfx_pr_failure_ingestion import (
    ingest_rfx_pr_failures,
)


def _entry(**kw):
    base = {
        "failure_id": "fail-001",
        "classification": "pytest_selection_incomplete",
        "trace_ref": "run-abc",
        "pr_number": 42,
        "check_name": "pr-pytest",
    }
    base.update(kw)
    return base


# RT-N17: PR log without structured failure extraction → must fail.
def test_rt_n17_raw_string_blocked():
    result = ingest_rfx_pr_failures(pr_log_entries=["raw log line without structure"])
    assert "rfx_pr_ingestion_unstructured" in result["reason_codes_emitted"]
    assert result["signals"]["normalized_count"] == 0


def test_rt_n17_structured_entry_passes():
    result = ingest_rfx_pr_failures(pr_log_entries=[_entry()])
    assert result["status"] == "complete"
    assert result["signals"]["normalized_count"] == 1


def test_empty_log_flagged():
    result = ingest_rfx_pr_failures(pr_log_entries=[])
    assert "rfx_pr_ingestion_empty" in result["reason_codes_emitted"]


def test_missing_failure_id_flagged():
    result = ingest_rfx_pr_failures(pr_log_entries=[_entry(failure_id="")])
    assert "rfx_pr_ingestion_missing_failure_id" in result["reason_codes_emitted"]


def test_missing_reason_flagged():
    result = ingest_rfx_pr_failures(pr_log_entries=[_entry(classification="")])
    assert "rfx_pr_ingestion_missing_reason" in result["reason_codes_emitted"]


def test_missing_trace_flagged():
    result = ingest_rfx_pr_failures(pr_log_entries=[_entry(trace_ref="")])
    assert "rfx_pr_ingestion_missing_trace" in result["reason_codes_emitted"]


def test_mixed_entries():
    result = ingest_rfx_pr_failures(pr_log_entries=[_entry(), "bad string"])
    assert result["signals"]["structured_count"] == 1
    assert "rfx_pr_ingestion_unstructured" in result["reason_codes_emitted"]


def test_conversion_rate_full():
    result = ingest_rfx_pr_failures(pr_log_entries=[_entry(), _entry(failure_id="fail-002")])
    assert result["signals"]["conversion_rate"] == 1.0


def test_output_record_fields():
    result = ingest_rfx_pr_failures(pr_log_entries=[_entry()])
    rec = result["failure_records"][0]
    assert rec["failure_id"] == "fail-001"
    assert rec["classification"] == "pytest_selection_incomplete"
    assert rec["trace_ref"] == "run-abc"


def test_artifact_type():
    result = ingest_rfx_pr_failures(pr_log_entries=[_entry()])
    assert result["artifact_type"] == "rfx_pr_failure_ingestion_result"


def test_whitespace_failure_id_flagged():
    # P1 fix: whitespace-only failure_id must emit rfx_pr_ingestion_missing_failure_id.
    result = ingest_rfx_pr_failures(pr_log_entries=[_entry(failure_id="   ")])
    assert "rfx_pr_ingestion_missing_failure_id" in result["reason_codes_emitted"]
    assert result["signals"]["normalized_count"] == 0


def test_whitespace_classification_flagged():
    # P1 fix: whitespace-only classification must emit rfx_pr_ingestion_missing_reason.
    result = ingest_rfx_pr_failures(pr_log_entries=[_entry(classification="   ")])
    assert "rfx_pr_ingestion_missing_reason" in result["reason_codes_emitted"]
    assert result["signals"]["normalized_count"] == 0


def test_whitespace_trace_ref_flagged():
    # P1 fix: whitespace-only trace_ref must emit rfx_pr_ingestion_missing_trace.
    result = ingest_rfx_pr_failures(pr_log_entries=[_entry(trace_ref="   ")])
    assert "rfx_pr_ingestion_missing_trace" in result["reason_codes_emitted"]
    assert result["signals"]["normalized_count"] == 0
