from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.orchestration import cycle_runner


_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "autonomous_cycle"


def _write(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture(name: str) -> dict:
    return _load(_FIXTURES / name)


def _manifest(tmp_path: Path, *, state: str = "roadmap_under_review") -> tuple[dict, Path]:
    roadmap_path = _REPO_ROOT / "docs" / "roadmap" / "system_roadmap.md"
    review_path = tmp_path / "roadmap_review.json"
    _write(review_path, _fixture("roadmap_review_approved.json"))

    pqx_request = {
        "step_id": "AI-01",
        "roadmap_path": str(roadmap_path),
        "state_path": str(tmp_path / "pqx_state.json"),
        "runs_root": str(tmp_path / "pqx_runs"),
        "pqx_output_text": "deterministic pqx output",
    }
    pqx_request_path = tmp_path / "pqx_request.json"
    _write(pqx_request_path, pqx_request)

    base = {
        "cycle_id": "cycle-test",
        "current_state": state,
        "roadmap_artifact_path": str(roadmap_path),
        "roadmap_review_artifact_paths": [str(review_path)],
        "execution_report_paths": [],
        "implementation_review_paths": [],
        "fix_roadmap_path": None,
        "certification_record_path": None,
        "blocking_issues": [],
        "next_action": "await_roadmap_approval",
        "roadmap_approval_state": "approved",
        "hard_gates": {
            "roadmap_approved": True,
            "execution_contracts_pinned": True,
            "review_templates_present": True,
        },
        "pqx_execution_request_path": str(pqx_request_path),
        "pqx_request_ref": None,
        "execution_started_at": None,
        "execution_completed_at": None,
        "certification_status": "pending",
        "certification_summary": None,
        "done_certification_input_refs": {
            "replay_result_ref": "a",
            "regression_result_ref": "b",
            "certification_pack_ref": "c",
            "error_budget_ref": "d",
            "policy_ref": "e",
        },
        "updated_at": "2026-03-30T00:00:00Z",
    }
    path = tmp_path / "cycle_manifest.json"
    _write(path, base)
    return base, path


def test_cycle_runner_happy_path_execution_ready_through_certified_done(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="execution_ready")

    execution_result = cycle_runner.run_cycle(manifest_path)
    assert execution_result["next_state"] == "execution_complete_unreviewed"

    updated = _load(manifest_path)
    assert updated["current_state"] == "execution_complete_unreviewed"
    assert updated["execution_report_paths"]

    report_payload = _load(Path(updated["execution_report_paths"][0]))
    produced = report_payload["produced_artifacts"]
    slice_record_path = next(path for path in produced if path.endswith(".pqx_slice_execution_record.json"))
    slice_record = _load(Path(slice_record_path))
    emitted = slice_record["artifacts_emitted"]

    runs_root = Path(updated["pqx_execution_request_path"]).parent / "pqx_runs"

    def _resolve(name: str) -> str:
        rel = next(path for path in emitted if path.endswith(name))
        return str(runs_root / rel)

    refs = {
        "replay_result_ref": _resolve(".replay_result.json"),
        "regression_result_ref": _resolve(".regression_run_result.json"),
        "certification_pack_ref": _resolve(".control_loop_certification_pack.json"),
        "error_budget_ref": _resolve(".error_budget_status.json"),
        "policy_ref": _resolve(".control_decision.json"),
    }

    updated["current_state"] = "certification_pending"
    updated["done_certification_input_refs"] = refs
    _write(manifest_path, updated)

    certification_result = cycle_runner.run_cycle(manifest_path)
    assert certification_result["next_state"] == "certified_done"

    final_manifest = _load(manifest_path)
    assert final_manifest["current_state"] == "certified_done"
    assert Path(final_manifest["certification_record_path"]).is_file()
    assert final_manifest["certification_status"] == "passed"


def test_cycle_runner_blocks_when_pqx_output_artifact_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, manifest_path = _manifest(tmp_path, state="execution_ready")

    def _bad_handoff(**_: object) -> dict:
        return {
            "report_path": str(tmp_path / "missing_execution_report.json"),
            "report_payload": {
                "started_at": "2026-03-30T00:00:00Z",
                "completed_at": "2026-03-30T00:01:00Z",
            },
            "pqx_result": {"status": "complete", "result": str(tmp_path / "missing.result.json")},
            "pqx_result_payload": {},
        }

    monkeypatch.setattr(cycle_runner, "handoff_to_pqx", _bad_handoff)
    result = cycle_runner.run_cycle(manifest_path)

    assert result["status"] == "blocked"
    assert "pqx handoff failed" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_on_invalid_execution_report(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="execution_in_progress")

    bad_report = tmp_path / "bad_execution_report.json"
    _write(bad_report, {"artifact_type": "execution_report_artifact"})
    manifest["execution_report_paths"] = [str(bad_report)]
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "failed schema validation" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_on_failed_or_missing_certification(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="certification_pending")
    manifest["done_certification_input_refs"] = {}
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "done certification handoff failed" in " ".join(result["blocking_issues"])


def test_cycle_runner_deterministic_replay_for_same_inputs(tmp_path: Path) -> None:
    report = _load(_REPO_ROOT / "contracts" / "examples" / "execution_report_artifact.json")
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    for run_dir in (first_dir, second_dir):
        manifest, manifest_path = _manifest(run_dir, state="execution_in_progress")
        report_path = run_dir / "execution_report.json"
        _write(report_path, report)
        manifest["execution_report_paths"] = [str(report_path)]
        _write(manifest_path, manifest)

    first_result = cycle_runner.run_cycle(first_dir / "cycle_manifest.json")
    second_result = cycle_runner.run_cycle(second_dir / "cycle_manifest.json")

    assert (first_result["status"], first_result["next_state"], first_result["next_action"]) == (
        second_result["status"],
        second_result["next_state"],
        second_result["next_action"],
    )
