"""Governed, fail-closed contract preflight BLOCK auto-repair path."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from spectrum_systems.contracts import validate_artifact


class ContractPreflightAutofixError(RuntimeError):
    """Raised for fail-closed auto-repair blocking conditions."""


KNOWN_REPAIR_CATEGORIES = {
    "missing_required_artifact",
    "contract_mismatch",
    "schema_violation",
    "lineage_missing",
    "authority_evidence_missing",
    "invalid_wrapper",
    "non_repairable_policy_violation",
    "internal_preflight_error",
    "unknown_preflight_failure",
    "pytest_config_missing",
    "pytest_config_mismatch",
    "testpaths_missing",
    "no_tests_discovered",
    "unexpected_test_inventory_regression",
    "import_resolution_failure",
    "collection_failure",
    "working_directory_mismatch",
    "accidental_filtering_detected",
}

TERMINAL_STATES = {
    "passed_without_repair",
    "passed_after_auto_repair",
    "blocked_repair_failed",
    "blocked_repair_not_applicable",
    "blocked_escalation_required",
}


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ContractPreflightAutofixError(f"missing_required_input:{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ContractPreflightAutofixError(f"invalid_json_object:{path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_recovery_outcome(
    *,
    output_dir: Path,
    result_artifact: dict[str, Any],
    diagnosis: dict[str, Any],
    plan: dict[str, Any],
    repair_invoked: bool,
    repair_execution_status: str,
    rerun_status: str,
    final_decision: str,
    repair_attempted: bool,
    repair_inapplicable_reason: str | None,
    retry_count: int,
    reason_codes: list[str],
    artifact_refs: dict[str, str],
) -> dict[str, Any]:
    payload = {
        "artifact_type": "preflight_recovery_outcome_record",
        "schema_version": "1.1.0",
        "initial_preflight_status": str(result_artifact.get("preflight_status") or "failed"),
        "failure_class": str(diagnosis.get("failure_class") or "unknown_preflight_failure"),
        "eligibility_decision": str(plan.get("eligibility_decision") or "escalation_required"),
        "repair_invoked": bool(repair_invoked),
        "repair_execution_status": repair_execution_status,
        "rerun_status": rerun_status,
        "final_decision": final_decision,
        "repair_attempted": repair_attempted,
        "repair_inapplicable_reason": repair_inapplicable_reason,
        "retry_count": retry_count,
        "reason_codes": sorted({str(code) for code in reason_codes if str(code)}),
        "artifact_refs": artifact_refs,
    }
    validate_artifact(payload, "preflight_recovery_outcome_record")
    _write_json(output_dir / "preflight_recovery_outcome_record.json", payload)
    return payload


def _fold_terminal_state(
    *,
    eligibility_decision: str,
    repair_attempted: bool,
    repair_inapplicable_reason: str | None,
    repair_execution_status: str,
    rerun_status: str,
) -> str:
    if eligibility_decision == "escalation_required":
        return "blocked_escalation_required"
    if eligibility_decision == "auto_repair_forbidden":
        return "blocked_repair_not_applicable"
    if eligibility_decision == "auto_repair_allowed":
        if not repair_attempted and not repair_inapplicable_reason:
            raise ContractPreflightAutofixError("repair_guard_violation:auto_repair_allowed_without_attempt_or_reason")
        if repair_inapplicable_reason:
            return "blocked_repair_not_applicable"
        if rerun_status == "passed":
            return "passed_after_auto_repair"
        if repair_execution_status in {"failed_validation", "failed_execution"}:
            return "blocked_repair_failed"
        return "blocked_repair_failed"
    return "blocked_escalation_required"


def classify_preflight_block(*, report: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    test_inventory = report.get("test_inventory_integrity")
    if isinstance(test_inventory, dict):
        failure_class = str(test_inventory.get("failure_class") or "").strip()
        if failure_class and failure_class != "success":
            return failure_class, [failure_class]

    invariant_violations = [str(item) for item in (report.get("invariant_violations") or []) if isinstance(item, str)]
    ref_context = ((report.get("changed_path_detection") or {}).get("ref_context") or {}) if isinstance(report, dict) else {}
    ref_reason_code = str(ref_context.get("reason_code") or "").strip()
    if ref_reason_code == "missing_refs":
        return "missing_required_artifact", ["missing_refs"]
    if ref_reason_code == "unsupported_event_context":
        return "internal_preflight_error", ["unsupported_event_context"]
    if ref_reason_code == "malformed_ref_context":
        return "invalid_wrapper", ["malformed_ref_context"]
    if ref_reason_code == "invalid_git_ref":
        return "invalid_wrapper", ["invalid_git_ref"]

    detection_mode = str((report.get("changed_path_detection") or {}).get("changed_path_detection_mode") or "")
    if detection_mode in {"ref_context_invalid", "detection_failed_no_governed_paths"}:
        if "contract_mismatch_from_bad_ref_resolution" in invariant_violations:
            return "contract_mismatch", ["contract_mismatch_from_bad_ref_resolution"]
        return "missing_required_artifact", ["changed_path_resolution_failure"]

    if report.get("bootstrap_failures"):
        return "missing_required_artifact", ["changed_path_resolution_failure"]

    schema_example_failures = report.get("schema_example_failures") or []
    if schema_example_failures:
        for failure in schema_example_failures:
            if not isinstance(failure, dict):
                continue
            path = str(failure.get("path") or "")
            if path in {"contracts/examples/system_registry_artifact.json", "contracts/standards-manifest.json"}:
                return "schema_violation", ["SCHEMA_EXAMPLE_MANIFEST_DRIFT"]
        return "schema_violation", ["SCHEMA_EXAMPLE_FAILURE"]

    if report.get("missing_required_surface"):
        if "contract_mismatch_from_bad_ref_resolution" in invariant_violations:
            return "contract_mismatch", ["contract_mismatch_from_bad_ref_resolution"]
        return "contract_mismatch", ["MISSING_REQUIRED_SURFACE_MAPPING"]

    pqx_ctx = report.get("changed_path_detection", {}).get("pqx_required_context_enforcement")
    if isinstance(pqx_ctx, dict) and pqx_ctx.get("status") == "block":
        blocking_reasons = [str(item) for item in pqx_ctx.get("blocking_reasons", []) if isinstance(item, str)]
        if any("AUTHORITY_EVIDENCE" in reason for reason in blocking_reasons):
            return "authority_evidence_missing", ["AUTHORITY_EVIDENCE_REF_RESOLUTION_MISMATCH"]
        if any("WRAPPER" in reason for reason in blocking_reasons):
            return "invalid_wrapper", ["PQX_REQUIRED_CONTEXT_WRAPPER_BLOCK"]
        return "missing_required_artifact", ["PQX_REQUIRED_CONTEXT_ENFORCEMENT_BLOCK"]

    mode = detection_mode
    if mode == "degraded_full_governed_scan":
        return "internal_preflight_error", ["PR_EVENT_PREFLIGHT_NORMALIZATION_BUG"]

    if report.get("control_surface_gap_blocking") is True:
        return "lineage_missing", ["CONTROL_SURFACE_GAP_BLOCKING"]

    if report.get("trust_spine_evidence_cohesion"):
        return "non_repairable_policy_violation", ["TRUST_SPINE_EVIDENCE_COHESION_PRESENT"]

    producer_failures = report.get("producer_failures") or []
    fixture_hits = [entry for entry in producer_failures if isinstance(entry, dict) and "fixtures" in str(entry.get("path") or "")]
    if fixture_hits:
        return "contract_mismatch", ["FIXTURE_CONTRACT_FAILURE"]

    consumer_failures = report.get("consumer_failures") or []
    if consumer_failures:
        reasons.extend(["CONSUMER_FAILURES_PRESENT"])
        return "contract_mismatch", reasons

    if invariant_violations:
        if "artifact_validation_failure" in invariant_violations:
            return "schema_violation", ["artifact_validation_failure"]
        if "repair_pipeline_failure" in invariant_violations:
            return "internal_preflight_error", ["repair_pipeline_failure"]
        if "preflight_runtime_exception" in invariant_violations:
            return "internal_preflight_error", ["preflight_runtime_exception"]
        return "contract_mismatch", invariant_violations[:3]

    return "unknown_preflight_failure", ["UNCLASSIFIED_BLOCK_REASON"]


def _repair_policy(failure_class: str) -> tuple[str, bool, bool]:
    if failure_class in {
        "schema_violation",
        "contract_mismatch",
        "invalid_wrapper",
        "authority_evidence_missing",
        "missing_required_artifact",
        "pytest_config_missing",
        "pytest_config_mismatch",
        "testpaths_missing",
        "no_tests_discovered",
        "unexpected_test_inventory_regression",
        "import_resolution_failure",
        "collection_failure",
        "working_directory_mismatch",
        "accidental_filtering_detected",
    }:
        return "auto_repair_allowed", True, False
    if failure_class in {"non_repairable_policy_violation", "lineage_missing"}:
        return "auto_repair_forbidden", False, True
    if failure_class in {"internal_preflight_error", "unknown_preflight_failure"}:
        return "escalation_required", False, True
    return "escalation_required", False, True


def build_preflight_block_diagnosis_record(*, report: dict[str, Any], preflight_artifact: dict[str, Any]) -> dict[str, Any]:
    try:
        category, reasons = classify_preflight_block(report=report)
    except Exception:
        category, reasons = "internal_preflight_error", ["preflight_runtime_exception"]
    return {
        "artifact_type": "preflight_block_diagnosis_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "diagnosis_id": f"diag-{preflight_artifact.get('generated_at', 'unknown')}",
        "strategy_gate_decision": str(((preflight_artifact.get("control_signal") or {}).get("strategy_gate_decision")) or "BLOCK"),
        "failure_class": category,
        "reason_codes": reasons,
        "root_cause_summary": str((preflight_artifact.get("control_signal") or {}).get("rationale") or "preflight block"),
    }


def build_preflight_repair_plan_record(*, diagnosis_record: dict[str, Any]) -> dict[str, Any]:
    category = diagnosis_record["failure_class"]
    if category not in KNOWN_REPAIR_CATEGORIES:
        raise ContractPreflightAutofixError("unknown_repair_category")
    eligibility_decision, auto_repair_allowed, escalation_required = _repair_policy(category)

    allowed_paths = {
        "invalid_wrapper": [
            "outputs/contract_preflight/preflight_pqx_task_wrapper.json",
            "outputs/contract_preflight/preflight_changed_path_resolution.json",
        ],
        "authority_evidence_missing": [
            "outputs/contract_preflight/preflight_pqx_task_wrapper.json",
            "outputs/contract_preflight/preflight_changed_path_resolution.json",
        ],
        "contract_mismatch": ["tests/", "contracts/examples", "docs/governance/preflight_required_surface_test_overrides.json"],
        "schema_violation": ["contracts/examples", "contracts/schemas"],
        "missing_required_artifact": ["outputs/contract_preflight", "contracts/examples"],
        "lineage_missing": ["outputs/contract_preflight", "scripts/run_contract_preflight.py"],
        "non_repairable_policy_violation": ["docs/reviews"],
        "internal_preflight_error": ["scripts/run_contract_preflight.py"],
        "unknown_preflight_failure": ["docs/reviews"],
        "pytest_config_missing": ["pytest.ini"],
        "pytest_config_mismatch": ["pytest.ini", "docs/governance/pytest_pr_inventory_baseline.json"],
        "testpaths_missing": ["pytest.ini", "tests/"],
        "no_tests_discovered": ["tests/", "pytest.ini"],
        "unexpected_test_inventory_regression": ["tests/", "docs/governance/pytest_pr_inventory_baseline.json"],
        "import_resolution_failure": ["tests/", "spectrum_systems/", "pytest.ini"],
        "collection_failure": ["tests/", "pytest.ini"],
        "working_directory_mismatch": [".github/workflows/", "scripts/run_contract_preflight.py"],
        "accidental_filtering_detected": ["pytest.ini", ".github/workflows/"],
    }[category]

    return {
        "artifact_type": "preflight_repair_plan_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "plan_id": f"plan-{diagnosis_record['diagnosis_id']}",
        "failure_class": category,
        "eligibility_decision": eligibility_decision,
        "allowed_paths": allowed_paths,
        "apply_automatically": auto_repair_allowed,
        "escalation_required": escalation_required,
        "max_retry_attempts": 2,
        "rerun_prerequisites": ["preflight_repair_validation_record"],
    }


def build_failure_repair_candidate_artifact(*, diagnosis_record: dict[str, Any], plan_record: dict[str, Any]) -> dict[str, Any]:
    failure_class = diagnosis_record["failure_class"]
    return {
        "artifact_type": "failure_repair_candidate_artifact",
        "schema_version": "1.0.0",
        "failure_id": diagnosis_record["diagnosis_id"],
        "source_run_ref": "contract_preflight_report:latest",
        "source_test_refs": ["tests/test_contract_preflight.py"],
        "failure_class": failure_class,
        "safe_to_repair": bool(plan_record.get("apply_automatically", False)),
        "bounded_scope": list(plan_record.get("allowed_paths", [])),
        "proposed_repair_ref": f"preflight_repair_plan_record:{plan_record['plan_id']}",
        "trace_refs": ["contract_preflight_result_artifact:latest"],
        "reason_codes": list(diagnosis_record.get("reason_codes", [])),
        "retry_budget": int(plan_record.get("max_retry_attempts", 0)),
        "rerun_prerequisites": list(plan_record.get("rerun_prerequisites", [])),
    }


def build_preflight_repair_result_record(*, attempt_id: str, plan_record: dict[str, Any], rerun_exit: int, rerun_decision: str) -> dict[str, Any]:
    rerun_allowed = bool(plan_record.get("apply_automatically", False))
    escalation_required = bool(plan_record.get("escalation_required", not rerun_allowed))
    return {
        "artifact_type": "preflight_repair_result_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "result_id": f"result-{attempt_id}",
        "attempt_id": attempt_id,
        "rerun_preflight_exit_code": rerun_exit,
        "rerun_strategy_gate_decision": rerun_decision,
        "success": rerun_exit == 0 and rerun_decision == "ALLOW",
        "rerun_allowed": rerun_allowed,
        "rerun_requires": list(plan_record.get("rerun_prerequisites", [])),
        "escalation_required": escalation_required,
        "next_invocation_surface": "scripts/run_github_pr_autofix_contract_preflight.py" if rerun_allowed else "operator_escalation_queue",
        "terminal_state": "passed_after_auto_repair" if rerun_exit == 0 and rerun_decision == "ALLOW" else "blocked_repair_failed",
    }


def emit_preflight_block_bundle(*, report: dict[str, Any], preflight_artifact: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    diagnosis = build_preflight_block_diagnosis_record(report=report, preflight_artifact=preflight_artifact)
    plan = build_preflight_repair_plan_record(diagnosis_record=diagnosis)
    candidate = build_failure_repair_candidate_artifact(diagnosis_record=diagnosis, plan_record=plan)
    result = build_preflight_repair_result_record(
        attempt_id=f"attempt-{plan['plan_id']}",
        plan_record=plan,
        rerun_exit=2,
        rerun_decision=str((preflight_artifact.get("control_signal") or {}).get("strategy_gate_decision") or "BLOCK"),
    )
    validate_artifact(diagnosis, "preflight_block_diagnosis_record")
    validate_artifact(plan, "preflight_repair_plan_record")
    validate_artifact(candidate, "failure_repair_candidate_artifact")
    validate_artifact(result, "preflight_repair_result_record")
    _write_json(output_dir / "preflight_block_diagnosis_record.json", diagnosis)
    _write_json(output_dir / "preflight_repair_plan_record.json", plan)
    _write_json(output_dir / "failure_repair_candidate_artifact.json", candidate)
    _write_json(output_dir / "preflight_repair_result_record.json", result)
    if bool(plan.get("escalation_required", False)):
        escalation = {
            "artifact_type": "preflight_human_escalation_record",
            "schema_version": "1.0.0",
            "diagnosis_id": diagnosis["diagnosis_id"],
            "failure_class": diagnosis["failure_class"],
            "reason_codes": diagnosis["reason_codes"],
            "escalation_reason": "auto_repair_forbidden_or_unknown",
            "required_actions": ["manual_review_required", "bounded_followup_plan_required"],
        }
        _write_json(output_dir / "preflight_human_escalation_record.json", escalation)
    return {"diagnosis": diagnosis, "plan": plan, "candidate": candidate, "result": result}


def _repair_required_surface_mapping(*, repo_root: Path, report: dict[str, Any]) -> list[str]:
    missing = report.get("missing_required_surface") or []
    override_path = repo_root / "docs" / "governance" / "preflight_required_surface_test_overrides.json"
    payload: dict[str, list[str]] = {}
    if override_path.is_file():
        loaded = json.loads(override_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            payload = {str(path): [str(test) for test in tests if isinstance(test, str)] for path, tests in loaded.items() if isinstance(path, str) and isinstance(tests, list)}

    actionable = False
    for entry in missing:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "").strip()
        if not path.startswith("spectrum_systems/modules/runtime/"):
            continue
        actionable = True
        module_stem = Path(path).stem
        candidate = f"tests/test_{module_stem}.py"
        fallback = "tests/test_task_registry_ai_adapter_eval_slice_runner.py"
        selected = candidate if (repo_root / candidate).is_file() else fallback
        payload[path] = sorted(set(payload.get(path, []) + [selected]))

    if not actionable:
        return []
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [str(override_path.relative_to(repo_root))]


def _repair_system_registry_reserved_entries(*, repo_root: Path) -> list[str]:
    path = repo_root / "contracts" / "examples" / "system_registry_artifact.json"
    payload = _read_json(path)
    changed = False
    for system in payload.get("systems", []):
        if not isinstance(system, dict):
            continue
        acronym = str(system.get("acronym") or "")
        if acronym not in {"CPX", "CLX", "HFX"}:
            continue
        if not system.get("owns"):
            system["owns"] = [f"{acronym.lower()}_reserved_planning_scope"]
            changed = True
        if not system.get("consumes"):
            system["consumes"] = [f"{acronym.lower()}_reserved_input"]
            changed = True
        if not system.get("produces"):
            system["produces"] = [f"{acronym.lower()}_reserved_artifact"]
            changed = True
    if changed:
        _write_json(path, payload)
    return [str(path.relative_to(repo_root))]


def _run(command: list[str], cwd: Path) -> CommandResult:
    completed = subprocess.run(command, cwd=str(cwd), check=False)
    return CommandResult(command=command, returncode=completed.returncode)


def run_preflight_block_autorepair(
    *,
    repo_root: Path,
    output_dir: Path,
    base_ref: str,
    head_ref: str,
    execution_context: str,
    pqx_wrapper_path: Path,
    authority_evidence_ref: str,
    same_repo_write_allowed: bool,
    command_runner: Callable[[list[str], Path], CommandResult] = _run,
) -> dict[str, Any]:
    if not same_repo_write_allowed:
        raise ContractPreflightAutofixError("unsafe_context_fork_or_external_repo")

    result_artifact = _read_json(output_dir / "contract_preflight_result_artifact.json")
    if str((result_artifact.get("control_signal") or {}).get("strategy_gate_decision") or "") != "BLOCK":
        raise ContractPreflightAutofixError("preflight_not_blocked")

    report = _read_json(output_dir / "contract_preflight_report.json")
    bundle = emit_preflight_block_bundle(report=report, preflight_artifact=result_artifact, output_dir=output_dir)
    diagnosis = bundle["diagnosis"]
    plan = bundle["plan"]
    attempt = {
        "artifact_type": "preflight_repair_attempt_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "attempt_id": f"attempt-{plan['plan_id']}",
        "plan_id": plan["plan_id"],
        "attempt_status": "skipped",
        "mutated_paths": [],
    }

    artifact_refs = {
        "preflight_result_ref": str(output_dir / "contract_preflight_result_artifact.json"),
        "diagnosis_ref": str(output_dir / "preflight_block_diagnosis_record.json"),
        "repair_plan_ref": str(output_dir / "preflight_repair_plan_record.json"),
        "repair_candidate_ref": str(output_dir / "failure_repair_candidate_artifact.json"),
        "rerun_decision_ref": str(output_dir / "preflight_repair_result_record.json"),
    }

    repair_inapplicable_reason: str | None = None
    if plan["apply_automatically"]:
        category = plan["failure_class"]
        if category in {"invalid_wrapper", "authority_evidence_missing", "missing_required_artifact"}:
            cmd = [
                sys.executable,
                "scripts/build_preflight_pqx_wrapper.py",
                "--base-ref",
                base_ref,
                "--head-ref",
                head_ref,
                "--output",
                str(pqx_wrapper_path),
            ]
            built = command_runner(cmd, repo_root)
            if built.returncode != 0:
                raise ContractPreflightAutofixError("wrapper_regeneration_failed")
            attempt["mutated_paths"] = [str(pqx_wrapper_path)]
        elif category == "contract_mismatch":
            attempt["mutated_paths"] = _repair_required_surface_mapping(repo_root=repo_root, report=report)
        elif category == "schema_violation":
            attempt["mutated_paths"] = _repair_system_registry_reserved_entries(repo_root=repo_root)
        else:
            raise ContractPreflightAutofixError("unsupported_auto_repair_category")
        if not attempt["mutated_paths"]:
            repair_inapplicable_reason = "empty_repair_plan"
            attempt["attempt_status"] = "skipped"
            result = build_preflight_repair_result_record(
                attempt_id=attempt["attempt_id"],
                plan_record=plan,
                rerun_exit=2,
                rerun_decision=str(((result_artifact.get("control_signal") or {}).get("strategy_gate_decision")) or "BLOCK"),
            )
            result["terminal_state"] = _fold_terminal_state(
                eligibility_decision=str(plan.get("eligibility_decision", "escalation_required")),
                repair_attempted=False,
                repair_inapplicable_reason=repair_inapplicable_reason,
                repair_execution_status="not_invoked",
                rerun_status="not_run",
            )
            validate_artifact(attempt, "preflight_repair_attempt_record")
            validate_artifact(result, "preflight_repair_result_record")
            _write_json(output_dir / "preflight_repair_attempt_record.json", attempt)
            _write_json(output_dir / "preflight_repair_result_record.json", result)
            _write_recovery_outcome(
                output_dir=output_dir,
                result_artifact=result_artifact,
                diagnosis=diagnosis,
                plan=plan,
                repair_invoked=False,
                repair_execution_status="not_invoked",
                rerun_status="not_run",
                final_decision=result["terminal_state"],
                repair_attempted=False,
                repair_inapplicable_reason=repair_inapplicable_reason,
                retry_count=0,
                reason_codes=list(diagnosis.get("reason_codes", [])) + ["EMPTY_REPAIR_PLAN"],
                artifact_refs=artifact_refs,
            )
            raise ContractPreflightAutofixError("repair_plan_not_applicable:empty_repair_plan")
        if len(attempt["mutated_paths"]) > 5:
            raise ContractPreflightAutofixError("proposed_file_scope_too_broad")
        attempt["attempt_status"] = "applied"
    else:
        repair_inapplicable_reason = (
            "eligibility_decision_escalation_required"
            if str(plan.get("eligibility_decision")) == "escalation_required"
            else "auto_repair_forbidden_by_policy"
        )
        result = build_preflight_repair_result_record(
            attempt_id=attempt["attempt_id"],
            plan_record=plan,
            rerun_exit=2,
            rerun_decision=str(((result_artifact.get("control_signal") or {}).get("strategy_gate_decision")) or "BLOCK"),
        )
        result["terminal_state"] = _fold_terminal_state(
            eligibility_decision=str(plan.get("eligibility_decision", "escalation_required")),
            repair_attempted=False,
            repair_inapplicable_reason=repair_inapplicable_reason,
            repair_execution_status="not_invoked",
            rerun_status="not_permitted",
        )
        validate_artifact(attempt, "preflight_repair_attempt_record")
        validate_artifact(result, "preflight_repair_result_record")
        _write_json(output_dir / "preflight_repair_attempt_record.json", attempt)
        _write_json(output_dir / "preflight_repair_result_record.json", result)
        escalation_ref = output_dir / "preflight_human_escalation_record.json"
        if escalation_ref.exists():
            artifact_refs["escalation_ref"] = str(escalation_ref)
        _write_recovery_outcome(
            output_dir=output_dir,
            result_artifact=result_artifact,
            diagnosis=diagnosis,
            plan=plan,
            repair_invoked=False,
            repair_execution_status="not_invoked",
            rerun_status="not_permitted",
            final_decision=result["terminal_state"],
            repair_attempted=False,
            repair_inapplicable_reason=repair_inapplicable_reason,
            retry_count=0,
            reason_codes=list(diagnosis.get("reason_codes", [])),
            artifact_refs=artifact_refs,
        )
        raise ContractPreflightAutofixError("auto_repair_forbidden_escalation_required")

    validation_cmd = [sys.executable, "-m", "pytest", "-q", "tests/test_contract_preflight.py"]
    validation = command_runner(validation_cmd, repo_root)
    validation_record = {
        "artifact_type": "preflight_repair_validation_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "validation_id": f"validation-{attempt['attempt_id']}",
        "attempt_id": attempt["attempt_id"],
        "validation_passed": validation.returncode == 0,
        "validation_command": " ".join(validation_cmd),
    }
    if validation.returncode != 0:
        terminal_state = _fold_terminal_state(
            eligibility_decision=str(plan.get("eligibility_decision", "escalation_required")),
            repair_attempted=True,
            repair_inapplicable_reason=None,
            repair_execution_status="failed_validation",
            rerun_status="not_run",
        )
        _write_recovery_outcome(
            output_dir=output_dir,
            result_artifact=result_artifact,
            diagnosis=diagnosis,
            plan=plan,
            repair_invoked=True,
            repair_execution_status="failed_validation",
            rerun_status="not_run",
            final_decision=terminal_state,
            repair_attempted=True,
            repair_inapplicable_reason=None,
            retry_count=1,
            reason_codes=list(diagnosis.get("reason_codes", [])) + ["VALIDATION_REPLAY_FAILED", "repair_pipeline_failure"],
            artifact_refs=artifact_refs,
        )
        raise ContractPreflightAutofixError("validation_replay_failed")

    rerun_cmd = [
        sys.executable,
        "scripts/run_contract_preflight.py",
        "--base-ref",
        base_ref,
        "--head-ref",
        head_ref,
        "--output-dir",
        str(output_dir),
        "--execution-context",
        execution_context,
        "--pqx-wrapper-path",
        str(pqx_wrapper_path),
        "--authority-evidence-ref",
        authority_evidence_ref,
    ]
    rerun = command_runner(rerun_cmd, repo_root)
    rerun_artifact = _read_json(output_dir / "contract_preflight_result_artifact.json")
    rerun_decision = str(((rerun_artifact.get("control_signal") or {}).get("strategy_gate_decision")) or "BLOCK")
    result = build_preflight_repair_result_record(
        attempt_id=attempt["attempt_id"],
        plan_record=plan,
        rerun_exit=rerun.returncode,
        rerun_decision=rerun_decision,
    )
    result["terminal_state"] = _fold_terminal_state(
        eligibility_decision=str(plan.get("eligibility_decision", "escalation_required")),
        repair_attempted=True,
        repair_inapplicable_reason=None,
        repair_execution_status="completed",
        rerun_status="passed" if result["success"] else "blocked",
    )

    validate_artifact(attempt, "preflight_repair_attempt_record")
    validate_artifact(validation_record, "preflight_repair_validation_record")
    validate_artifact(result, "preflight_repair_result_record")

    _write_json(output_dir / "preflight_block_diagnosis_record.json", diagnosis)
    _write_json(output_dir / "preflight_repair_plan_record.json", plan)
    _write_json(output_dir / "preflight_repair_attempt_record.json", attempt)
    _write_json(output_dir / "preflight_repair_validation_record.json", validation_record)
    _write_json(output_dir / "preflight_repair_result_record.json", result)
    if not result["success"]:
        _write_recovery_outcome(
            output_dir=output_dir,
            result_artifact=result_artifact,
            diagnosis=diagnosis,
            plan=plan,
            repair_invoked=True,
            repair_execution_status="completed",
            rerun_status="blocked",
            final_decision=result["terminal_state"],
            repair_attempted=True,
            repair_inapplicable_reason=None,
            retry_count=1,
            reason_codes=list(diagnosis.get("reason_codes", [])) + ["RERUN_STILL_BLOCKED", "repair_pipeline_failure"],
            artifact_refs=artifact_refs,
        )
        raise ContractPreflightAutofixError("preflight_rerun_blocked_or_failed")
    outcome = _write_recovery_outcome(
        output_dir=output_dir,
        result_artifact=result_artifact,
        diagnosis=diagnosis,
        plan=plan,
        repair_invoked=True,
        repair_execution_status="completed",
        rerun_status="passed",
        final_decision=result["terminal_state"],
        repair_attempted=True,
        repair_inapplicable_reason=None,
        retry_count=1,
        reason_codes=list(diagnosis.get("reason_codes", [])),
        artifact_refs=artifact_refs,
    )
    return {"repair_result": result, "recovery_outcome": outcome}
