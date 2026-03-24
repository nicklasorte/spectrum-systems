from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from scripts.run_eval_ci_gate import main
from spectrum_systems.contracts import load_schema


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _eval_run(case_ids: list[str] | None = None) -> dict:
    return {
        "artifact_type": "eval_run",
        "schema_version": "1.0.0",
        "trace_id": "22222222-2222-4222-8222-222222222222",
        "eval_run_id": "eval-run-test-001",
        "eval_case_ids": case_ids or ["eval-case-001"],
        "system_version": "spectrum-systems@test",
        "dataset_version": "golden@test",
        "timestamp": "2026-03-23T00:00:00Z",
    }


def _eval_case(*, forced_status: str = "pass", forced_score: float = 1.0) -> dict:
    return {
        "artifact_type": "eval_case",
        "schema_version": "1.0.0",
        "trace_id": "11111111-1111-4111-8111-111111111111",
        "eval_case_id": "eval-case-001",
        "input_artifact_refs": ["artifact://golden/case-001/input"],
        "expected_output_spec": {
            "forced_status": forced_status,
            "forced_score": forced_score,
        },
        "scoring_rubric": {
            "weights": {
                "correctness": 0.7,
                "completeness": 0.3,
            },
            "pass_threshold": 0.8,
        },
        "evaluation_type": "deterministic",
        "created_from": "manual",
    }


def _policy(
    *,
    pass_rate_min: float = 0.95,
    failure_rate_max: float = 0.05,
    drift_rate_max: float = 0.2,
    reproducibility_score_min: float = 0.8,
    blocking_system_responses: list[str] | None = None,
    control_thresholds: dict | None = None,
) -> dict:
    payload = {
        "artifact_type": "eval_ci_gate_policy",
        "schema_version": "1.0.0",
        "thresholds": {
            "pass_rate_min": pass_rate_min,
            "failure_rate_max": failure_rate_max,
            "drift_rate_max": drift_rate_max,
            "reproducibility_score_min": reproducibility_score_min,
        },
        "blocking_system_responses": blocking_system_responses or ["freeze", "block"],
    }
    if control_thresholds:
        payload["control_thresholds"] = control_thresholds
    return payload


def _run_gate(tmp_path: Path, *, case: dict, eval_run: dict | None = None, policy: dict | None = None) -> tuple[int, dict]:
    eval_run_path = tmp_path / "eval_run.json"
    eval_cases_path = tmp_path / "eval_cases.json"
    policy_path = tmp_path / "policy.json"
    out_dir = tmp_path / "out"

    _write_json(eval_run_path, eval_run or _eval_run())
    _write_json(eval_cases_path, [case])
    _write_json(policy_path, policy or _policy())

    code = main([
        "--eval-run",
        str(eval_run_path),
        "--eval-cases",
        str(eval_cases_path),
        "--policy",
        str(policy_path),
        "--output-dir",
        str(out_dir),
    ])
    summary = json.loads((out_dir / "evaluation_ci_gate_result.json").read_text(encoding="utf-8"))
    return code, summary


def test_happy_path_passes_and_emits_schema_valid_summary(tmp_path: Path) -> None:
    code, summary = _run_gate(tmp_path, case=_eval_case(forced_status="pass", forced_score=1.0))

    assert code == 0
    assert summary["status"] == "pass"
    assert summary["blocking_reasons"] == []
    assert summary["id"] == summary["gate_run_id"]
    assert summary["trace_refs"] == ["22222222-2222-4222-8222-222222222222"]

    validator = Draft202012Validator(load_schema("evaluation_ci_gate_result"), format_checker=FormatChecker())
    validator.validate(summary)


def test_missing_required_artifact_fails_closed(tmp_path: Path) -> None:
    eval_run_path = tmp_path / "eval_run.json"
    policy_path = tmp_path / "policy.json"
    out_dir = tmp_path / "out"

    _write_json(eval_run_path, _eval_run())
    _write_json(policy_path, _policy())

    code = main([
        "--eval-run",
        str(eval_run_path),
        "--eval-cases",
        str(tmp_path / "does-not-exist.json"),
        "--policy",
        str(policy_path),
        "--output-dir",
        str(out_dir),
    ])

    summary = json.loads((out_dir / "evaluation_ci_gate_result.json").read_text(encoding="utf-8"))
    assert code == 2
    assert summary["status"] == "blocked"
    assert "eval_cases" in summary["missing_artifacts"]
    assert summary["id"] == summary["gate_run_id"]


