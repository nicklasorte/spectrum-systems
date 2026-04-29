"""RFX-N17 — PR failure ingestion into RFX.

Parses structured PR failure log entries and converts them into normalized
RFX failure records suitable for corpus, eval-bridge, and replay-packet
consumption. Raw unstructured log strings are rejected.

This module is a non-owning phase-label support helper. It does not own PR
governance or merge outcomes — canonical ownership is declared in
``docs/architecture/system_registry.md``.

Failure prevented: PR log data entering RFX without structured failure
extraction, hiding failure patterns and blocking replay/eval pipelines.

Signal improved: PR-failure-to-RFX conversion rate; structured failure record
coverage of PR CI history.

Reason codes:
  rfx_pr_ingestion_empty              — no log entries supplied
  rfx_pr_ingestion_unstructured       — log entry is a raw string without structured fields
  rfx_pr_ingestion_missing_failure_id — structured entry lacks a failure identifier
  rfx_pr_ingestion_missing_reason     — structured entry lacks a reason/classification
  rfx_pr_ingestion_missing_trace      — structured entry lacks a trace reference
"""

from __future__ import annotations

from typing import Any


def ingest_rfx_pr_failures(
    *,
    pr_log_entries: list[Any],
) -> dict[str, Any]:
    """Normalize PR failure log entries into structured RFX failure records.

    Each entry must be a dict (not a raw string). Entries missing required
    fields are flagged with reason codes but still included in the output
    with ``None`` for the missing fields.
    """
    reason: list[str] = []
    records: list[dict[str, Any]] = []

    if not pr_log_entries:
        reason.append("rfx_pr_ingestion_empty")
        return {
            "artifact_type": "rfx_pr_failure_ingestion_result",
            "schema_version": "1.0.0",
            "failure_records": records,
            "reason_codes_emitted": sorted(set(reason)),
            "status": "empty",
            "signals": {
                "total_entries": 0,
                "structured_count": 0,
                "normalized_count": 0,
                "conversion_rate": 0.0,
            },
        }

    structured_count = 0
    normalized_count = 0

    for entry in pr_log_entries:
        if isinstance(entry, str):
            reason.append("rfx_pr_ingestion_unstructured")
            continue
        if not isinstance(entry, dict):
            reason.append("rfx_pr_ingestion_unstructured")
            continue

        structured_count += 1
        entry_ok = True

        failure_id = (
            entry.get("failure_id")
            or entry.get("id")
            or entry.get("check_run_id")
            or ""
        )
        if not failure_id:
            reason.append("rfx_pr_ingestion_missing_failure_id")
            entry_ok = False

        classification = (
            entry.get("classification")
            or entry.get("reason")
            or entry.get("failure_reason")
            or ""
        )
        if not classification:
            reason.append("rfx_pr_ingestion_missing_reason")
            entry_ok = False

        trace_ref = (
            entry.get("trace_ref")
            or entry.get("trace_id")
            or entry.get("run_id")
            or ""
        )
        if not trace_ref:
            reason.append("rfx_pr_ingestion_missing_trace")
            entry_ok = False

        if entry_ok:
            normalized_count += 1

        records.append({
            "failure_id": failure_id or None,
            "classification": classification or None,
            "trace_ref": trace_ref or None,
            "pr_number": entry.get("pr_number"),
            "check_name": entry.get("check_name"),
            "description": entry.get("description", ""),
            "reproduction_inputs": entry.get("reproduction_inputs"),
            "expected_outcome": entry.get("expected_outcome"),
        })

    total = len(pr_log_entries)
    unique_reasons = sorted(set(reason))
    return {
        "artifact_type": "rfx_pr_failure_ingestion_result",
        "schema_version": "1.0.0",
        "failure_records": records,
        "reason_codes_emitted": unique_reasons,
        "status": "complete" if not unique_reasons else "incomplete",
        "signals": {
            "total_entries": total,
            "structured_count": structured_count,
            "normalized_count": normalized_count,
            "conversion_rate": normalized_count / max(total, 1),
        },
    }
