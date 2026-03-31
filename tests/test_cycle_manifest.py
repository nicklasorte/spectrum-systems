from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.orchestration.cycle_manifest_validator import CycleManifestError, validate_cycle_manifest


_REPO_ROOT = Path(__file__).resolve().parents[1]


def _example_manifest() -> dict:
    return json.loads((_REPO_ROOT / "contracts" / "examples" / "cycle_manifest.json").read_text(encoding="utf-8"))


def test_cycle_manifest_example_validates() -> None:
    manifest = _example_manifest()
    validate_cycle_manifest(manifest)


def test_cycle_manifest_rejects_selected_step_outside_eligible_snapshot() -> None:
    manifest = _example_manifest()
    manifest["selected_step_id"] = "CTRL-99"

    with pytest.raises(CycleManifestError, match="selected_step_id must be present"):
        validate_cycle_manifest(manifest)


def test_cycle_manifest_rejects_blocked_state_without_blocking_issues() -> None:
    manifest = _example_manifest()
    manifest["current_state"] = "blocked"
    manifest["blocking_issues"] = []

    with pytest.raises(CycleManifestError, match="blocked state requires"):
        validate_cycle_manifest(manifest)


def test_cycle_manifest_rejects_inconsistent_timing() -> None:
    manifest = _example_manifest()
    manifest["execution_started_at"] = "2026-03-31T12:00:00Z"
    manifest["execution_completed_at"] = "2026-03-31T11:00:00Z"

    with pytest.raises(CycleManifestError, match="execution_completed_at must be >= execution_started_at"):
        validate_cycle_manifest(manifest)


def test_cycle_manifest_rejects_sequence_state_without_traceability() -> None:
    manifest = _example_manifest()
    manifest["sequence_mode"] = "three_slice"
    manifest["current_state"] = "admitted"
    manifest["sequence_trace_id"] = None
    manifest["sequence_lineage"] = []

    with pytest.raises(CycleManifestError, match="None is not of type 'string'"):
        validate_cycle_manifest(manifest)
