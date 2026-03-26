from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.control_loop_chaos import (  # noqa: E402
    load_scenarios,
    run_chaos_scenarios,
    run_chaos_scenarios_from_file,
)
from spectrum_systems.modules.runtime.decision_precedence import most_severe  # noqa: E402
from spectrum_systems.modules.runtime.control_loop import ControlLoopError, run_control_loop  # noqa: E402
from tests.helpers.replay_result_builder import make_canonical_replay_result  # noqa: E402

_FIXTURE_PATH = _REPO_ROOT / "tests" / "fixtures" / "control_loop_chaos_scenarios.json"


def _base_replay_result() -> dict[str, object]:
    return make_canonical_replay_result(
        replay_id="RPL-chaos-precedence",
        trace_id="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        replay_run_id="eval-chaos-precedence",
    )


def test_chaos_runner_passes_all_declared_expectations() -> None:
    scenarios = load_scenarios(_FIXTURE_PATH)
    summary = run_chaos_scenarios(scenarios=scenarios, chaos_run_id="chaos-test")

    assert summary["scenario_count"] == len(scenarios)
    assert summary["fail_count"] == 0
    assert summary["pass_count"] == len(scenarios)
    assert summary["mismatches"] == []


def test_chaos_runner_reports_mismatch_when_expectation_is_wrong() -> None:
    scenarios = load_scenarios(_FIXTURE_PATH)
    tampered = [{**scenarios[0], "expected_response": "allow"}]
    summary = run_chaos_scenarios(scenarios=tampered, chaos_run_id="chaos-mismatch")

    assert summary["scenario_count"] == 1
    assert summary["fail_count"] == 1
    assert summary["mismatches"][0]["scenario_id"] == tampered[0]["scenario_id"]
    assert "response" in summary["mismatches"][0]["mismatch_fields"]


@pytest.mark.parametrize(
    ("artifact", "expected_signal"),
    [
        ({"artifact_type": "eval_summary", "eval_run_id": "x"}, "unsupported artifact_type"),
        ({"artifact_type": "replay_result", "replay_id": "x"}, "normalized signal missing required field"),
    ],
)
def test_fail_closed_on_malformed_input(artifact: dict[str, object], expected_signal: str) -> None:
    with pytest.raises(ControlLoopError, match=expected_signal):
        run_control_loop(artifact, {"execution_id": "x", "stage": "chaos", "runtime_environment": "test"})  # type: ignore[arg-type]


def test_runner_is_deterministic_across_repeated_runs() -> None:
    scenarios = load_scenarios(_FIXTURE_PATH)
    first = run_chaos_scenarios(scenarios=scenarios, chaos_run_id="determinism-1", timestamp="2026-03-24T00:00:00Z")
    second = run_chaos_scenarios(scenarios=scenarios, chaos_run_id="determinism-1", timestamp="2026-03-24T00:00:00Z")

    assert first["scenario_results"] == second["scenario_results"]
    assert first["mismatches"] == second["mismatches"]


@pytest.mark.parametrize(
    ("replay_patch", "expected_response"),
    [
        ({"observability_metrics": {"metrics": {"replay_success_rate": 0.70, "drift_exceed_threshold_rate": 0.01}}}, "warn"),
        ({"observability_metrics": {"metrics": {"replay_success_rate": 0.95, "drift_exceed_threshold_rate": 0.50}}}, "freeze"),
        ({"consistency_status": "mismatch"}, "block"),
        ({"observability_metrics": {"metrics": {"replay_success_rate": 0.70, "drift_exceed_threshold_rate": 0.50}}}, "freeze"),
        ({"observability_metrics": {"metrics": {"replay_success_rate": 0.95, "drift_exceed_threshold_rate": 0.50}}, "consistency_status": "mismatch"}, "block"),
    ],
)
def test_precedence_rules_are_explicitly_enforced(
    replay_patch: dict[str, object],
    expected_response: str,
) -> None:
    replay = _base_replay_result()
    if "observability_metrics" in replay_patch:
        replay["observability_metrics"]["metrics"].update(replay_patch["observability_metrics"]["metrics"])  # type: ignore[index]
    if "consistency_status" in replay_patch:
        replay["consistency_status"] = replay_patch["consistency_status"]
        replay["drift_detected"] = replay_patch["consistency_status"] == "mismatch"
    decision = run_control_loop(replay, {"execution_id": "x", "stage": "chaos", "runtime_environment": "test"})["evaluation_control_decision"]  # type: ignore[arg-type]
    assert decision["system_response"] == expected_response


def test_summary_artifact_is_emitted_to_json(tmp_path: Path) -> None:
    output_path = tmp_path / "evaluation_control_chaos_summary.json"
    summary = run_chaos_scenarios_from_file(scenarios_path=_FIXTURE_PATH, output_path=output_path)

    assert output_path.exists()
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["artifact_type"] == "evaluation_control_chaos_summary"
    assert written["id"] == written["chaos_run_id"]
    assert written["trace_refs"] == {"primary": written["chaos_run_id"], "related": []}
    assert written["scenario_count"] == summary["scenario_count"]


def test_cli_returns_zero_when_no_mismatch(tmp_path: Path) -> None:
    output = tmp_path / "summary.json"
    script = _REPO_ROOT / "scripts" / "run_control_loop_chaos_tests.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--scenarios",
            str(_FIXTURE_PATH),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["fail_count"] == 0


def test_canonical_precedence_order_is_stable() -> None:
    assert most_severe(["promote", "warn", "hold"], default="promote") == "hold"
    assert most_severe(["warn", "freeze"], default="promote") == "freeze"
    assert most_severe(["hold", "rollback"], default="promote") == "rollback"
