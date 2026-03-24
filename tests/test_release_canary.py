from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from scripts.run_release_canary import main
from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.release_canary import ReleaseInputVersions, build_release_record


def _eval_summary(eval_run_id: str, *, pass_rate: float, trace_suffix: str = "1") -> dict:
    return {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": f"00000000-0000-4000-8000-{int(trace_suffix):012d}",
        "eval_run_id": eval_run_id,
        "pass_rate": pass_rate,
        "failure_rate": round(1.0 - pass_rate, 6),
        "drift_rate": 0.0,
        "reproducibility_score": 1.0,
        "system_status": "healthy",
    }


def _eval_result(case_id: str, *, status: str = "pass", indeterminate: bool = False) -> dict:
    failure_modes: list[str] = []
    if status != "pass":
        failure_modes.append("expected_output_mismatch")
    if indeterminate:
        failure_modes.append("indeterminate_treated_as_failure")
    return {
        "artifact_type": "eval_result",
        "schema_version": "1.0.0",
        "eval_case_id": case_id,
        "trace_id": "11111111-1111-4111-8111-111111111111",
        "result_status": status,
        "score": 1.0 if status == "pass" else 0.0,
        "failure_modes": failure_modes,
        "provenance_refs": [f"trace://{case_id}"],
    }


def _coverage(run_id: str, *, score: float = 1.0, uncovered: list[str] | None = None, total_cases: int = 2) -> dict:
    return {
        "artifact_type": "eval_coverage_summary",
        "schema_version": "1.0.0",
        "coverage_run_id": run_id,
        "timestamp": "2026-03-24T00:00:00Z",
        "dataset_refs": [],
        "total_eval_cases": total_cases,
        "covered_slices": ["slice.alpha"],
        "uncovered_required_slices": uncovered or [],
        "slice_case_counts": {"slice.alpha": total_cases},
        "risk_weighted_coverage_score": score,
        "coverage_gaps": [],
    }


def _slice_summary(pass_rate: float = 1.0, *, total_cases: int = 2) -> dict:
    return {
        "artifact_type": "eval_slice_summary",
        "schema_version": "1.0.0",
        "coverage_run_id": "cov",
        "slice_id": "slice.alpha",
        "slice_name": "Alpha",
        "total_cases": total_cases,
        "pass_count": int(total_cases * pass_rate),
        "fail_count": total_cases - int(total_cases * pass_rate),
        "indeterminate_count": 0,
        "pass_rate": pass_rate,
        "failure_rate": round(1.0 - pass_rate, 6),
        "latest_eval_run_refs": ["trace://1"],
        "risk_class": "high",
        "priority": "p1",
        "status": "healthy",
    }


def _policy() -> dict:
    return {
        "policy_version_id": "eval-release-policy-v1.0.0",
        "minimum_eval_sample_size": 2,
        "max_acceptable_aggregate_regression": 0.02,
        "max_coverage_score_delta_drop": 0.05,
        "required_slices_no_regression": True,
        "coverage_parity_required": True,
        "new_failures_block": True,
        "indeterminate_blocks": True,
        "control_thresholds": {
            "reliability_threshold": 0.85,
            "drift_threshold": 0.2,
            "trust_threshold": 0.8,
        },
        "blocking_system_responses": ["freeze", "block"],
        "rollback_system_responses": ["block"],
        "rollback_pass_rate_delta_drop_threshold": 0.1,
        "rollback_triggers": [
            "candidate_blocked_by_control",
            "required_slice_regression",
            "coverage_mismatch",
            "new_failures_introduced",
            "indeterminate_case_detected",
            "pass_rate_drop_exceeds_rollback_threshold",
        ],
    }


def _versions(tag: str) -> ReleaseInputVersions:
    return ReleaseInputVersions(
        prompt_version_id=f"prompt-{tag}",
        schema_version=f"schema-{tag}",
        policy_version_id=f"policy-{tag}",
        route_policy_version_id=f"route-{tag}",
    )


