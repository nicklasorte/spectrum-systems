from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


def _load_run_module(repo_root: Path):
    module_path = repo_root / "scripts" / "run_autonomous_validation_run.py"
    spec = importlib.util.spec_from_file_location("run_autonomous_validation_run", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_run_autonomous_validation_run_emits_required_bundle(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    module = _load_run_module(repo_root)

    module.OUTPUT_DIR = tmp_path / "RUN-01"
    module.run()

    required_files = [
        "system_roadmap.json",
        "roadmap_execution_report.json",
        "multi_cycle_execution_report.json",
        "trust_posture_snapshots.json",
        "drift_detection_records.json",
        "policy_activation_records.json",
        "capability_readiness_records.json",
    ]
    for filename in required_files:
        assert (module.OUTPUT_DIR / filename).is_file(), filename

    roadmap = json.loads((module.OUTPUT_DIR / "system_roadmap.json").read_text(encoding="utf-8"))
    assert len(roadmap["batches"]) == 24

    titles = [str(batch["title"]) for batch in roadmap["batches"]]
    assert sum("failure_injected" in title for title in titles) >= 2
    assert any("drift_inducing" in title for title in titles)

    report = json.loads((module.OUTPUT_DIR / "roadmap_execution_report.json").read_text(encoding="utf-8"))
    assert report["stop_reason"] == "unsafe_halt"
    assert report["validation_checks"]["drift_changes_behavior"] is True
    assert report["validation_checks"]["system_halts_correctly_when_required"] is True

    drift_records = json.loads((module.OUTPUT_DIR / "drift_detection_records.json").read_text(encoding="utf-8"))
    assert drift_records
    assert drift_records[0]["behavior_change"] == "freeze_and_reprioritize"
