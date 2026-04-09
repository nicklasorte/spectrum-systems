from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.orchestration import pqx_handoff_adapter
from tests.helpers_repo_write_lineage import build_valid_repo_write_lineage


def _write(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return str(path)


def test_handoff_to_pqx_forwards_contract_preflight_artifact_path(tmp_path: Path, monkeypatch) -> None:
    result_path = tmp_path / "pqx.result.json"
    _write(
        result_path,
        {
            "schema_version": "1.0.0",
            "run_id": "pqx-slice-test",
            "step_id": "AI-01",
            "execution_status": "success",
            "started_at": "2026-04-01T00:00:00Z",
            "completed_at": "2026-04-01T00:01:00Z",
            "output_text": "ok",
            "error": None,
        },
    )
    preflight_artifact_path = tmp_path / "contract_preflight_result_artifact.json"
    _write(
        preflight_artifact_path,
        {
            "artifact_type": "contract_preflight_result_artifact",
            "schema_version": "1.0.0",
            "preflight_status": "passed",
            "changed_contracts": [],
            "impacted_producers": [],
            "impacted_fixtures": [],
            "impacted_consumers": [],
            "masking_detected": False,
            "recommended_repair_area": [],
            "report_paths": {
                "json_report_path": "outputs/contract_preflight/contract_preflight_report.json",
                "markdown_report_path": "outputs/contract_preflight/contract_preflight_report.md",
            },
            "generated_at": "2026-04-01T00:00:00Z",
            "control_signal": {
                "strategy_gate_decision": "ALLOW",
                "rationale": "passed",
                "changed_path_detection_mode": "base_head_diff",
                "degraded_detection": False,
            },
            "trace": {
                "producer": "scripts/run_contract_preflight.py",
                "policy_version": "1.0.0",
                "refs_attempted": ["origin/main..HEAD"],
                "fallback_used": False,
                "provenance_ref": "contracts/standards-manifest.json",
            },
        },
    )
    request_path = tmp_path / "request.json"
    _write(
        request_path,
        {
            "step_id": "AI-01",
            "roadmap_path": "docs/roadmap/system_roadmap.md",
            "state_path": str(tmp_path / "pqx_state.json"),
            "runs_root": str(tmp_path / "runs"),
            "pqx_output_text": "deterministic pqx output",
            "repo_mutation_requested": False,
            "contract_preflight_result_artifact_path": str(preflight_artifact_path),
        },
    )

    captured: dict[str, object] = {}

    def _fake_run_pqx_slice(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "status": "complete",
            "run_id": "pqx-slice-test",
            "request": str(tmp_path / "runs" / "request.json"),
            "result": str(result_path),
            "slice_execution_record": str(tmp_path / "runs" / "slice_execution_record.json"),
            "done_certification_record": str(tmp_path / "runs" / "done_certification_record.json"),
            "pqx_slice_audit_bundle": str(tmp_path / "runs" / "pqx_slice_audit_bundle.json"),
        }

    monkeypatch.setattr(pqx_handoff_adapter, "run_pqx_slice", _fake_run_pqx_slice)

    reports_root = tmp_path / "reports"
    handoff = pqx_handoff_adapter.handoff_to_pqx(
        cycle_id="cycle-test",
        request_path=request_path,
        reports_root=reports_root,
    )

    assert handoff["report_payload"]["execution_status"] == "succeeded"
    assert captured["contract_preflight_result_artifact_path"] == preflight_artifact_path


def test_handoff_to_pqx_uses_none_when_preflight_artifact_not_provided(tmp_path: Path, monkeypatch) -> None:
    result_path = tmp_path / "pqx.result.json"
    _write(
        result_path,
        {
            "schema_version": "1.0.0",
            "run_id": "pqx-slice-test",
            "step_id": "AI-01",
            "execution_status": "success",
            "started_at": "2026-04-01T00:00:00Z",
            "completed_at": "2026-04-01T00:01:00Z",
            "output_text": "ok",
            "error": None,
        },
    )
    request_path = tmp_path / "request.json"
    _write(
        request_path,
        {
            "step_id": "AI-01",
            "roadmap_path": "docs/roadmap/system_roadmap.md",
            "state_path": str(tmp_path / "pqx_state.json"),
            "runs_root": str(tmp_path / "runs"),
            "pqx_output_text": "deterministic pqx output",
            "repo_mutation_requested": False,
        },
    )

    captured: dict[str, object] = {}

    def _fake_run_pqx_slice(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "status": "complete",
            "run_id": "pqx-slice-test",
            "request": str(tmp_path / "runs" / "request.json"),
            "result": str(result_path),
            "slice_execution_record": str(tmp_path / "runs" / "slice_execution_record.json"),
            "done_certification_record": str(tmp_path / "runs" / "done_certification_record.json"),
            "pqx_slice_audit_bundle": str(tmp_path / "runs" / "pqx_slice_audit_bundle.json"),
        }

    monkeypatch.setattr(pqx_handoff_adapter, "run_pqx_slice", _fake_run_pqx_slice)

    pqx_handoff_adapter.handoff_to_pqx(
        cycle_id="cycle-test",
        request_path=request_path,
        reports_root=tmp_path / "reports",
    )

    assert captured["contract_preflight_result_artifact_path"] is None


def _repo_write_lineage_payload() -> dict[str, object]:
    lineage = build_valid_repo_write_lineage(request_id="req-cycle-1", trace_id="trace-cycle-repo-write")
    return {
        "repo_mutation_requested": True,
        "trace_id": "trace-cycle-repo-write",
        **lineage,
    }


def test_handoff_to_pqx_repo_write_fails_closed_without_admission_lineage(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    _write(
        request_path,
        {
            "step_id": "AI-01",
            "roadmap_path": "docs/roadmap/system_roadmap.md",
            "state_path": str(tmp_path / "pqx_state.json"),
            "runs_root": str(tmp_path / "runs"),
            "pqx_output_text": "deterministic pqx output",
            "repo_mutation_requested": True,
        },
    )

    with pytest.raises(pqx_handoff_adapter.PQXHandoffError, match="repo-write handoff rejected"):
        pqx_handoff_adapter.handoff_to_pqx(
            cycle_id="cycle-test",
            request_path=request_path,
            reports_root=tmp_path / "reports",
        )


def test_handoff_to_pqx_repo_write_succeeds_with_valid_admission_lineage(tmp_path: Path, monkeypatch) -> None:
    result_path = tmp_path / "pqx.result.json"
    _write(
        result_path,
        {
            "schema_version": "1.0.0",
            "run_id": "pqx-slice-test",
            "step_id": "AI-01",
            "execution_status": "success",
            "started_at": "2026-04-01T00:00:00Z",
            "completed_at": "2026-04-01T00:01:00Z",
            "output_text": "ok",
            "error": None,
        },
    )
    request_payload = {
        "step_id": "AI-01",
        "roadmap_path": "docs/roadmap/system_roadmap.md",
        "state_path": str(tmp_path / "pqx_state.json"),
        "runs_root": str(tmp_path / "runs"),
        "pqx_output_text": "deterministic pqx output",
        **_repo_write_lineage_payload(),
    }
    request_path = tmp_path / "request.json"
    _write(request_path, request_payload)

    captured: dict[str, object] = {}

    def _fake_run_pqx_slice(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "status": "complete",
            "run_id": "pqx-slice-test",
            "request": str(tmp_path / "runs" / "request.json"),
            "result": str(result_path),
        }

    monkeypatch.setattr(pqx_handoff_adapter, "run_pqx_slice", _fake_run_pqx_slice)
    handoff = pqx_handoff_adapter.handoff_to_pqx(
        cycle_id="cycle-test",
        request_path=request_path,
        reports_root=tmp_path / "reports",
    )

    assert handoff["report_payload"]["execution_status"] == "succeeded"
    assert captured["execution_intent"] == "repo_write"
    assert isinstance(captured["repo_write_lineage"], dict)
    assert captured["repo_write_lineage"]["build_admission_record"]["artifact_type"] == "build_admission_record"
