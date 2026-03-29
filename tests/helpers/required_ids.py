"""Shared helpers for required run/trace identity fields in test artifacts."""

from __future__ import annotations

from spectrum_systems.modules.runtime.identity_enforcement import ensure_required_ids


def add_required_ids(obj: dict) -> dict:
    """Ensure fail-closed required identity fields are present in test payloads."""
    return ensure_required_ids(obj, run_id="run-test-001", trace_id="trace-test-001")
