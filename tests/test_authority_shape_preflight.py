"""Tests verifying the authority shape preflight passes on the current repo state.

These tests act as regression guards: if authority-shaped vocabulary is
re-introduced in dashboard/MET artifacts, these tests catch it immediately.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = REPO_ROOT / "outputs" / "authority_shape_preflight" / "authority_shape_preflight_result.json"
DASHBOARD_SEED = REPO_ROOT / "artifacts" / "dashboard_seed"
DASHBOARD_METRICS = REPO_ROOT / "artifacts" / "dashboard_metrics"


def _run_preflight() -> dict:
    import subprocess, sys
    script = REPO_ROOT / "scripts" / "run_authority_shape_preflight.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--suggest-only"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert RESULT_PATH.is_file(), f"preflight result not written; stderr: {proc.stderr}"
    return json.loads(RESULT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def preflight_result() -> dict:
    return _run_preflight()


def test_preflight_passes_on_current_state(preflight_result: dict) -> None:
    violations = preflight_result.get("violations", [])
    assert preflight_result["status"] == "pass", (
        f"authority shape preflight failed with {len(violations)} violation(s):\n"
        + "\n".join(f"  {v}" for v in violations[:10])
    )


def test_preflight_violation_count_is_zero(preflight_result: dict) -> None:
    assert preflight_result["violation_count"] == 0


def test_preflight_scanned_dashboard_seed_artifacts(preflight_result: dict) -> None:
    scanned = preflight_result.get("scanned_files", [])
    seed_scanned = [f for f in scanned if "dashboard_seed" in f]
    assert len(seed_scanned) > 0, "preflight must scan at least one dashboard_seed artifact"


def test_preflight_scanned_dashboard_metrics_artifacts(preflight_result: dict) -> None:
    scanned = preflight_result.get("scanned_files", [])
    metrics_scanned = [f for f in scanned if "dashboard_metrics" in f]
    assert len(metrics_scanned) > 0, "preflight must scan at least one dashboard_metrics artifact"


def test_preflight_scanned_met_review_doc(preflight_result: dict) -> None:
    scanned = preflight_result.get("scanned_files", [])
    met_docs = [f for f in scanned if "MET-" in f and f.endswith(".md")]
    assert len(met_docs) > 0, "preflight must scan at least one MET-prefixed review doc"


def test_renamed_seed_artifacts_exist() -> None:
    for name in [
        "control_signal_record.json",
        "trust_policy_signal_record.json",
        "sel_signal_record.json",
    ]:
        assert (DASHBOARD_SEED / name).is_file(), f"expected renamed artifact missing: {name}"


def test_old_authority_named_seed_artifacts_removed() -> None:
    for name in [
        "control_decision_record.json",
        "enforcement_action_record.json",
        "trust_policy_decision_record.json",
    ]:
        assert not (DASHBOARD_SEED / name).is_file(), (
            f"old authority-named artifact still present: {name}"
        )


def test_control_signal_record_has_clean_artifact_type() -> None:
    path = DASHBOARD_SEED / "control_signal_record.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "control_signal_record"
    assert "decision" not in payload.get("payload", {})


def test_trust_policy_signal_record_has_clean_artifact_type() -> None:
    path = DASHBOARD_SEED / "trust_policy_signal_record.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "trust_policy_signal_record"
    assert "decision" not in payload.get("payload", {})


def test_sel_signal_record_has_clean_artifact_type() -> None:
    path = DASHBOARD_SEED / "sel_signal_record.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "sel_signal_record"
