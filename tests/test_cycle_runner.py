from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.orchestration.cycle_runner import run_cycle


def _write(path: Path, payload: dict) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _manifest(tmp_path: Path) -> dict:
    roadmap_path = tmp_path / "system_roadmap.md"
    roadmap_path.write_text("# roadmap\n", encoding="utf-8")
    review_path = tmp_path / "roadmap_review.json"
    review = {
        "artifact_id": "r1",
        "artifact_type": "roadmap_review_artifact",
        "schema_version": "1.0.0",
        "cycle_id": "cycle-test",
        "roadmap_path": str(roadmap_path),
        "reviewer": "claude",
        "approval_state": "approved",
        "findings": [],
        "reviewed_at": "2026-03-30T00:00:00Z",
    }
    _write(review_path, review)

    pqx_request = tmp_path / "pqx_request.json"
    pqx_request.write_text("{}", encoding="utf-8")

    base = {
        "cycle_id": "cycle-test",
        "current_state": "roadmap_under_review",
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
        "pqx_execution_request_path": str(pqx_request),
        "done_certification_input_refs": {
            "replay_result_ref": "a",
            "regression_result_ref": "b",
            "certification_pack_ref": "c",
            "error_budget_ref": "d",
            "policy_ref": "e",
        },
        "updated_at": "2026-03-30T00:00:00Z",
    }
    return base


def test_cycle_runner_next_step_for_approved_roadmap(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    path = tmp_path / "cycle_manifest.json"
    _write(path, manifest)

    result = run_cycle(path)
    assert result["next_state"] == "roadmap_approved"
    assert result["next_action"] == "lock_approved_roadmap"


def test_cycle_runner_blocks_when_required_artifact_missing(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["roadmap_review_artifact_paths"] = [str(tmp_path / "missing.json")]
    path = tmp_path / "cycle_manifest.json"
    _write(path, manifest)

    result = run_cycle(path)
    assert result["status"] == "blocked"
    assert "missing required artifact" in " ".join(result["blocking_issues"])


def test_roadmap_approval_required_before_execution_ready(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["current_state"] = "roadmap_under_review"
    manifest["roadmap_approval_state"] = "pending"
    review_path = Path(manifest["roadmap_review_artifact_paths"][0])
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    payload["approval_state"] = "changes_requested"
    review_path.write_text(json.dumps(payload), encoding="utf-8")
    path = tmp_path / "cycle_manifest.json"
    _write(path, manifest)

    result = run_cycle(path)
    assert result["status"] == "blocked"
    assert "roadmap approval required" in " ".join(result["blocking_issues"])


def test_certification_required_for_certified_done(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["current_state"] = "certification_pending"
    path = tmp_path / "cycle_manifest.json"
    _write(path, manifest)

    result = run_cycle(path)
    assert result["next_state"] == "certification_pending"
    assert result["next_action"] == "invoke_done_certification"

    cert_path = tmp_path / "done_certification_record.json"
    cert_path.write_text("{}", encoding="utf-8")
    manifest["certification_record_path"] = str(cert_path)
    _write(path, manifest)

    result = run_cycle(path)
    assert result["next_state"] == "certified_done"
