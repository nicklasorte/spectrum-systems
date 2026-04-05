from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.recovery_orchestrator import (
    RecoveryOrchestrationError,
    orchestrate_recovery,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _diagnosis_fixture() -> dict:
    return json.loads((_REPO_ROOT / "contracts" / "examples" / "failure_diagnosis_artifact.json").read_text(encoding="utf-8"))


def _repair_prompt_fixture() -> dict:
    return json.loads((_REPO_ROOT / "contracts" / "examples" / "repair_prompt_artifact.json").read_text(encoding="utf-8"))


def _execution_runner_complete(_: dict) -> dict:
    return {
        "execution_status": "completed",
        "reason_code": None,
        "repair_execution_mode": "bounded_governed_execution",
        "execution_artifact_refs": ["outputs/recovery/execution-attempt-01.json"],
        "governance_gate_evidence_refs": {
            "preflight": "outputs/governance/preflight-gate-01.json",
            "control": "outputs/governance/control-gate-01.json",
            "certification": "outputs/governance/certification-gate-01.json",
            "certification_applicable": True,
        },
    }


def test_successful_recovery_status_recovered() -> None:
    diagnosis = _diagnosis_fixture()
    prompt = _repair_prompt_fixture()

    def validation_runner(_: str) -> dict:
        return {"status": "passed", "artifact_ref": "outputs/recovery/validation-attempt-01.json", "details": {"exit_code": 0}}

    artifact = orchestrate_recovery(
        diagnosis_artifact=diagnosis,
        repair_prompt_artifact=prompt,
        recovery_attempt_number=1,
        max_attempts=2,
        execution_runner=_execution_runner_complete,
        validation_runner=validation_runner,
        emitted_at="2026-04-05T00:00:00Z",
    )

    assert artifact["recovery_status"] == "recovered"
    assert artifact["retry_recommended"] is False
    assert artifact["validation_summary"]["passed"] == len(artifact["attempted_validation_commands"])


def test_partial_recovery_status() -> None:
    diagnosis = _diagnosis_fixture()
    prompt = _repair_prompt_fixture()

    statuses = iter(["passed", "failed"])

    def validation_runner(_: str) -> dict:
        return {"status": next(statuses), "artifact_ref": "outputs/recovery/validation-partial.json", "details": {}}

    artifact = orchestrate_recovery(
        diagnosis_artifact=diagnosis,
        repair_prompt_artifact=prompt,
        recovery_attempt_number=1,
        max_attempts=3,
        execution_runner=_execution_runner_complete,
        validation_runner=validation_runner,
        emitted_at="2026-04-05T00:00:00Z",
    )

    assert artifact["recovery_status"] == "partially_recovered"
    assert artifact["remaining_failure_classes"] == [diagnosis["primary_root_cause"]]
    assert artifact["retry_recommended"] is True


def test_blocked_recovery_status() -> None:
    diagnosis = _diagnosis_fixture()
    prompt = _repair_prompt_fixture()

    def execution_runner(_: dict) -> dict:
        return {
            "execution_status": "blocked",
            "reason_code": "governance_block",
            "execution_artifact_refs": ["outputs/recovery/execution-blocked.json"],
            "governance_gate_evidence_refs": {
                "preflight": "outputs/governance/preflight-gate-blocked.json",
                "control": "outputs/governance/control-gate-blocked.json",
                "certification": "",
                "certification_applicable": False,
            },
        }

    def validation_runner(_: str) -> dict:
        return {"status": "passed", "artifact_ref": "outputs/recovery/validation-blocked.json", "details": {}}

    artifact = orchestrate_recovery(
        diagnosis_artifact=diagnosis,
        repair_prompt_artifact=prompt,
        recovery_attempt_number=1,
        max_attempts=2,
        execution_runner=execution_runner,
        validation_runner=validation_runner,
        emitted_at="2026-04-05T00:00:00Z",
    )

    assert artifact["recovery_status"] == "blocked"
    assert artifact["blocking_reason_code"] == "governance_block"


def test_failed_recovery_status() -> None:
    diagnosis = _diagnosis_fixture()
    prompt = _repair_prompt_fixture()

    def validation_runner(_: str) -> dict:
        return {"status": "failed", "artifact_ref": "outputs/recovery/validation-failed.json", "details": {"exit_code": 1}}

    artifact = orchestrate_recovery(
        diagnosis_artifact=diagnosis,
        repair_prompt_artifact=prompt,
        recovery_attempt_number=1,
        max_attempts=3,
        execution_runner=_execution_runner_complete,
        validation_runner=validation_runner,
        emitted_at="2026-04-05T00:00:00Z",
    )

    assert artifact["recovery_status"] == "failed"
    assert artifact["retry_recommended"] is True


def test_deterministic_status_for_same_inputs() -> None:
    diagnosis = _diagnosis_fixture()
    prompt = _repair_prompt_fixture()

    def validation_runner(_: str) -> dict:
        return {"status": "failed", "artifact_ref": "outputs/recovery/validation-deterministic.json", "details": {}}

    first = orchestrate_recovery(
        diagnosis_artifact=copy.deepcopy(diagnosis),
        repair_prompt_artifact=copy.deepcopy(prompt),
        recovery_attempt_number=1,
        max_attempts=3,
        execution_runner=_execution_runner_complete,
        validation_runner=validation_runner,
        emitted_at="2026-04-05T00:00:00Z",
    )
    second = orchestrate_recovery(
        diagnosis_artifact=copy.deepcopy(diagnosis),
        repair_prompt_artifact=copy.deepcopy(prompt),
        recovery_attempt_number=1,
        max_attempts=3,
        execution_runner=copy.deepcopy(_execution_runner_complete),
        validation_runner=validation_runner,
        emitted_at="2026-04-05T00:00:00Z",
    )

    assert first == second


def test_fail_closed_when_validation_commands_missing() -> None:
    diagnosis = _diagnosis_fixture()
    prompt = _repair_prompt_fixture()
    prompt["validation_commands"] = []

    with pytest.raises(RecoveryOrchestrationError, match="failed schema validation"):
        orchestrate_recovery(
            diagnosis_artifact=diagnosis,
            repair_prompt_artifact=prompt,
            recovery_attempt_number=1,
            max_attempts=2,
            execution_runner=_execution_runner_complete,
            validation_runner=lambda _: {"status": "passed", "artifact_ref": "x", "details": {}},
        )


def test_retry_recommendation_and_reentry_evidence() -> None:
    diagnosis = _diagnosis_fixture()
    prompt = _repair_prompt_fixture()

    def validation_runner(_: str) -> dict:
        return {"status": "failed", "artifact_ref": "outputs/recovery/validation-reentry.json", "details": {"exit_code": 1}}

    artifact = orchestrate_recovery(
        diagnosis_artifact=diagnosis,
        repair_prompt_artifact=prompt,
        recovery_attempt_number=1,
        max_attempts=2,
        execution_runner=_execution_runner_complete,
        validation_runner=validation_runner,
        emitted_at="2026-04-05T00:00:00Z",
    )

    assert artifact["retry_recommended"] is True
    assert artifact["diagnosis_ref"] == diagnosis["diagnosis_id"]
    assert artifact["repair_prompt_ref"] == prompt["repair_prompt_id"]
    assert artifact["validation_results"]


def test_contract_example_and_generated_artifact_validate() -> None:
    schema = load_schema("recovery_result_artifact")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    example = json.loads((_REPO_ROOT / "contracts" / "examples" / "recovery_result_artifact.json").read_text(encoding="utf-8"))
    validator.validate(example)

    diagnosis = _diagnosis_fixture()

    def validation_runner(_: str) -> dict:
        return {"status": "passed", "artifact_ref": "outputs/recovery/validation-schema.json", "details": {"exit_code": 0}}

    generated = orchestrate_recovery(
        diagnosis_artifact=diagnosis,
        repair_prompt_artifact=None,
        recovery_attempt_number=1,
        max_attempts=2,
        execution_runner=_execution_runner_complete,
        validation_runner=validation_runner,
        emitted_at="2026-04-05T00:00:00Z",
    )
    validator.validate(generated)


def test_standards_manifest_registers_recovery_result_artifact() -> None:
    manifest = json.loads((_REPO_ROOT / "contracts" / "standards-manifest.json").read_text(encoding="utf-8"))
    entries = [entry for entry in manifest.get("contracts", []) if entry.get("artifact_type") == "recovery_result_artifact"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["artifact_class"] == "coordination"
    assert entry["example_path"] == "contracts/examples/recovery_result_artifact.json"


def test_retry_budget_exhausted_emits_terminal_blocked_artifact() -> None:
    diagnosis = _diagnosis_fixture()
    prompt = _repair_prompt_fixture()
    schema = load_schema("recovery_result_artifact")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    artifact = orchestrate_recovery(
        diagnosis_artifact=diagnosis,
        repair_prompt_artifact=prompt,
        recovery_attempt_number=3,
        max_attempts=2,
        execution_runner=_execution_runner_complete,
        validation_runner=lambda _: {"status": "passed", "artifact_ref": "unused", "details": {}},
        emitted_at="2026-04-05T00:00:00Z",
    )

    validator.validate(artifact)
    assert artifact["recovery_status"] == "blocked"
    assert artifact["blocking_reason_code"] == "retry_budget_exhausted"
    assert artifact["retry_recommended"] is False
    assert artifact["execution_artifact_refs"]
    assert artifact["validation_results"]
    assert all(row["status"] == "not_run" for row in artifact["validation_results"])


def test_execution_without_governance_evidence_fails_closed() -> None:
    diagnosis = _diagnosis_fixture()
    prompt = _repair_prompt_fixture()

    def execution_runner(_: dict) -> dict:
        return {
            "execution_status": "completed",
            "reason_code": None,
            "repair_execution_mode": "bounded_governed_execution",
            "execution_artifact_refs": ["outputs/recovery/execution-attempt-01.json"],
        }

    with pytest.raises(RecoveryOrchestrationError, match="governance_gate_evidence_refs"):
        orchestrate_recovery(
            diagnosis_artifact=diagnosis,
            repair_prompt_artifact=prompt,
            recovery_attempt_number=1,
            max_attempts=2,
            execution_runner=execution_runner,
            validation_runner=lambda _: {"status": "passed", "artifact_ref": "outputs/recovery/validation-01.json", "details": {}},
            emitted_at="2026-04-05T00:00:00Z",
        )


def test_execution_with_governance_evidence_is_allowed_and_preserved() -> None:
    diagnosis = _diagnosis_fixture()
    prompt = _repair_prompt_fixture()

    artifact = orchestrate_recovery(
        diagnosis_artifact=diagnosis,
        repair_prompt_artifact=prompt,
        recovery_attempt_number=1,
        max_attempts=2,
        execution_runner=_execution_runner_complete,
        validation_runner=lambda _: {"status": "passed", "artifact_ref": "outputs/recovery/validation-01.json", "details": {}},
        emitted_at="2026-04-05T00:00:00Z",
    )

    assert "outputs/governance/preflight-gate-01.json" in artifact["execution_artifact_refs"]
    assert "outputs/governance/control-gate-01.json" in artifact["execution_artifact_refs"]
    assert "outputs/governance/certification-gate-01.json" in artifact["execution_artifact_refs"]
    assert any(step["step"] == "governance_gate_evidence" for step in artifact["deterministic_decision_trace"])
