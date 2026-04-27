import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.github_pr_autofix_contract_preflight import (
    ContractPreflightAutofixError,
    build_preflight_block_diagnosis_record,
    build_preflight_repair_plan_record,
    classify_preflight_block,
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
    assert diagnosis["failure_class"] == "internal_preflight_error"


def test_pr_pytest_execution_invariant_is_classified_for_repair(tmp_path: Path) -> None:
    diagnosis = build_preflight_block_diagnosis_record(
        report={
            "invariant_violations": ["PR_PYTEST_EXECUTION_REQUIRED"],
            "normalized_failure": {"failure_class": "test_inventory_regression", "repairable": True},
        },
        preflight_artifact={"control_signal": {"strategy_gate_decision": "BLOCK"}, "generated_at": "2026"},
    )
    assert diagnosis["failure_class"] == "no_tests_discovered"
    assert diagnosis["normalized_failure"]["repairable"] is True
    plan = build_preflight_repair_plan_record(diagnosis_record=diagnosis)
    assert plan["eligibility_decision"] == "auto_repair_allowed"


def test_preflight_pass_without_execution_invariant_is_classified_for_repair() -> None:
    diagnosis = build_preflight_block_diagnosis_record(
        report={
            "invariant_violations": ["PREFLIGHT_PASS_WITHOUT_PYTEST_EXECUTION"],
            "normalized_failure": {"failure_class": "test_inventory_regression", "repairable": True},
        },
        preflight_artifact={"control_signal": {"strategy_gate_decision": "BLOCK"}, "generated_at": "2026"},
    )
    assert diagnosis["failure_class"] == "no_tests_discovered"
    assert diagnosis["reason_codes"] == ["PREFLIGHT_PASS_WITHOUT_PYTEST_EXECUTION"]


def test_pytest_execution_record_required_invariant_is_classified_for_repair() -> None:
    diagnosis = build_preflight_block_diagnosis_record(
        report={
            "invariant_violations": ["PR_PYTEST_EXECUTION_RECORD_REQUIRED"],
            "normalized_failure": {"failure_class": "test_inventory_regression", "repairable": True},
        },
        preflight_artifact={"control_signal": {"strategy_gate_decision": "BLOCK"}, "generated_at": "2026"},
    )
    assert diagnosis["failure_class"] == "no_tests_discovered"
    assert diagnosis["reason_codes"] == ["PR_PYTEST_EXECUTION_RECORD_REQUIRED"]


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
    outcome = json.loads((out / "preflight_recovery_outcome_record.json").read_text(encoding="utf-8"))
    assert outcome["final_decision"] == "blocked_repair_failed"
    assert outcome["repair_attempted"] is True
    assert outcome["repair_inapplicable_reason"] is None


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
    assert outcome["final_decision"] == "blocked_repair_failed"
    result = json.loads((out / "preflight_repair_result_record.json").read_text(encoding="utf-8"))
    assert result["terminal_state"] == "blocked_repair_failed"


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
                        "pytest_execution_record_ref": "outputs/contract_preflight/pytest_execution_record.json",
                        "pytest_selection_integrity_result_ref": "outputs/contract_preflight/pytest_selection_integrity_result.json",
                        "pytest_selection_integrity": {"selection_integrity_decision": "ALLOW"},
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
    assert result["recovery_outcome"]["final_decision"] == "passed_after_auto_repair"
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
    assert outcome["final_decision"] == "blocked_repair_not_applicable"
    assert outcome["repair_invoked"] is False
    assert outcome["repair_attempted"] is False
    assert outcome["repair_inapplicable_reason"] == "auto_repair_forbidden_by_policy"


def test_contract_mismatch_with_empty_repair_plan_is_blocked_not_applicable(tmp_path: Path) -> None:
    out = _write_base_artifacts(
        tmp_path,
        report_overrides={
            "missing_required_surface": [
                {"path": "docs/architecture/system_registry.md", "reason": "missing deterministic mapping"},
            ],
            "changed_path_detection": {},
        },
    )
    with pytest.raises(ContractPreflightAutofixError, match="repair_plan_not_applicable:empty_repair_plan"):
        run_preflight_block_autorepair(
            repo_root=tmp_path,
            output_dir=out,
            base_ref="base",
            head_ref="head",
            execution_context="pqx_governed",
            pqx_wrapper_path=out / "preflight_pqx_task_wrapper.json",
            authority_evidence_ref="artifact",
            same_repo_write_allowed=True,
            command_runner=lambda cmd, cwd: type("Res", (), {"command": cmd, "returncode": 0})(),
        )
    outcome = json.loads((out / "preflight_recovery_outcome_record.json").read_text(encoding="utf-8"))
    assert outcome["final_decision"] == "blocked_repair_not_applicable"
    assert outcome["repair_attempted"] is False
    assert outcome["repair_inapplicable_reason"] == "empty_repair_plan"


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
                json.dumps({"control_signal": {"strategy_gate_decision": "ALLOW"}, "generated_at": "2026-04-13T00:00:00Z", "pytest_execution_record_ref": "outputs/contract_preflight/pytest_execution_record.json", "pytest_selection_integrity_result_ref": "outputs/contract_preflight/pytest_selection_integrity_result.json", "pytest_selection_integrity": {"selection_integrity_decision": "ALLOW"}}),
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
    assert result["recovery_outcome"]["final_decision"] == "passed_after_auto_repair"


def test_classification_distinguishes_missing_refs_reason() -> None:
    failure_class, reason_codes = classify_preflight_block(
        report={"changed_path_detection": {"ref_context": {"reason_code": "missing_refs"}}}
    )
    assert failure_class == "missing_required_artifact"
    assert reason_codes == ["missing_refs"]


def test_classification_distinguishes_unsupported_event_context_reason() -> None:
    failure_class, reason_codes = classify_preflight_block(
        report={"changed_path_detection": {"ref_context": {"reason_code": "unsupported_event_context"}}}
    )
    assert failure_class == "internal_preflight_error"
    assert reason_codes == ["unsupported_event_context"]


def test_classification_distinguishes_malformed_ref_context_reason() -> None:
    failure_class, reason_codes = classify_preflight_block(
        report={"changed_path_detection": {"ref_context": {"reason_code": "malformed_ref_context"}}}
    )
    assert failure_class == "invalid_wrapper"
    assert reason_codes == ["malformed_ref_context"]


def test_classification_distinguishes_contract_mismatch_from_bad_ref_resolution() -> None:
    failure_class, reason_codes = classify_preflight_block(
        report={
            "missing_required_surface": [{"path": "contracts/schemas/x.schema.json", "reason": "none"}],
            "invariant_violations": ["contract_mismatch_from_bad_ref_resolution"],
        }
    )
    assert failure_class == "contract_mismatch"
    assert reason_codes == ["contract_mismatch_from_bad_ref_resolution"]


def test_classification_maps_preflight_runtime_exception_reason() -> None:
    failure_class, reason_codes = classify_preflight_block(
        report={"invariant_violations": ["preflight_runtime_exception"]}
    )
    assert failure_class == "internal_preflight_error"
    assert reason_codes == ["preflight_runtime_exception"]


def test_repair_pipeline_failure_preserves_original_reason_codes(tmp_path: Path) -> None:
    out = _write_base_artifacts(
        tmp_path,
        report_overrides={
            "changed_path_detection": {"ref_context": {"reason_code": "missing_refs"}},
        },
    )

    class _Res:
        def __init__(self, command, returncode):
            self.command = command
            self.returncode = returncode

    def _runner(cmd, cwd):
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

    outcome = json.loads((out / "preflight_recovery_outcome_record.json").read_text(encoding="utf-8"))
    assert "missing_refs" in outcome["reason_codes"]
    assert "repair_pipeline_failure" in outcome["reason_codes"]


def test_diagnosable_push_ref_failure_does_not_emit_human_escalation(tmp_path: Path) -> None:
    out = _write_base_artifacts(
        tmp_path,
        report_overrides={
            "changed_path_detection": {"ref_context": {"reason_code": "missing_refs"}},
        },
    )

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
            command_runner=lambda cmd, cwd: type("Res", (), {"command": cmd, "returncode": 1 if "pytest" in cmd else 0})(),
        )

    assert not (out / "preflight_human_escalation_record.json").exists()


