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
    with pytest.raises(ContractPreflightAutofixError, match="auto_repair_forbidden_escalation_required"):
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
    assert (out / "preflight_block_diagnosis_record.json").exists()
    assert (out / "preflight_repair_plan_record.json").exists()
    assert (out / "preflight_repair_result_record.json").exists()
    assert (out / "preflight_recovery_outcome_record.json").exists()
    diagnosis = json.loads((out / "preflight_block_diagnosis_record.json").read_text(encoding="utf-8"))
    assert diagnosis["failure_class"] == "unknown_preflight_failure"


def test_bounded_repair_plan_creation_known_category() -> None:
    diagnosis = build_preflight_block_diagnosis_record(
        report={"missing_required_surface": ["x"]},
        preflight_artifact={"control_signal": {"strategy_gate_decision": "BLOCK"}, "generated_at": "2026"},
    )
    plan = build_preflight_repair_plan_record(diagnosis_record=diagnosis)
    assert plan["failure_class"] == "contract_mismatch"
    assert plan["eligibility_decision"] == "auto_repair_allowed"
    assert "docs/governance/preflight_required_surface_test_overrides.json" in plan["allowed_paths"]


def test_repair_scope_is_bounded_to_declared_paths() -> None:
    diagnosis = {
        "artifact_type": "preflight_block_diagnosis_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "diagnosis_id": "diag-1",
        "strategy_gate_decision": "BLOCK",
        "failure_class": "invalid_wrapper",
        "reason_codes": ["x"],
        "root_cause_summary": "wrapper missing",
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
        if any("run_contract_preflight.py" in part for part in cmd):
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
    outcome = json.loads((out / "preflight_recovery_outcome_record.json").read_text(encoding="utf-8"))
    assert outcome["final_decision"] == "repaired_but_still_blocked"


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


def test_schema_example_manifest_drift_classified_and_scoped() -> None:
    diagnosis = build_preflight_block_diagnosis_record(
        report={
            "schema_example_failures": [
                {
                    "path": "contracts/examples/system_registry_artifact.json",
                    "error": "minItems",
                }
            ]
        },
        preflight_artifact={"control_signal": {"strategy_gate_decision": "BLOCK"}, "generated_at": "2026"},
    )
    assert diagnosis["failure_class"] == "schema_violation"
    plan = build_preflight_repair_plan_record(diagnosis_record=diagnosis)
    assert plan["apply_automatically"] is True
    assert "contracts/examples" in plan["allowed_paths"]


def test_missing_required_surface_mapping_autorepair_writes_override_file(tmp_path: Path) -> None:
    out = _write_base_artifacts(
        tmp_path,
        report_overrides={
            "missing_required_surface": [
                {
                    "path": "spectrum_systems/modules/runtime/task_registry.py",
                    "reason": "required contract surface changed but no deterministic evaluation target was found",
                }
            ],
            "changed_path_detection": {},
        },
    )
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "test_task_registry_ai_adapter_eval_slice_runner.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")

    class _Res:
        def __init__(self, command, returncode):
            self.command = command
            self.returncode = returncode

    def _runner(cmd, cwd):
        if any("run_contract_preflight.py" in part for part in cmd):
            (out / "contract_preflight_result_artifact.json").write_text(
                json.dumps(
                    {
                        "control_signal": {"strategy_gate_decision": "ALLOW"},
                        "generated_at": "2026-04-13T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
        return _Res(cmd, 0)

    result = run_preflight_block_autorepair(
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
    assert result["repair_result"]["success"] is True
    assert result["recovery_outcome"]["final_decision"] == "repaired_and_passed"
    override_file = tmp_path / "docs" / "governance" / "preflight_required_surface_test_overrides.json"
    assert override_file.exists()


def test_non_repairable_block_emits_recovery_outcome_and_escalates(tmp_path: Path) -> None:
    out = _write_base_artifacts(
        tmp_path,
        report_overrides={
            "trust_spine_evidence_cohesion": {"overall_decision": "BLOCK"},
            "changed_path_detection": {"pqx_required_context_enforcement": {"status": "allow"}},
        },
    )
    with pytest.raises(ContractPreflightAutofixError, match="auto_repair_forbidden_escalation_required"):
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
    outcome = json.loads((out / "preflight_recovery_outcome_record.json").read_text(encoding="utf-8"))
    assert outcome["final_decision"] == "repair_not_permitted"
    assert outcome["repair_invoked"] is False


def test_schema_violation_auto_repair_path_writes_terminal_success_outcome(tmp_path: Path) -> None:
    out = _write_base_artifacts(
        tmp_path,
        report_overrides={
            "schema_example_failures": [{"path": "contracts/examples/system_registry_artifact.json", "error": "schema drift"}],
            "changed_path_detection": {},
        },
    )
    sample = tmp_path / "contracts" / "examples" / "system_registry_artifact.json"
    sample.parent.mkdir(parents=True, exist_ok=True)
    sample.write_text(json.dumps({"systems": []}), encoding="utf-8")

    class _Res:
        def __init__(self, command, returncode):
            self.command = command
            self.returncode = returncode

    def _runner(cmd, cwd):
        if any("run_contract_preflight.py" in part for part in cmd):
            (out / "contract_preflight_result_artifact.json").write_text(
                json.dumps({"control_signal": {"strategy_gate_decision": "ALLOW"}, "generated_at": "2026-04-13T00:00:00Z"}),
                encoding="utf-8",
            )
        return _Res(cmd, 0)

    result = run_preflight_block_autorepair(
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
    assert result["recovery_outcome"]["final_decision"] == "repaired_and_passed"
