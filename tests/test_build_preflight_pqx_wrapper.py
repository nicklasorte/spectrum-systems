from __future__ import annotations

import json
from pathlib import Path

from scripts import build_preflight_pqx_wrapper as builder


def test_wrapper_builder_writes_changed_paths_and_resolution(tmp_path: Path, monkeypatch) -> None:
    template = tmp_path / "template.json"
    template.write_text(
        json.dumps(
            {
                "artifact_type": "codex_pqx_task_wrapper",
                "changed_paths": [],
                "task_identity": {"run_id": "run-1", "step_id": "AI-01"},
                "governance": {"authority_evidence_ref": None},
                "metadata": {"authority_notes": "test"},
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out.json"

    monkeypatch.setattr(builder, "_REPO_ROOT", tmp_path)

    class FakeResult:
        changed_paths = ["contracts/schemas/a.schema.json"]
        changed_path_detection_mode = "base_head_diff"
        resolution_mode = "exact_diff"
        trust_level = "authoritative"
        bounded_runtime = True
        refs_attempted = ["base..head"]
        warnings = []
        insufficient_context = False

    monkeypatch.setattr(builder, "resolve_changed_paths", lambda **_: FakeResult())
    monkeypatch.setattr(
        builder,
        "_write_preflight_hardening_artifacts",
        lambda **_: {
            "eval": "outputs/contract_preflight/preflight.pqx_execution_eval_result.json",
            "readiness": "outputs/contract_preflight/preflight.pqx_execution_readiness_record.json",
            "effectiveness": "outputs/contract_preflight/preflight.pqx_execution_effectiveness_record.json",
            "recurrence": "outputs/contract_preflight/preflight.pqx_execution_recurrence_record.json",
            "bundle": "outputs/contract_preflight/preflight.pqx_execution_bundle.json",
        },
    )

    rc = builder.main([
        "--base-ref",
        "base",
        "--head-ref",
        "head",
        "--template",
        str(template.relative_to(tmp_path)),
        "--output",
        str(out.relative_to(tmp_path)),
    ])
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["changed_paths"] == ["contracts/schemas/a.schema.json"]
    assert payload["governance"]["authority_evidence_ref"] == "artifacts/pqx_runs/preflight.pqx_slice_execution_record.json"
    assert "changed_path_resolution" not in payload
    sidecar = json.loads((tmp_path / "preflight_changed_path_resolution.json").read_text(encoding="utf-8"))
    assert sidecar["trust_level"] == "authoritative"


def test_wrapper_builder_blocks_on_insufficient_context(tmp_path: Path, monkeypatch) -> None:
    template = tmp_path / "template.json"
    template.write_text(
        json.dumps(
            {
                "artifact_type": "codex_pqx_task_wrapper",
                "changed_paths": [],
                "task_identity": {"run_id": "run-1", "step_id": "AI-01"},
                "governance": {"authority_evidence_ref": None},
                "metadata": {"authority_notes": "test"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(builder, "_REPO_ROOT", tmp_path)

    class FakeResult:
        changed_paths = []
        changed_path_detection_mode = "detection_failed_no_governed_paths"
        resolution_mode = "insufficient"
        trust_level = "insufficient"
        bounded_runtime = False
        refs_attempted = []
        warnings = []
        insufficient_context = True

    monkeypatch.setattr(builder, "resolve_changed_paths", lambda **_: FakeResult())
    rc = builder.main(["--base-ref", "base", "--head-ref", "head", "--template", "template.json"])
    assert rc == 2
