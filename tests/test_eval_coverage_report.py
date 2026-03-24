from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from scripts.run_eval_coverage_report import build_eval_coverage, main
from spectrum_systems.contracts import load_schema


def _eval_case(case_id: str, slice_tags: list[str], *, risk_class: str = "high") -> dict:
    return {
        "artifact_type": "eval_case",
        "schema_version": "1.0.0",
        "trace_id": "11111111-1111-4111-8111-111111111111" if case_id == "case-1" else "11111111-1111-4111-8111-222222222222",
        "eval_case_id": case_id,
        "input_artifact_refs": [f"artifact://{case_id}/input"],
        "expected_output_spec": {"forced_status": "pass", "forced_score": 1.0},
        "scoring_rubric": {"pass_threshold": 0.8},
        "evaluation_type": "deterministic",
        "created_from": "manual",
        "slice_tags": slice_tags,
        "risk_class": risk_class,
        "priority": "p1",
    }


def _eval_result(case_id: str, status: str, trace_suffix: str) -> dict:
    return {
        "artifact_type": "eval_result",
        "schema_version": "1.0.0",
        "eval_case_id": case_id,
        "trace_id": f"22222222-2222-4222-8222-{int(trace_suffix):012d}",
        "result_status": status,
        "score": 1.0 if status == "pass" else 0.0,
        "failure_modes": [] if status == "pass" else ["expected_output_mismatch"],
        "provenance_refs": [f"trace://{case_id}"],
    }


def _policy() -> dict:
    return {
        "required_slices": [
            {
                "slice_id": "slice.alpha",
                "slice_name": "Alpha",
                "risk_class": "critical",
                "priority": "p0",
                "weight": 1.0,
            },
            {
                "slice_id": "slice.beta",
                "slice_name": "Beta",
                "risk_class": "high",
                "priority": "p1",
                "weight": 0.75,
            },
        ],
        "optional_slices": ["slice.gamma"],
        "minimum_cases_per_required_slice": 1,
        "minimum_pass_rate_by_risk_class": {
            "critical": 0.9,
            "high": 0.8,
            "medium": 0.7,
            "low": 0.6,
        },
        "indeterminate_counts_as_failure": True,
        "gap_severity_mapping": {
            "missing_required_slice": "critical",
            "zero_cases": "high",
            "below_min_cases": "medium",
            "below_pass_rate": "medium",
        },
    }


def _dataset() -> dict:
    return {
        "artifact_type": "eval_dataset",
        "schema_version": "1.0.0",
        "dataset_id": "dataset-test",
        "dataset_version": "1.0.0",
        "dataset_name": "Coverage test dataset",
        "status": "approved",
        "intended_use": "pre_merge_gate",
        "admission_policy_id": "policy-bbc-core",
        "canonicalization_policy_id": "canon-bbc-v1",
        "created_at": "2026-03-24T00:00:00Z",
        "created_by": "test-suite",
        "provenance": {
            "trace_id": "trace-coverage-dataset",
            "run_id": "run-coverage-dataset",
            "source_artifact_ids": ["case-1"],
        },
        "members": [
            {
                "artifact_type": "eval_case",
                "artifact_id": "case-1",
                "artifact_version": "1.0.0",
                "source": "manual",
                "admission_status": "admitted",
                "admission_reason_code": "meets_policy",
                "provenance_ref": "trace://case-1",
            }
        ],
        "summary": {
            "total_members": 1,
            "admitted_members": 1,
            "rejected_members": 0,
            "contains_failure_generated_cases": False,
        },
    }


def test_grouping_aggregation_gaps_and_weighted_score() -> None:
    eval_cases = [
        _eval_case("case-1", ["slice.alpha"]),
        _eval_case("case-2", ["slice.alpha", "slice.gamma"]),
    ]
    eval_results = [
        _eval_result("case-1", "pass", "1"),
        _eval_result("case-2", "indeterminate", "2"),
    ]

    coverage, slice_summaries, markdown = build_eval_coverage(
        eval_cases=eval_cases,
        eval_results=eval_results,
        datasets=[_dataset()],
        policy=_policy(),
        coverage_run_id="cov-run-1",
        timestamp="2026-03-24T00:00:00Z",
    )

    by_slice = {item["slice_id"]: item for item in slice_summaries}
    assert set(by_slice.keys()) == {"slice.alpha", "slice.beta", "slice.gamma"}

    assert by_slice["slice.alpha"]["total_cases"] == 2
    assert by_slice["slice.alpha"]["pass_count"] == 1
    assert by_slice["slice.alpha"]["indeterminate_count"] == 1
    assert by_slice["slice.alpha"]["failure_rate"] == 0.5

    assert by_slice["slice.beta"]["total_cases"] == 0
    assert "slice.beta" in coverage["uncovered_required_slices"]

    # Weighted score is deterministic: (alpha covered=1.0 + beta uncovered=0.0) / (1.0 + 0.75)
    assert coverage["risk_weighted_coverage_score"] == 0.571429
    assert any(gap["slice_id"] == "slice.beta" for gap in coverage["coverage_gaps"])

    assert "## Coverage Overview" in markdown
    assert "## Top Failing Slices" in markdown
    assert "aggregate pass rate alone is insufficient" in markdown.lower()


