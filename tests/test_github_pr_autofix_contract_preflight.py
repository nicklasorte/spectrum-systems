import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.github_pr_autofix_contract_preflight import (
    ContractPreflightAutofixError,
    build_preflight_block_diagnosis_record,
    build_preflight_repair_plan_record,
    run_preflight_block_autorepair,
)


def _write_base_artifacts(tmp_path: Path, *, strategy: str = "BLOCK", report_overrides: dict | None = None) -> Path:
    out = tmp_path / "outputs" / "contract_preflight"
    out.mkdir(parents=True, exist_ok=True)
    result = {
        "control_signal": {"strategy_gate_decision": strategy},
        "generated_at": "2026-04-13T00:00:00Z",
    }
    report = {
        "missing_required_surface": [],
        "changed_path_detection": {"pqx_required_context_enforcement": {"status": "block"}},
        "control_surface_gap_blocking": False,
        "trust_spine_evidence_cohesion": None,
        "producer_failures": [],
        "consumer_failures": [],
    }
    if report_overrides:
        report.update(report_overrides)
    (out / "contract_preflight_result_artifact.json").write_text(json.dumps(result), encoding="utf-8")
    (out / "contract_preflight_report.json").write_text(json.dumps(report), encoding="utf-8")
    return out


def test_diagnosis_fails_closed_when_preflight_artifact_missing(tmp_path: Path) -> None:
    out = tmp_path / "outputs" / "contract_preflight"
    out.mkdir(parents=True)
    with pytest.raises(ContractPreflightAutofixError, match="missing_required_input"):
        run_preflight_block_autorepair(
            repo_root=tmp_path,
            output_dir=out,
            base_ref="base",
            head_ref="head",
            execution_context="pqx_governed",
            pqx_wrapper_path=out / "preflight_pqx_task_wrapper.json",
            authority_evidence_ref="artifact",
            same_repo_write_allowed=True,
            command_runner=lambda cmd, cwd: None,  # type: ignore[arg-type]
        )


def test_diagnosis_fails_closed_when_block_reason_unknown(tmp_path: Path) -> None:
    out = _write_base_artifacts(tmp_path, report_overrides={"changed_path_detection": {}, "consumer_failures": [], "producer_failures": []})
    with pytest.raises(ContractPreflightAutofixError, match="unknown_block_reason"):
        run_preflight_block_autorepair(
            repo_root=tmp_path,
            output_dir=out,
            base_ref="base",
            head_ref="head",
            execution_context="pqx_governed",
            pqx_wrapper_path=out / "preflight_pqx_task_wrapper.json",
            authority_evidence_ref="artifact",
            same_repo_write_allowed=True,
            command_runner=lambda cmd, cwd: None,  # type: ignore[arg-type]
        )


def test_bounded_repair_plan_creation_known_category() -> None:
    diagnosis = build_preflight_block_diagnosis_record(
        report={"missing_required_surface": ["x"]},
        preflight_artifact={"control_signal": {"strategy_gate_decision": "BLOCK"}, "generated_at": "2026"},
    )
    plan = build_preflight_repair_plan_record(diagnosis_record=diagnosis)
    assert plan["repair_category"] == "missing_required_surface_mapping"
    assert "contracts/standards-manifest.json" in plan["allowed_paths"]


def test_repair_scope_is_bounded_to_declared_paths() -> None:
    diagnosis = {
        "artifact_type": "preflight_block_diagnosis_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "diagnosis_id": "diag-1",
        "strategy_gate_decision": "BLOCK",
        "repair_category": "missing_preflight_wrapper_or_authority_linkage",
        "reason_codes": ["x"],
    }
    plan = build_preflight_repair_plan_record(diagnosis_record=diagnosis)
    assert plan["allowed_paths"] == [
        "outputs/contract_preflight/preflight_pqx_task_wrapper.json",
        "outputs/contract_preflight/preflight_changed_path_resolution.json",
    ]


def test_validation_replay_required_before_success(tmp_path: Path) -> None:
    out = _write_base_artifacts(tmp_path)

    class _Res:
        def __init__(self, command, returncode):
            self.command = command
            self.returncode = returncode

    calls = []

    def _runner(cmd, cwd):
        calls.append(cmd)
        if "pytest" in cmd:
            return _Res(cmd, 1)
        return _Res(cmd, 0)

    with pytest.raises(ContractPreflightAutofixError, match="validation_replay_failed"):
        run_preflight_block_autorepair(
            repo_root=tmp_path,
            output_dir=out,
            base_ref="base",
            head_ref="head",
            execution_context="pqx_governed",
            pqx_wrapper_path=out / "preflight_pqx_task_wrapper.json",
            authority_evidence_ref="artifact",
            same_repo_write_allowed=True,
            command_runner=_runner,
        )
    assert any("pytest" in cmd for cmd in calls)


def test_rerun_preflight_required_and_blocks_when_still_block(tmp_path: Path) -> None:
    out = _write_base_artifacts(tmp_path)

    class _Res:
        def __init__(self, command, returncode):
            self.command = command
            self.returncode = returncode

    def _runner(cmd, cwd):
        if "run_contract_preflight.py" in cmd:
            return _Res(cmd, 2)
        return _Res(cmd, 0)

    with pytest.raises(ContractPreflightAutofixError, match="preflight_rerun_blocked_or_failed"):
        run_preflight_block_autorepair(
            repo_root=tmp_path,
            output_dir=out,
            base_ref="base",
            head_ref="head",
            execution_context="pqx_governed",
            pqx_wrapper_path=out / "preflight_pqx_task_wrapper.json",
            authority_evidence_ref="artifact",
            same_repo_write_allowed=True,
            command_runner=_runner,
        )


def test_no_mutation_allowed_for_fork_or_unsafe_context(tmp_path: Path) -> None:
    out = _write_base_artifacts(tmp_path)
    with pytest.raises(ContractPreflightAutofixError, match="unsafe_context_fork_or_external_repo"):
        run_preflight_block_autorepair(
            repo_root=tmp_path,
            output_dir=out,
            base_ref="base",
            head_ref="head",
            execution_context="pqx_governed",
            pqx_wrapper_path=out / "preflight_pqx_task_wrapper.json",
            authority_evidence_ref="artifact",
            same_repo_write_allowed=False,
        )