def _build(**overrides):
    payload = {
        "release_id": "release-test-001",
        "timestamp": "2026-03-24T00:00:00Z",
        "baseline_version": "baseline-v1",
        "candidate_version": "candidate-v1",
        "artifact_types": ["prompt", "schema", "policy", "routing"],
        "baseline_versions": _versions("base"),
        "candidate_versions": _versions("cand"),
        "baseline_eval_summary": _eval_summary("base-run", pass_rate=1.0, trace_suffix="1"),
        "candidate_eval_summary": _eval_summary("cand-run", pass_rate=1.0, trace_suffix="2"),
        "baseline_eval_results": [_eval_result("case-1", status="pass"), _eval_result("case-2", status="pass")],
        "candidate_eval_results": [_eval_result("case-1", status="pass"), _eval_result("case-2", status="pass")],
        "baseline_coverage_summary": _coverage("cov-base", score=1.0),
        "candidate_coverage_summary": _coverage("cov-cand", score=1.0),
        "baseline_slice_summaries": [_slice_summary(1.0)],
        "candidate_slice_summaries": [_slice_summary(1.0)],
        "eval_summary_refs": {"baseline": "baseline/eval_summary.json", "candidate": "candidate/eval_summary.json"},
        "coverage_summary_refs": {
            "baseline": "baseline/eval_coverage_summary.json",
            "candidate": "candidate/eval_coverage_summary.json",
        },
        "policy": _policy(),
    }
    payload.update(overrides)
    return build_release_record(**payload)


