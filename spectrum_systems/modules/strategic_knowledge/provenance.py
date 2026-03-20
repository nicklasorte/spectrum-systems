"""Provenance helper utilities for strategic knowledge artifact families."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_provenance(*, extraction_run_id: str, extractor_version: str, notes: str | None = None) -> dict[str, Any]:
    provenance = {
        "extraction_run_id": extraction_run_id,
        "extractor_version": extractor_version,
    }
    if notes:
        provenance["notes"] = notes
    return provenance


def pdf_anchor(*, page_number: int, text_span: str | None = None, quote_snippet: str | None = None) -> dict[str, Any]:
    anchor = {"anchor_type": "pdf", "page_number": page_number}
    if text_span:
        anchor["text_span"] = text_span
    if quote_snippet:
        anchor["quote_snippet"] = quote_snippet
    return anchor


def transcript_anchor(
    *,
    timestamp_start: str,
    timestamp_end: str,
    speaker: str | None = None,
    quote_snippet: str | None = None,
) -> dict[str, Any]:
    anchor = {
        "anchor_type": "transcript",
        "timestamp_start": timestamp_start,
        "timestamp_end": timestamp_end,
    }
    if speaker:
        anchor["speaker"] = speaker
    if quote_snippet:
        anchor["quote_snippet"] = quote_snippet
    return anchor