def test_schema_validation_of_emitted_coverage_artifacts() -> None:
    eval_cases = [_eval_case("case-1", ["slice.alpha"])]
    eval_results = [_eval_result("case-1", "pass", "9")]

    coverage, slices, _ = build_eval_coverage(
        eval_cases=eval_cases,
        eval_results=eval_results,
        datasets=[_dataset()],
        policy=_policy(),
        coverage_run_id="cov-run-2",
        timestamp="2026-03-24T00:00:00Z",
    )

    cov_validator = Draft202012Validator(load_schema("eval_coverage_summary"), format_checker=FormatChecker())
    cov_validator.validate(coverage)

    slice_validator = Draft202012Validator(load_schema("eval_slice_summary"), format_checker=FormatChecker())
    for item in slices:
        slice_validator.validate(item)


def test_cli_writes_expected_artifacts_and_report_sections(tmp_path: Path) -> None:
    eval_cases = [_eval_case("case-1", ["slice.alpha"])]
    eval_results = [_eval_result("case-1", "fail", "4")]

    eval_cases_path = tmp_path / "eval_cases.json"
    eval_results_path = tmp_path / "eval_results.json"
    dataset_path = tmp_path / "dataset.json"
    policy_path = tmp_path / "policy.json"
    output_dir = tmp_path / "out"

    eval_cases_path.write_text(json.dumps(eval_cases, indent=2) + "\n", encoding="utf-8")
    eval_results_path.write_text(json.dumps(eval_results, indent=2) + "\n", encoding="utf-8")
    dataset_path.write_text(json.dumps(_dataset(), indent=2) + "\n", encoding="utf-8")
    policy_path.write_text(json.dumps(_policy(), indent=2) + "\n", encoding="utf-8")

    code = main(
        [
            "--eval-cases",
            str(eval_cases_path),
            "--eval-results",
            str(eval_results_path),
            "--dataset",
            str(dataset_path),
            "--policy",
            str(policy_path),
            "--output-dir",
            str(output_dir),
            "--coverage-run-id",
            "cov-run-3",
        ]
    )

    assert code == 0
    assert (output_dir / "eval_coverage_summary.json").exists()
    assert (output_dir / "eval_slice_summaries.json").exists()

    report = (output_dir / "eval_coverage_report.md").read_text(encoding="utf-8")
    assert "## Per-Slice Breakdown" in report
    assert "## Zero-Case Slices" in report
    assert "Aggregate pass rate" in report


def test_indeterminate_policy_alias_is_respected() -> None:
    eval_cases = [_eval_case("case-1", ["slice.alpha"])]
    eval_results = [_eval_result("case-1", "indeterminate", "11")]
    policy = _policy()
    policy["indeterminate_counts_as_failure"] = False
    policy["indeterminate_is_blocking"] = True

    _, slices, _ = build_eval_coverage(
        eval_cases=eval_cases,
        eval_results=eval_results,
        datasets=[],
        policy=policy,
        coverage_run_id="cov-run-alias",
        timestamp="2026-03-24T00:00:00Z",
    )
    assert slices[0]["failure_rate"] == 1.0


def test_cli_default_coverage_run_id_is_deterministic(tmp_path: Path) -> None:
    eval_cases = [_eval_case("case-1", ["slice.alpha"])]
    eval_results = [_eval_result("case-1", "pass", "12")]
    eval_cases_path = tmp_path / "eval_cases.json"
    eval_results_path = tmp_path / "eval_results.json"
    policy_path = tmp_path / "policy.json"
    out_one = tmp_path / "out1"
    out_two = tmp_path / "out2"

    eval_cases_path.write_text(json.dumps(eval_cases, indent=2) + "\n", encoding="utf-8")
    eval_results_path.write_text(json.dumps(eval_results, indent=2) + "\n", encoding="utf-8")
    policy_path.write_text(json.dumps(_policy(), indent=2) + "\n", encoding="utf-8")

    code_one = main(["--eval-cases", str(eval_cases_path), "--eval-results", str(eval_results_path), "--policy", str(policy_path), "--output-dir", str(out_one)])
    code_two = main(["--eval-cases", str(eval_cases_path), "--eval-results", str(eval_results_path), "--policy", str(policy_path), "--output-dir", str(out_two)])
    assert code_one == 0
    assert code_two == 0

    coverage_one = json.loads((out_one / "eval_coverage_summary.json").read_text(encoding="utf-8"))
    coverage_two = json.loads((out_two / "eval_coverage_summary.json").read_text(encoding="utf-8"))
    assert coverage_one["coverage_run_id"] == coverage_two["coverage_run_id"]