def test_invalid_schema_artifact_fails_closed(tmp_path: Path) -> None:
    bad_case = _eval_case()
    bad_case.pop("eval_case_id")

    code, summary = _run_gate(tmp_path, case=bad_case)

    assert code == 2
    assert summary["status"] == "blocked"
    assert any(item.startswith("eval_case[") for item in summary["invalid_artifacts"])


def test_indeterminate_eval_outcome_fails_closed(tmp_path: Path) -> None:
    code, summary = _run_gate(tmp_path, case=_eval_case(forced_status="indeterminate", forced_score=0.0))

    assert code == 2
    assert summary["status"] == "blocked"
    assert "indeterminate_eval_outcome_detected" in summary["blocking_reasons"]


def test_indeterminate_can_be_explicitly_overridden_by_policy(tmp_path: Path) -> None:
    policy = _policy()
    policy["indeterminate_is_blocking"] = False
    code, summary = _run_gate(
        tmp_path,
        case=_eval_case(forced_status="indeterminate", forced_score=0.0),
        policy=policy,
    )

    assert code == 1
    assert summary["status"] == "fail"
    assert "indeterminate_eval_outcome_detected" not in summary["blocking_reasons"]


def test_threshold_failure_fails_closed(tmp_path: Path) -> None:
    code, summary = _run_gate(
        tmp_path,
        case=_eval_case(forced_status="fail", forced_score=0.0),
    )

    assert code == 1
    assert summary["status"] == "fail"
    assert any(reason.startswith("threshold_failed:") for reason in summary["blocking_reasons"])


def test_blocking_control_decision_fails_closed(tmp_path: Path, monkeypatch) -> None:
    def _stubbed_run_eval_run(_eval_run: dict, _eval_cases: list[dict]) -> dict:
        return {
            "artifact_type": "eval_run_execution",
            "schema_version": "1.0.0",
            "trace_id": "22222222-2222-4222-8222-222222222222",
            "executed_at": "2026-03-23T00:00:00Z",
            "eval_run": _eval_run,
            "eval_results": [
                {
                    "artifact_type": "eval_result",
                    "schema_version": "1.0.0",
                    "eval_case_id": "eval-case-001",
                    "trace_id": "11111111-1111-4111-8111-111111111111",
                    "result_status": "pass",
                    "score": 1.0,
                    "failure_modes": ["non_reproducible"],
                    "provenance_refs": ["trace://11111111-1111-4111-8111-111111111111"],
                }
            ],
            "eval_summary": {
                "artifact_type": "eval_summary",
                "schema_version": "1.0.0",
                "trace_id": "22222222-2222-4222-8222-222222222222",
                "eval_run_id": "eval-run-test-001",
                "pass_rate": 1.0,
                "failure_rate": 0.0,
                "drift_rate": 0.0,
                "reproducibility_score": 0.2,
                "system_status": "healthy",
            },
        }

    monkeypatch.setattr("scripts.run_eval_ci_gate.run_eval_run", _stubbed_run_eval_run)

    code, summary = _run_gate(
        tmp_path,
        case=_eval_case(forced_status="pass", forced_score=1.0),
        policy=_policy(reproducibility_score_min=0.1, control_thresholds={"trust_threshold": 0.8}),
    )

    assert code == 2
    assert summary["status"] == "blocked"
    assert any(reason.startswith("control_decision_blocked:") for reason in summary["blocking_reasons"])


def test_gate_run_id_is_deterministic_for_same_inputs(tmp_path: Path) -> None:
    case = _eval_case(forced_status="pass", forced_score=1.0)
    code_one, summary_one = _run_gate(tmp_path, case=case)
    code_two, summary_two = _run_gate(tmp_path, case=case)
    assert code_one == 0
    assert code_two == 0
    assert summary_one["gate_run_id"] == summary_two["gate_run_id"]
