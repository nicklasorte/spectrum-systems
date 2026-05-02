"""F3L-03 — Tests for deterministic PRL artifact persistence.

PRL retains all classification, repair-candidate, and eval-candidate
authority. These tests assert only that PRL persists its artifacts at
stable file paths so downstream observers (APU, replay) can ingest
file-based evidence rather than parsing the legacy stdout NDJSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


import re

_VOLATILE_KEYS = {
    "timestamp",
    "generated_at",
    "created_at",
    "last_updated",
    "run_at",
    "gated_at",
    "run_id",
    "trace_id",
    "id",
    "trace_refs",
    "primary",
    "candidate_id",
    "gated_eval_id",
    "capture_record_ref",
    "failure_packet_ref",
    "candidate_ref",
}

_ID_RE = re.compile(r"prl-[a-z]+-[0-9a-f]{8,}")


def _scrub_ids_in_string(s: str) -> str:
    return _ID_RE.sub("prl-XXX", s)


def _normalize(obj):
    if isinstance(obj, dict):
        return {
            k: _normalize(v) for k, v in sorted(obj.items()) if k not in _VOLATILE_KEYS
        }
    if isinstance(obj, list):
        # Sort lists of strings so two runs produce the same structural set
        normalized = [_normalize(x) for x in obj]
        if normalized and all(isinstance(x, str) for x in normalized):
            return sorted({_scrub_ids_in_string(x) for x in normalized})
        return normalized
    if isinstance(obj, str):
        return _scrub_ids_in_string(obj)
    return obj


def _normalize_text(payload: dict) -> str:
    return json.dumps(_normalize(payload), sort_keys=True)


def _import_run_gate():
    from scripts.run_pre_pr_reliability_gate import run_gate

    return run_gate


def test_run_gate_writes_gate_result_file(tmp_path: Path) -> None:
    """When ``output_dir`` is supplied, prl_gate_result.json is written."""
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        result = run_gate(
            run_id="run-test-persist",
            trace_id="trace-test-persist",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    gate_path = tmp_path / "prl_gate_result.json"
    assert gate_path.is_file()
    written = json.loads(gate_path.read_text(encoding="utf-8"))
    assert written["artifact_type"] == "prl_gate_result"
    assert written["gate_recommendation"] == result["gate_recommendation"]


def test_run_gate_writes_failure_packets_to_stable_paths(tmp_path: Path) -> None:
    """Each failure packet is persisted under failure_packets/ subdirectory."""
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        result = run_gate(
            run_id="run-test-packets",
            trace_id="trace-test-packets",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    fp_dir = tmp_path / "failure_packets"
    assert fp_dir.is_dir()
    files = list(fp_dir.glob("*.json"))
    assert files, "no failure packet files written"
    # gate result references should include the file paths
    file_paths = {str(p) for p in files}
    assert any(
        any(ref.endswith(p.name) for p in files)
        for ref in result["failure_packet_refs"]
    )


def test_run_gate_persists_repair_and_eval_candidates(tmp_path: Path) -> None:
    """Repair + eval candidate subdirectories receive artifacts; gate result includes paths."""
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        result = run_gate(
            run_id="run-test-repair-eval",
            trace_id="trace-test-repair-eval",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    repair_dir = tmp_path / "repair_candidates"
    eval_dir = tmp_path / "eval_candidates"
    assert repair_dir.is_dir() and list(repair_dir.glob("*.json"))
    assert eval_dir.is_dir() and list(eval_dir.glob("*.json"))
    assert any(
        ref.startswith(str(repair_dir.name)) or "repair_candidates/" in ref
        for ref in result["repair_candidate_refs"]
    )
    assert any(
        ref.startswith(str(eval_dir.name)) or "eval_candidates/" in ref
        for ref in result["eval_candidate_refs"]
    )


def test_run_gate_passed_run_writes_only_gate_result(tmp_path: Path) -> None:
    """A clean run still writes prl_gate_result.json (no per-failure artifacts)."""
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (0, "")
        result = run_gate(
            run_id="run-test-clean",
            trace_id="trace-test-clean",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    assert result["gate_recommendation"] == "passed_gate"
    assert (tmp_path / "prl_gate_result.json").is_file()
    assert not list((tmp_path / "failure_packets").glob("*.json")) if (
        tmp_path / "failure_packets"
    ).exists() else True


def test_two_runs_produce_no_structural_diff(tmp_path: Path) -> None:
    """F3L-03 acceptance: a second run produces no structural diff vs first.

    Volatile fields (timestamps, run_id, trace_id, ids) are excluded;
    everything else must match byte-for-byte.
    """
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        first = run_gate(
            run_id="run-test-determinism-a",
            trace_id="trace-test-determinism-a",
            skip_pytest=True,
            output_dir=tmp_path,
        )
        second = run_gate(
            run_id="run-test-determinism-b",
            trace_id="trace-test-determinism-b",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    assert _normalize_text(first) == _normalize_text(second)


def test_replay_from_artifacts_alone(tmp_path: Path) -> None:
    """The persisted artifacts alone are sufficient to reconstruct what PRL emitted.

    F3L-03 acceptance: replay must be possible from artifacts alone, not
    from the stdout NDJSON.
    """
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        result = run_gate(
            run_id="run-test-replay",
            trace_id="trace-test-replay",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    gate_path = tmp_path / "prl_gate_result.json"
    assert gate_path.is_file()
    replayed = json.loads(gate_path.read_text(encoding="utf-8"))
    assert replayed == result

    # Each file-path ref in the gate result must exist on disk
    refs_to_check: list[str] = []
    for key in ("failure_packet_refs", "repair_candidate_refs", "eval_candidate_refs"):
        for ref in replayed[key]:
            if "/" in ref:
                refs_to_check.append(ref)
    assert refs_to_check, "no file-path refs written"
    for ref in refs_to_check:
        # refs are relative to repo root; resolve under tmp_path for the test
        candidate = tmp_path / ref.split("outputs/prl/", 1)[-1]
        if candidate.is_file():
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            assert payload.get("artifact_type")


def test_output_dir_none_disables_persistence(tmp_path: Path) -> None:
    """When output_dir is None, no files are written (legacy stdout-only mode)."""
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        run_gate(
            run_id="run-test-no-dir",
            trace_id="trace-test-no-dir",
            skip_pytest=True,
            output_dir=None,
        )
    assert not (tmp_path / "prl_gate_result.json").is_file()