def test_classification_deterministic_for_same_push_inputs() -> None:
    report = {"changed_path_detection": {"ref_context": {"reason_code": "missing_refs"}}}
    first = classify_preflight_block(report=report)
    second = classify_preflight_block(report=report)
    assert first == second


def test_classify_preflight_block_reports_precise_test_inventory_failure() -> None:
    failure_class, reason_codes = classify_preflight_block(
        report={
            "test_inventory_integrity": {
                "failure_class": "unexpected_test_inventory_regression",
                "status": "failed",
                "blocking": True,
            }
        }
    )
    assert failure_class == "unexpected_test_inventory_regression"
    assert reason_codes == ["unexpected_test_inventory_regression"]


def test_preflight_test_inventory_failure_is_auto_repairable_and_bounded() -> None:
    plan = build_preflight_repair_plan_record(
        diagnosis_record={
            "artifact_type": "preflight_block_diagnosis_record",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "diagnosis_id": "diag-2",
            "strategy_gate_decision": "BLOCK",
            "failure_class": "unexpected_test_inventory_regression",
            "reason_codes": ["unexpected_test_inventory_regression"],
            "root_cause_summary": "inventory drift",
        }
    )
    assert plan["eligibility_decision"] == "auto_repair_allowed"
    assert "docs/governance/pytest_pr_inventory_baseline.json" in plan["allowed_paths"]


