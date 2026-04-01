from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts import run_control_loop_certification as clc  # noqa: E402
from spectrum_systems.contracts import load_schema  # noqa: E402


def _check(
    check_id: str,
    status: str,
    *,
    exit_code: int | None = 0,
    evidence_ref: str = "evidence.json",
) -> clc.CheckResult:
    return clc.CheckResult(
        check_id=check_id,
        check_name=clc.CHECK_NAMES[check_id],
        command=clc.DEFAULT_COMMANDS[check_id],
        status=status,
        exit_code=exit_code,
        evidence_ref=evidence_ref,
        summary=f"{check_id}:{status}",
    )


def _gate_proof_evidence() -> dict:
    return {
        "severity_linkage_complete": True,
        "deterministic_transition_consumption": True,
        "policy_caused_action_observed": True,
        "recurrence_prevention_linked": True,
        "failure_binding_required_for_progression": True,
        "missing_binding_blocks_progression": True,
        "advisory_only_learning_rejected": True,
        "transition_policy_consumes_binding_deterministically": True,
        "control_loop_closure_bundle_complete": True,
        "replay_parity_exact": True,
        "trace_completeness_verified": True,
        "severity_linkage_refs": ["contracts/examples/failure_eval_case.json"],
        "transition_consumption_refs": ["contracts/examples/prompt_queue_transition_decision.json"],
        "policy_action_refs": ["contracts/examples/pqx_slice_execution_record.json"],
        "recurrence_prevention_refs": ["contracts/examples/failure_policy_binding.json"],
        "control_loop_closure_bundle_refs": ["contracts/examples/control_loop_closure_evidence_bundle.json"],
    }


def test_status_mapping_happy_path_is_certified() -> None:
    checks = [_check(cid, "pass", exit_code=0) for cid in clc.REQUIRED_CHECK_IDS]
    status, decision = clc._status_from_checks(checks)
    assert status == "certified"
    assert decision == "pass"


def test_status_mapping_failed_check_is_uncertified() -> None:
    checks = [
        _check("control_loop_chaos_runner", "pass", exit_code=0),
        _check("targeted_control_loop_eval_gate_tests", "fail", exit_code=1),
        _check("review_artifact_validation", "pass", exit_code=0),
        _check("repo_review_validator", "pass", exit_code=0),
    ]
    status, decision = clc._status_from_checks(checks)
    assert status == "uncertified"
    assert decision == "fail"


def test_missing_required_check_command_is_blocked() -> None:
    commands = dict(clc.DEFAULT_COMMANDS)
    commands["repo_review_validator"] = ""

    blocked = clc._check_missing_required_commands(commands)
    assert len(blocked) == 4
    missing = next(check for check in blocked if check.check_id == "repo_review_validator")
    assert missing.status == "blocked"
    assert "missing" in missing.summary.lower()


def test_malformed_chaos_payload_is_blocked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    chaos_output = tmp_path / "chaos.json"
    chaos_output.write_text(json.dumps({"chaos_run_id": "chaos-1"}), encoding="utf-8")

    commands = dict(clc.DEFAULT_COMMANDS)
    commands["targeted_control_loop_eval_gate_tests"] = "python -c \"print('ok tests')\""
    commands["review_artifact_validation"] = "python -c \"print('ok review')\""
    commands["repo_review_validator"] = "python -c \"print('ok repo review')\""

    review_json = tmp_path / "review.json"
    review_md = tmp_path / "review.md"
    review_json.write_text("{}", encoding="utf-8")
    review_md.write_text("---\nmodule: x\nreview_type: x\nreview_date: 2026-03-27\nreviewer: x\ndecision: PASS\ntrust_assessment: high\nstatus: final\nrelated_plan: docs/review-actions/PLAN-PQX-CLT-003-2026-03-27.md\n---\n", encoding="utf-8")

    monkeypatch.setattr(clc, "_run_command", lambda _command: clc.CommandExecution(0, "ok", ""))

    checks, _, _, _ = clc._execute_checks(
        commands=commands,
        chaos_output_path=chaos_output,
        review_json=review_json,
        review_markdown=review_md,
        log_dir=tmp_path,
    )

    chaos = next(check for check in checks if check.check_id == "control_loop_chaos_runner")
    assert chaos.status == "blocked"
    assert "malformed" in chaos.summary


