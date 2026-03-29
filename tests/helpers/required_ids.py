"""Shared helpers for required run/trace identity fields in test artifacts."""

from __future__ import annotations


def add_required_ids(obj: dict) -> dict:
    """Ensure fail-closed required identity fields are present in test payloads."""
    obj.setdefault("run_id", "run-test-001")
    obj.setdefault("trace_id", "trace-test-001")
    return obj