def test_selection_integrity_missing_artifact_classifies_repairable() -> None:
    diagnosis = build_preflight_block_diagnosis_record(
        report={
            "invariant_violations": ["PYTEST_SELECTION_ARTIFACT_MISSING"],
            "normalized_failure": {"failure_class": "test_inventory_regression", "repairable": True},
        },
        preflight_artifact={"control_signal": {"strategy_gate_decision": "BLOCK"}, "generated_at": "2026"},
    )
    assert diagnosis["failure_class"] == "pytest_selection_missing"
    plan = build_preflight_repair_plan_record(diagnosis_record=diagnosis)
    assert plan["eligibility_decision"] == "auto_repair_allowed"


def test_selection_integrity_mismatch_classifies_non_repairable() -> None:
    diagnosis = build_preflight_block_diagnosis_record(
        report={
            "invariant_violations": ["PYTEST_SELECTION_MISMATCH"],
            "normalized_failure": {"failure_class": "test_inventory_regression", "repairable": False},
        },
        preflight_artifact={"control_signal": {"strategy_gate_decision": "BLOCK"}, "generated_at": "2026"},
    )
    assert diagnosis["failure_class"] == "pytest_selection_mismatch"
    plan = build_preflight_repair_plan_record(diagnosis_record=diagnosis)
    assert plan["eligibility_decision"] != "auto_repair_allowed"


def test_pr_selection_integrity_required_invariant_classifies_as_selection_missing() -> None:
    diagnosis = build_preflight_block_diagnosis_record(
        report={
            "invariant_violations": ["PR_PYTEST_SELECTION_INTEGRITY_REQUIRED"],
            "normalized_failure": {"failure_class": "test_inventory_regression", "repairable": True},
        },
        preflight_artifact={"control_signal": {"strategy_gate_decision": "BLOCK"}, "generated_at": "2026"},
    )
    assert diagnosis["failure_class"] == "pytest_selection_missing"


def test_pytest_selection_diagnostic_names_unmatched_paths_and_recommended_locations() -> None:
    """When a pytest_selection_* failure is classified, the diagnosis record
    must surface the unmatched changed files, the surface rules that were
    attempted, and the registry locations to update — so the next operator can
    repair without re-tracing the runtime.
    """
    diagnosis = build_preflight_block_diagnosis_record(
        report={
            "invariant_violations": [
                "PR_PYTEST_SELECTION_INTEGRITY_REQUIRED",
                "PYTEST_REQUIRED_TARGETS_MISSING",
            ],
            "normalized_failure": {
                "failure_class": "test_inventory_regression",
                "repairable": True,
            },
            "changed_path_detection": {
                "changed_paths_resolved": [
                    ".github/workflows/example-workflow.yml",
                ],
            },
            "evaluation_classification": [
                {
                    "path": ".github/workflows/example-workflow.yml",
                    "classification": "no_applicable_contract_surface",
                    "reason": "path does not map to governed contract surface",
                    "requires_evaluation": False,
                    "surface": "other",
                },
            ],
            "pytest_selection_integrity": {
                "selected_test_targets": [],
                "missing_required_targets": [],
            },
        },
        preflight_artifact={
            "control_signal": {"strategy_gate_decision": "BLOCK"},
            "generated_at": "2026",
        },
    )
    assert diagnosis["failure_class"] == "pytest_selection_missing"
    diagnostic = diagnosis.get("pytest_selection_diagnostic")
    assert isinstance(diagnostic, dict)
    assert ".github/workflows/example-workflow.yml" in diagnostic["unmatched_changed_paths"]
    locations = diagnostic["recommended_mapping_locations"]
    assert any("pytest_pr_selection_integrity_policy.json" in loc for loc in locations)
    assert any("preflight_required_surface_test_overrides.json" in loc for loc in locations)
    assert any("_REQUIRED_SURFACE_TEST_OVERRIDES" in loc for loc in locations)
    assert any("_is_forced_evaluation_surface" in loc for loc in locations)


def test_pytest_selection_diagnostic_only_emitted_for_selection_failure_classes() -> None:
    """Non-pytest-selection failures must not include the diagnostic — schema
    must allow the field but the producer must not surface it for unrelated
    failure classes.
    """
    diagnosis = build_preflight_block_diagnosis_record(
        report={"missing_required_surface": ["x"]},
        preflight_artifact={"control_signal": {"strategy_gate_decision": "BLOCK"}, "generated_at": "2026"},
    )
    assert diagnosis["failure_class"] == "contract_mismatch"
    assert "pytest_selection_diagnostic" not in diagnosis