def _write_json(path: Path, payload: dict | list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _eval_run(run_id: str, case_ids: list[str]) -> dict:
    return {
        "artifact_type": "eval_run",
        "schema_version": "1.0.0",
        "trace_id": "22222222-2222-4222-8222-222222222222",
        "eval_run_id": run_id,
        "eval_case_ids": case_ids,
        "system_version": "spectrum-systems@test",
        "dataset_version": "golden@test",
        "timestamp": "2026-03-24T00:00:00Z",
    }


def _eval_cases(*, second_status: str = "pass") -> list[dict]:
    statuses = ["pass", second_status]
    return [
        {
            "artifact_type": "eval_case",
            "schema_version": "1.0.0",
            "trace_id": f"11111111-1111-4111-8111-11111111111{i}",
            "eval_case_id": f"eval-case-00{i+1}",
            "input_artifact_refs": [f"artifact://golden/case-00{i+1}/input"],
            "expected_output_spec": {
                "forced_status": status,
                "forced_score": 1.0 if status == "pass" else 0.0,
            },
            "scoring_rubric": {
                "weights": {"correctness": 1.0},
                "pass_threshold": 0.8,
            },
            "evaluation_type": "deterministic",
            "created_from": "manual",
        }
        for i, status in enumerate(statuses)
    ]


def _run_cli(tmp_path: Path, monkeypatch, *, policy_payload: dict | None = None, write_fail: bool = False) -> tuple[int, dict]:
    baseline_run = tmp_path / "baseline_eval_run.json"
    baseline_cases = tmp_path / "baseline_eval_cases.json"
    candidate_run = tmp_path / "candidate_eval_run.json"
    candidate_cases = tmp_path / "candidate_eval_cases.json"
    policy = tmp_path / "policy.json"
    coverage_policy = tmp_path / "coverage_policy.json"
    out_dir = tmp_path / "out"

    baseline_case_payload = _eval_cases(second_status="pass")
    candidate_case_payload = _eval_cases(second_status="pass")
    _write_json(baseline_run, _eval_run("baseline-eval-run", [c["eval_case_id"] for c in baseline_case_payload]))
    _write_json(candidate_run, _eval_run("candidate-eval-run", [c["eval_case_id"] for c in candidate_case_payload]))
    _write_json(baseline_cases, baseline_case_payload)
    _write_json(candidate_cases, candidate_case_payload)
    _write_json(policy, policy_payload or _policy())
    _write_json(
        coverage_policy,
        {
            "minimum_coverage_pct": 0.0,
            "risk_class_weights": {"high": 1.0, "medium": 1.0, "low": 1.0},
            "required_slices": ["slice.alpha"],
            "slice_aliases": {},
        },
    )

    if write_fail:
        original_write_text = Path.write_text

        def _fail_write(self, *args, **kwargs):
            if self.name == "evaluation_release_record.json":
                raise OSError("simulated-write-failure")
            return original_write_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", _fail_write)

    code = main(
        [
            "--baseline-eval-run",
            str(baseline_run),
            "--baseline-eval-cases",
            str(baseline_cases),
            "--candidate-eval-run",
            str(candidate_run),
            "--candidate-eval-cases",
            str(candidate_cases),
            "--release-policy",
            str(policy),
            "--coverage-policy",
            str(coverage_policy),
            "--output-dir",
            str(out_dir),
            "--baseline-version",
            "baseline-v1",
            "--candidate-version",
            "candidate-v1",
            "--baseline-prompt-version-id",
            "prompt-base",
            "--candidate-prompt-version-id",
            "prompt-cand",
            "--baseline-schema-version",
            "schema-base",
            "--candidate-schema-version",
            "schema-cand",
            "--baseline-policy-version-id",
            "policy-base",
            "--candidate-policy-version-id",
            "policy-cand",
        ]
    )

    record = {}
    record_path = out_dir / "evaluation_release_record.json"
    if record_path.exists():
        record = json.loads(record_path.read_text(encoding="utf-8"))
    return code, record


def test_happy_path_promote() -> None:
    record = _build()
    assert record["decision"] == "promote"


def test_required_slice_regression_triggers_rollback() -> None:
    record = _build(
        candidate_coverage_summary=_coverage("cov-cand", score=0.8, uncovered=["slice.alpha"]),
        candidate_slice_summaries=[_slice_summary(0.5)],
    )
    assert record["decision"] == "rollback"


def test_coverage_mismatch_non_promote() -> None:
    record = _build(candidate_coverage_summary=_coverage("cov-cand", score=1.0, total_cases=3))
    assert record["decision"] != "promote"
    assert record["canary_comparison_results"]["coverage_mismatch_fields"] == ["slice_case_counts", "total_eval_cases"]


def test_new_failure_identity_non_promote() -> None:
    record = _build(candidate_eval_results=[_eval_result("case-1", status="pass"), _eval_result("case-2", status="fail")])
    assert record["decision"] != "promote"
    assert "case-2" in record["canary_comparison_results"]["new_failures"]


def test_indeterminate_non_promote() -> None:
    record = _build(candidate_eval_results=[_eval_result("case-1", status="pass"), _eval_result("case-2", status="fail", indeterminate=True)])
    assert record["decision"] != "promote"


def test_exact_threshold_boundary_promotes() -> None:
    record = _build(
        baseline_eval_summary=_eval_summary("base-run", pass_rate=0.92, trace_suffix="3"),
        candidate_eval_summary=_eval_summary("cand-run", pass_rate=0.9, trace_suffix="4"),
    )
    assert record["canary_comparison_results"]["pass_rate_delta"] == -0.02
    assert record["decision"] == "promote"


def test_precedence_rollback_overrides_hold() -> None:
    policy = deepcopy(_policy())
    policy["rollback_triggers"] = ["new_failures_introduced"]
    record = _build(
        policy=policy,
        candidate_eval_summary=_eval_summary("cand-run", pass_rate=0.9, trace_suffix="5"),
        candidate_eval_results=[_eval_result("case-1", status="pass"), _eval_result("case-2", status="fail")],
    )
    assert record["decision"] == "rollback"


def test_deterministic_repeated_runs() -> None:
    one = _build()
    two = _build()
    assert one == two


def test_release_record_validates_against_schema() -> None:
    record = _build()
    validator = Draft202012Validator(load_schema("evaluation_release_record"), format_checker=FormatChecker())
    validator.validate(record)


def test_policy_load_failure_non_promote(tmp_path: Path, monkeypatch) -> None:
    bad_policy = tmp_path / "policy.json"
    bad_policy.write_text("{bad json", encoding="utf-8")
    coverage_policy = tmp_path / "coverage_policy.json"
    _write_json(
        coverage_policy,
        {
            "minimum_coverage_pct": 0.0,
            "risk_class_weights": {"high": 1.0, "medium": 1.0, "low": 1.0},
            "required_slices": ["slice.alpha"],
            "slice_aliases": {},
        },
    )
    code = main(
        [
            "--release-policy",
            str(bad_policy),
            "--coverage-policy",
            str(coverage_policy),
            "--output-dir",
            str(tmp_path / "out"),
            "--baseline-version",
            "baseline-v1",
            "--candidate-version",
            "candidate-v1",
            "--baseline-prompt-version-id",
            "prompt-base",
            "--candidate-prompt-version-id",
            "prompt-cand",
            "--baseline-schema-version",
            "schema-base",
            "--candidate-schema-version",
            "schema-cand",
            "--baseline-policy-version-id",
            "policy-base",
            "--candidate-policy-version-id",
            "policy-cand",
        ]
    )
    record = json.loads((tmp_path / "out" / "evaluation_release_record.json").read_text(encoding="utf-8"))
    assert code in (1, 2)
    assert record["decision"] in ("hold", "rollback")


def test_comparison_exception_non_promote(tmp_path: Path, monkeypatch) -> None:
    def _raise(*_args, **_kwargs):
        raise RuntimeError("comparison-failed")

    monkeypatch.setattr("scripts.run_release_canary.build_release_record", _raise)
    code, record = _run_cli(tmp_path, monkeypatch)
    assert code in (1, 2)
    assert record["decision"] in ("hold", "rollback")


def test_artifact_write_failure_non_promote(tmp_path: Path, monkeypatch) -> None:
    code, _record = _run_cli(tmp_path, monkeypatch, write_fail=True)
    assert code == 2