def test_generated_artifact_is_schema_valid_and_id_deterministic() -> None:
    checks = [_check(cid, "pass", exit_code=0) for cid in clc.REQUIRED_CHECK_IDS]

    artifact_a = clc._build_certification_artifact(
        checks=checks,
        scenario_summary={"chaos_run_id": "chaos-1", "scenario_count": 4, "pass_count": 4, "fail_count": 0},
        test_summary={
            "targeted_test_command": clc.DEFAULT_COMMANDS["targeted_control_loop_eval_gate_tests"],
            "targeted_test_status": "pass",
            "targeted_test_exit_code": 0,
        },
        artifact_validation_summary={
            "review_artifact_validation_status": "pass",
            "repo_review_validator_status": "pass",
        },
        gate_proof_evidence=_gate_proof_evidence(),
        related_review_refs=["docs/reviews/2026-03-27-control-loop-trust-boundary-surgical-review.json"],
        related_plan_refs=["docs/review-actions/PLAN-PQX-CLT-003-2026-03-27.md"],
    )

    artifact_b = clc._build_certification_artifact(
        checks=checks,
        scenario_summary={"chaos_run_id": "chaos-1", "scenario_count": 4, "pass_count": 4, "fail_count": 0},
        test_summary={
            "targeted_test_command": clc.DEFAULT_COMMANDS["targeted_control_loop_eval_gate_tests"],
            "targeted_test_status": "pass",
            "targeted_test_exit_code": 0,
        },
        artifact_validation_summary={
            "review_artifact_validation_status": "pass",
            "repo_review_validator_status": "pass",
        },
        gate_proof_evidence=_gate_proof_evidence(),
        related_review_refs=["docs/reviews/2026-03-27-control-loop-trust-boundary-surgical-review.json"],
        related_plan_refs=["docs/review-actions/PLAN-PQX-CLT-003-2026-03-27.md"],
    )

    assert artifact_a["certification_id"] == artifact_b["certification_id"]

    validator = Draft202012Validator(load_schema("control_loop_certification_pack"), format_checker=FormatChecker())
    errors = list(validator.iter_errors(artifact_a))
    assert errors == []


def test_gate_proof_evidence_requires_non_advisory_failure_binding() -> None:
    evidence = _gate_proof_evidence()
    evidence["advisory_only_learning_rejected"] = False
    passed, failures = clc._evaluate_gate_proof_evidence(evidence)
    assert passed is False
    assert any("advisory_only_learning_rejected" in message for message in failures)


def test_cli_integration_emits_artifact(tmp_path: Path) -> None:
    script_path = REPO_ROOT / "scripts" / "run_control_loop_certification.py"
    output = tmp_path / "certification.json"
    chaos_output = tmp_path / "chaos.json"
    chaos_output.write_text(
        json.dumps({"chaos_run_id": "chaos-cli", "scenario_count": 2, "pass_count": 2, "fail_count": 0}),
        encoding="utf-8",
    )

    review_json = tmp_path / "review.json"
    review_md = tmp_path / "review.md"
    review_json.write_text("{}", encoding="utf-8")
    review_md.write_text("synthetic", encoding="utf-8")

    cmd = [
        sys.executable,
        str(script_path),
        "--output",
        str(output),
        "--chaos-output",
        str(chaos_output),
        "--review-json",
        str(review_json),
        "--review-markdown",
        str(review_md),
        "--chaos-command",
        "python -c \"print('ok chaos')\"",
        "--tests-command",
        "python -c \"print('ok tests')\"",
        "--review-command",
        "python -c \"print('ok review')\"",
        "--repo-review-command",
        "python -c \"print('ok repo review')\"",
        "--gate-proof-ref",
        "contracts/examples/failure_eval_case.json",
    ]

    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr

    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["certification_status"] == "certified"
    assert artifact["decision"] == "pass"
    assert len(artifact["executed_checks"]) == 4
