from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


def _load_run_module(repo_root: Path):
    module_path = repo_root / "scripts" / "run_ops02_scheduled_autonomous_execution.py"
    spec = importlib.util.spec_from_file_location("run_ops02_scheduled_autonomous_execution", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_run_ops02_emits_schedule_and_passive_monitoring_bundle(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    module = _load_run_module(repo_root)

    module.OUTPUT_DIR = tmp_path / "OPS-02"
    module.run()

    required_files = [
        "operations_execution_schedule.json",
        "selected_real_roadmap.json",
        "execution_timeline.json",
        "trust_posture_evolution.json",
        "drift_evolution.json",
        "roadmap_changes_over_time.json",
        "final_system_state.json",
        "trust_posture_snapshots.json",
        "drift_detection_records.json",
        "capability_readiness_records.json",
        "roadmap_signal_bundles.json",
        "batch_handoff_bundles.json",
    ]
    for filename in required_files:
        assert (module.OUTPUT_DIR / filename).is_file(), filename

    schedule = json.loads((module.OUTPUT_DIR / "operations_execution_schedule.json").read_text(encoding="utf-8"))
    assert schedule["max_cycles_per_run"] == 24
    assert "full_roadmap_execution" in schedule["allowed_execution_scope"]

    roadmap = json.loads((module.OUTPUT_DIR / "selected_real_roadmap.json").read_text(encoding="utf-8"))
    assert roadmap["batch_count"] >= 20

    final_state = json.loads((module.OUTPUT_DIR / "final_system_state.json").read_text(encoding="utf-8"))
    assert final_state["human_intervention_required"] is False
    assert final_state["invalid_state_not_silent"] is True
    assert final_state["unsafe_promotion_occurred"] is False
