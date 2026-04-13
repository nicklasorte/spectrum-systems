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
    "missing_required_surface_mapping",
    "stale_test_fixture_contract",
    "stale_targeted_test_expectation",
    "missing_preflight_wrapper_or_authority_linkage",
    "trust_spine_input_expectation_mismatch",
    "control_surface_gap_mapping_missing",
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


def classify_preflight_block(*, report: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []

    if report.get("missing_required_surface"):
        return "missing_required_surface_mapping", ["missing_required_surface"]

    pqx_ctx = report.get("changed_path_detection", {}).get("pqx_required_context_enforcement")
    if isinstance(pqx_ctx, dict) and pqx_ctx.get("status") == "block":
        return "missing_preflight_wrapper_or_authority_linkage", ["pqx_required_context_enforcement_block"]

    if report.get("control_surface_gap_blocking") is True:
        return "control_surface_gap_mapping_missing", ["control_surface_gap_blocking"]

    if report.get("trust_spine_evidence_cohesion"):
        return "trust_spine_input_expectation_mismatch", ["trust_spine_evidence_cohesion_present"]

    producer_failures = report.get("producer_failures") or []
    fixture_hits = [entry for entry in producer_failures if isinstance(entry, dict) and "fixtures" in str(entry.get("path") or "")]
    if fixture_hits:
        return "stale_test_fixture_contract", ["fixture_contract_failure"]

    consumer_failures = report.get("consumer_failures") or []
    if consumer_failures:
        reasons.extend(["consumer_failures_present"])
        return "stale_targeted_test_expectation", reasons

    return "unknown", ["unclassified_block_reason"]


def build_preflight_block_diagnosis_record(*, report: dict[str, Any], preflight_artifact: dict[str, Any]) -> dict[str, Any]:
    category, reasons = classify_preflight_block(report=report)
    return {
        "artifact_type": "preflight_block_diagnosis_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "diagnosis_id": f"diag-{preflight_artifact.get('generated_at', 'unknown')}",
        "strategy_gate_decision": str(((preflight_artifact.get("control_signal") or {}).get("strategy_gate_decision")) or "BLOCK"),
        "repair_category": category,
        "reason_codes": reasons,
    }


def build_preflight_repair_plan_record(*, diagnosis_record: dict[str, Any]) -> dict[str, Any]:
    category = diagnosis_record["repair_category"]
    if category not in KNOWN_REPAIR_CATEGORIES:
        raise ContractPreflightAutofixError("unknown_repair_category")

    allowed_paths = {
        "missing_preflight_wrapper_or_authority_linkage": [
            "outputs/contract_preflight/preflight_pqx_task_wrapper.json",
            "outputs/contract_preflight/preflight_changed_path_resolution.json",
        ],
        "missing_required_surface_mapping": ["contracts/standards-manifest.json"],
        "stale_test_fixture_contract": ["tests/fixtures"],
        "stale_targeted_test_expectation": ["tests/"],
        "trust_spine_input_expectation_mismatch": ["tests/", "outputs/contract_preflight"],
        "control_surface_gap_mapping_missing": ["spectrum_systems/modules/runtime/control_surface_gap_to_pqx.py", "tests/test_control_surface_gap_to_pqx.py"],
    }[category]

    return {
        "artifact_type": "preflight_repair_plan_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "plan_id": f"plan-{diagnosis_record['diagnosis_id']}",
        "repair_category": category,
        "allowed_paths": allowed_paths,
        "apply_automatically": category in {"missing_preflight_wrapper_or_authority_linkage"},
    }


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
    diagnosis = build_preflight_block_diagnosis_record(report=report, preflight_artifact=result_artifact)
    if diagnosis["repair_category"] == "unknown":
        raise ContractPreflightAutofixError("unknown_block_reason")

    plan = build_preflight_repair_plan_record(diagnosis_record=diagnosis)
    attempt = {
        "artifact_type": "preflight_repair_attempt_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "attempt_id": f"attempt-{plan['plan_id']}",
        "plan_id": plan["plan_id"],
        "attempt_status": "skipped",
        "mutated_paths": [],
    }

    if plan["apply_automatically"]:
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
        attempt["attempt_status"] = "applied"
        attempt["mutated_paths"] = [str(pqx_wrapper_path)]

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
    result = {
        "artifact_type": "preflight_repair_result_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "result_id": f"result-{attempt['attempt_id']}",
        "attempt_id": attempt["attempt_id"],
        "rerun_preflight_exit_code": rerun.returncode,
        "rerun_strategy_gate_decision": rerun_decision,
        "success": rerun.returncode == 0 and rerun_decision == "ALLOW",
    }

    validate_artifact(diagnosis, "preflight_block_diagnosis_record")
    validate_artifact(plan, "preflight_repair_plan_record")
    validate_artifact(attempt, "preflight_repair_attempt_record")
    validate_artifact(validation_record, "preflight_repair_validation_record")
    validate_artifact(result, "preflight_repair_result_record")

    _write_json(output_dir / "preflight_block_diagnosis_record.json", diagnosis)
    _write_json(output_dir / "preflight_repair_plan_record.json", plan)
    _write_json(output_dir / "preflight_repair_attempt_record.json", attempt)
    _write_json(output_dir / "preflight_repair_validation_record.json", validation_record)
    _write_json(output_dir / "preflight_repair_result_record.json", result)

    if not result["success"]:
        raise ContractPreflightAutofixError("preflight_rerun_blocked_or_failed")
    return result
