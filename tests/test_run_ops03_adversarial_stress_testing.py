from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


def _load_module(repo_root: Path):
    module_path = repo_root / "scripts" / "run_ops03_adversarial_stress_testing.py"
    spec = importlib.util.spec_from_file_location("run_ops03_adversarial_stress_testing", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_run_ops03_emits_expected_fail_closed_report(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    module = _load_module(repo_root)

    output_path = tmp_path / "OPS-03" / "adversarial_stress_report.json"
    module.run(output_path=output_path, max_cycles=24)

    assert output_path.is_file()
    report = json.loads(output_path.read_text(encoding="utf-8"))

    assert report["run_id"] == "OPS-03"
    assert report["execution_mode"] == {
        "drift_detection_enabled": True,
        "roadmap_steering_enabled": True,
        "readiness_gating_enabled": True,
        "promotion_gating_enabled": True,
        "policy_enforcement_enabled": True,
        "human_intervention_used": False,
    }

    expected_scenarios = [
        "missing_eval_coverage",
        "replay_mismatch",
        "drift_spike",
        "policy_conflict",
        "judgment_conflict",
        "budget_breach",
        "stale_artifact_dominance",
    ]
    actual_scenarios = [entry["scenario"] for entry in report["failure_timeline"]]
    assert actual_scenarios == expected_scenarios

    assert report["validation"]["no_silent_continuation"] is True
    assert report["validation"]["drift_changes_behavior"] is True
    assert report["validation"]["system_halts_correctly_when_needed"] is True

    assert report["halt_conditions"]["halted"] is True
    assert report["halt_conditions"]["halt_cycle"] == 7
    assert report["final_system_state"]["state"] == "halted_fail_closed"
    assert report["final_system_state"]["unsafe_promotion_prevented"] is True


def test_run_ops03_output_is_deterministic(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    module = _load_module(repo_root)

    output_a = tmp_path / "run-a.json"
    output_b = tmp_path / "run-b.json"

    module.run(output_path=output_a, max_cycles=24)
    module.run(output_path=output_b, max_cycles=24)

    payload_a = json.loads(output_a.read_text(encoding="utf-8"))
    payload_b = json.loads(output_b.read_text(encoding="utf-8"))
    assert payload_a == payload_b


def test_run_ops03_fail_closed_for_incomplete_injection_surface(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    module = _load_module(repo_root)

    output_path = tmp_path / "should_not_exist.json"
    try:
        module.run(output_path=output_path, max_cycles=6)
    except RuntimeError as exc:
        assert "max_cycles must be >= 7" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for incomplete OPS-03 injection surface")
