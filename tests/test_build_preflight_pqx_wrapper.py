from __future__ import annotations

import json
from pathlib import Path

from scripts import build_preflight_pqx_wrapper as builder
from scripts import run_contract_preflight as preflight


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


def test_wrapper_and_runner_share_canonical_ref_normalizer() -> None:
    assert builder.normalize_preflight_ref_context is preflight.normalize_preflight_ref_context


def _write_minimal_template(tmp_path: Path) -> Path:
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
    return template


def test_null_base_resolves_to_head_parent_and_builds_wrapper(tmp_path: Path, monkeypatch) -> None:
    template = _write_minimal_template(tmp_path)
    out = tmp_path / "out.json"
    monkeypatch.setattr(builder, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(builder, "_is_valid_commit", lambda ref: ref in {"head", "head-parent"})
    monkeypatch.setattr(
        builder,
        "_run_git",
        lambda command: (0, "head-parent", "")
        if command == ["git", "rev-parse", "head^"]
        else (0, "", ""),
    )

    class FakeResult:
        changed_paths = ["scripts/build_preflight_pqx_wrapper.py"]
        changed_path_detection_mode = "base_head_diff"
        resolution_mode = "exact_diff"
        trust_level = "authoritative"
        bounded_runtime = True
        refs_attempted = ["head-parent..head"]
        warnings = []
        insufficient_context = False

    seen: dict[str, str] = {}

    def fake_resolve_changed_paths(**kwargs):
        seen["base_ref"] = kwargs["base_ref"]
        seen["head_ref"] = kwargs["head_ref"]
        return FakeResult()

    monkeypatch.setattr(builder, "resolve_changed_paths", fake_resolve_changed_paths)
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
    rc = builder.main(
        [
            "--event-name",
            "push",
            "--base-ref",
            "0000000000000000000000000000000000000000",
            "--head-ref",
            "head",
            "--template",
            "template.json",
            "--output",
            "out.json",
        ]
    )

    assert rc == 0
    assert seen == {"base_ref": "head-parent", "head_ref": "head"}
    sidecar = json.loads((tmp_path / "preflight_changed_path_resolution.json").read_text(encoding="utf-8"))
    assert sidecar["ref_resolution"]["base_ref_resolution_strategy"] == "head_parent"
    assert sidecar["ref_resolution"]["original_base_ref"] == "0000000000000000000000000000000000000000"
    assert sidecar["ref_resolution"]["effective_base_ref"] == "head-parent"


def test_null_base_uses_merge_base_when_head_parent_unavailable(tmp_path: Path, monkeypatch) -> None:
    template = _write_minimal_template(tmp_path)
    monkeypatch.setattr(builder, "_REPO_ROOT", tmp_path)

    def fake_is_valid_commit(ref: str) -> bool:
        return ref in {"head", "origin/main"}

    monkeypatch.setattr(builder, "_is_valid_commit", fake_is_valid_commit)

    def fake_run_git(command: list[str]) -> tuple[int, str, str]:
        if command == ["git", "rev-parse", "head^"]:
            return 1, "", "no parent"
        if command == ["git", "merge-base", "head", "origin/main"]:
            return 0, "mbase", ""
        return 1, "", "unsupported"

    monkeypatch.setattr(builder, "_run_git", fake_run_git)

    class FakeResult:
        changed_paths = ["contracts/schemas/codex_pqx_task_wrapper.schema.json"]
        changed_path_detection_mode = "base_head_diff"
        resolution_mode = "exact_diff"
        trust_level = "authoritative"
        bounded_runtime = True
        refs_attempted = ["mbase..head"]
        warnings = []
        insufficient_context = False

    captured: dict[str, str] = {}
    monkeypatch.setattr(
        builder,
        "resolve_changed_paths",
        lambda **kwargs: captured.update({"base_ref": kwargs["base_ref"], "head_ref": kwargs["head_ref"]}) or FakeResult(),
    )
    monkeypatch.setattr(
        builder,
        "_write_preflight_hardening_artifacts",
        lambda **_: {"eval": "e", "readiness": "r", "effectiveness": "f", "recurrence": "c", "bundle": "b"},
    )

    rc = builder.main(
        [
            "--event-name",
            "push",
            "--base-ref",
            "0000000000000000000000000000000000000000",
            "--head-ref",
            "head",
            "--template",
            str(template.relative_to(tmp_path)),
            "--output",
            "out.json",
        ]
    )
    assert rc == 0
    assert captured["base_ref"] == "mbase"
    sidecar = json.loads((tmp_path / "preflight_changed_path_resolution.json").read_text(encoding="utf-8"))
    assert sidecar["ref_resolution"]["base_ref_resolution_strategy"] == "merge_base"


def test_null_base_without_parent_or_merge_base_fails_closed_with_explicit_reason(tmp_path: Path, monkeypatch) -> None:
    template = _write_minimal_template(tmp_path)
    monkeypatch.setattr(builder, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(builder, "_is_valid_commit", lambda ref: ref == "head")
    monkeypatch.setattr(builder, "_run_git", lambda command: (1, "", "no parent"))
    monkeypatch.setattr(builder, "resolve_changed_paths", lambda **_: (_ for _ in ()).throw(AssertionError("must not resolve")))

    rc = builder.main(
        [
            "--event-name",
            "push",
            "--base-ref",
            "0000000000000000000000000000000000000000",
            "--head-ref",
            "head",
            "--template",
            str(template.relative_to(tmp_path)),
            "--output",
            "out.json",
        ]
    )
    assert rc == 2
    sidecar = json.loads((tmp_path / "preflight_changed_path_resolution.json").read_text(encoding="utf-8"))
    assert sidecar["failure_reason_code"] == "null_base_unresolved"
    assert "null base could not be resolved" in sidecar["failure_reason"]


def test_non_null_base_remains_unchanged(tmp_path: Path, monkeypatch) -> None:
    template = _write_minimal_template(tmp_path)
    monkeypatch.setattr(builder, "_REPO_ROOT", tmp_path)

    class FakeResult:
        changed_paths = ["docs/review-actions/PLAN-PFX-01-NULL-BASE-PUSH-RESOLUTION-2026-04-27.md"]
        changed_path_detection_mode = "base_head_diff"
        resolution_mode = "exact_diff"
        trust_level = "authoritative"
        bounded_runtime = True
        refs_attempted = ["base..head"]
        warnings = []
        insufficient_context = False

    seen: dict[str, str] = {}
    monkeypatch.setattr(
        builder,
        "resolve_changed_paths",
        lambda **kwargs: seen.update({"base_ref": kwargs["base_ref"], "head_ref": kwargs["head_ref"]}) or FakeResult(),
    )
    monkeypatch.setattr(
        builder,
        "_write_preflight_hardening_artifacts",
        lambda **_: {"eval": "e", "readiness": "r", "effectiveness": "f", "recurrence": "c", "bundle": "b"},
    )

    rc = builder.main(
        [
            "--event-name",
            "push",
            "--base-ref",
            "base",
            "--head-ref",
            "head",
            "--template",
            str(template.relative_to(tmp_path)),
            "--output",
            "out.json",
        ]
    )
    assert rc == 0
    assert seen == {"base_ref": "base", "head_ref": "head"}
    sidecar = json.loads((tmp_path / "preflight_changed_path_resolution.json").read_text(encoding="utf-8"))
    assert sidecar["ref_resolution"]["base_ref_resolution_strategy"] == "as_provided"
