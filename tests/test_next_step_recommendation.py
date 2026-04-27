from __future__ import annotations

from pathlib import Path

from spectrum_systems.modules.dashboard_3ls.next_step_recommendation.next_step_engine import build_next_step_report
from spectrum_systems.modules.dashboard_3ls.next_step_recommendation.next_step_inputs import NextStepInputs, SourceRef


def _runtime_inputs(
    *,
    missing_required: list[str] | None = None,
    blf_status: str = "pass",
    rfx_status: str = "implemented",
    drift_detected: bool = False,
    include_h01: bool = True,
) -> NextStepInputs:
    missing_required = missing_required or []
    required_paths = [
        "contracts/examples/system_roadmap.json",
        "docs/roadmaps/system_roadmap.md",
        "docs/roadmaps/rfx_cross_system_roadmap.md",
        "artifacts/system_dependency_priority_report.json",
        "artifacts/rmp_01_delivery_report.json",
        "artifacts/rmp_drift_report.json",
        "artifacts/blf_01_baseline_failure_fix/delivery_report.json",
    ]
    source_refs = [
        SourceRef(path=path, required=True, present=path not in missing_required, content_hash="sha256:test" if path not in missing_required else None)
        for path in required_paths
    ]
    source_refs.append(SourceRef(path="artifacts/rfx_04_loop_07_08/delivery_report.json", required=False, present=True, content_hash="sha256:test"))
    source_refs.append(SourceRef(path="contracts/review_artifact/H01_review.json", required=False, present=include_h01, content_hash="sha256:test" if include_h01 else None))
    source_refs.append(SourceRef(path="docs/reviews/H01_pre_mvp_spine_review.md", required=False, present=include_h01, content_hash="sha256:test" if include_h01 else None))

    payloads = {
        "artifacts/system_dependency_priority_report.json": {"top_5": [{"system_id": "MET"}]},
        "artifacts/rmp_01_delivery_report.json": {"status": "pass", "h01_readiness": {"ready": True}},
        "artifacts/rmp_drift_report.json": {"status": "pass", "drift_detected": drift_detected},
        "artifacts/blf_01_baseline_failure_fix/delivery_report.json": {"status": blf_status},
        "artifacts/rfx_04_loop_07_08/delivery_report.json": {"status": rfx_status},
    }
    return NextStepInputs(source_refs=source_refs, payloads=payloads, reason_codes=[f"missing_required_artifact:{p}" for p in missing_required])


def test_happy_path_selects_rfx_proof(monkeypatch):
    monkeypatch.setattr(
        "spectrum_systems.modules.dashboard_3ls.next_step_recommendation.next_step_engine.load_inputs",
        lambda _repo_root: _runtime_inputs(),
    )
    report, hard_failure = build_next_step_report(Path("."))
    assert hard_failure is False
    assert report["selected_recommendation"]["id"] == "RFX-PROOF-01"


def test_met_hop_and_evl_rejected_before_prereqs(monkeypatch):
    monkeypatch.setattr(
        "spectrum_systems.modules.dashboard_3ls.next_step_recommendation.next_step_engine.load_inputs",
        lambda _repo_root: _runtime_inputs(include_h01=False),
    )
    report, _ = build_next_step_report(Path("."))
    rejected = {row["work_item"] for row in report["rejected_next_steps"]}
    assert {"MET", "HOP", "EVL"}.issubset(rejected)


def test_fake_implemented_status_is_detected(monkeypatch):
    inputs = _runtime_inputs(include_h01=True)
    inputs.payloads["artifacts/blf_01_baseline_failure_fix/delivery_report.json"] = {"status": "failed"}
    monkeypatch.setattr(
        "spectrum_systems.modules.dashboard_3ls.next_step_recommendation.next_step_engine.load_inputs",
        lambda _repo_root: inputs,
    )
    report, _ = build_next_step_report(Path("."))
    assert any(item["reason_code"] == "h01_readiness_without_prereqs" for item in report["red_team_findings"])


def test_missing_required_artifact_blocks(monkeypatch):
    missing_path = "artifacts/rmp_01_delivery_report.json"
    monkeypatch.setattr(
        "spectrum_systems.modules.dashboard_3ls.next_step_recommendation.next_step_engine.load_inputs",
        lambda _repo_root: _runtime_inputs(missing_required=[missing_path]),
    )
    report, hard_failure = build_next_step_report(Path("."))
    assert hard_failure is True
    assert report["status"] == "blocked"
    assert f"missing_required_artifact:{missing_path}" in report["reason_codes"]


def test_source_refs_include_sha256(monkeypatch):
    monkeypatch.setattr(
        "spectrum_systems.modules.dashboard_3ls.next_step_recommendation.next_step_engine.load_inputs",
        lambda _repo_root: _runtime_inputs(),
    )
    report, _ = build_next_step_report(Path("."))
    assert all(ref["content_hash"] is None or str(ref["content_hash"]).startswith("sha256:") for ref in report["source_refs"])


def test_builder_import_is_jsonschema_safe():
    import subprocess
    import sys

    probe = (
        "import importlib,sys;"
        "importlib.import_module('scripts.build_next_step_recommendation');"
        "print('jsonschema' in sys.modules)"
    )
    out = subprocess.check_output([sys.executable, "-c", probe], text=True).strip()
    assert out == "False"


def test_package_import_does_not_pull_runtime_run_bundle():
    import subprocess
    import sys

    probe = (
        "import importlib,sys;"
        "importlib.import_module('spectrum_systems.modules.dashboard_3ls.next_step_recommendation');"
        "print('spectrum_systems.modules.runtime.run_bundle' in sys.modules)"
    )
    out = subprocess.check_output([sys.executable, "-c", probe], text=True).strip()
    assert out == "False"
